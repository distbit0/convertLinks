import hashlib
import mimetypes
import os
import re
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

import requests
from loguru import logger

MD_IMAGE_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<url><[^>]+>|[^)\s]+)(?P<title>\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)
HTML_IMAGE_PATTERN = re.compile(
    r'(<img[^>]*\s+src=)(?P<quote>["\'])(?P<url>[^"\']+)(?P=quote)',
    re.IGNORECASE,
)
MD_LINK_PATTERN = re.compile(
    r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<url><[^>]+>|[^)\s]+)(?P<title>\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)


def _normalize_image_url(url: str) -> str:
    cleaned_url = url.strip()
    if cleaned_url.startswith("<") and cleaned_url.endswith(">"):
        cleaned_url = cleaned_url[1:-1].strip()
    return cleaned_url


def _looks_like_image_url(url: str) -> bool:
    lowered = url.lower()
    if any(
        lowered.endswith(ext)
        for ext in (
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".svg",
            ".bmp",
            ".tif",
            ".tiff",
        )
    ):
        return True
    if "substackcdn.com/image" in lowered:
        return True
    if "substack-post-media.s3.amazonaws.com" in lowered:
        return True
    return False


def _extract_image_urls(markdown_text: str) -> list[str]:
    urls = [match.group("url") for match in MD_IMAGE_PATTERN.finditer(markdown_text)]
    urls.extend(
        match.group("url") for match in HTML_IMAGE_PATTERN.finditer(markdown_text)
    )
    for match in MD_LINK_PATTERN.finditer(markdown_text):
        if match.group("text"):
            continue
        url = match.group("url")
        normalized_url = _normalize_image_url(url)
        if _looks_like_image_url(normalized_url):
            urls.append(url)
    return urls


def _guess_extension(content_type: str | None) -> str | None:
    if content_type:
        extension = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if extension:
            return extension
    return None


def _dedupe_filename(filename: str, used_filenames: set[str], seed: str) -> str:
    if filename not in used_filenames:
        used_filenames.add(filename)
        return filename
    stem, suffix = os.path.splitext(filename)
    short_hash = hashlib.sha1(seed.encode()).hexdigest()[:8]
    deduped = f"{stem}-{short_hash}{suffix}"
    used_filenames.add(deduped)
    logger.warning("Duplicate image filename {} renamed to {}", filename, deduped)
    return deduped


def _sanitize_filename(filename: str) -> str:
    cleaned = filename.replace("\\", "_").replace("/", "_")
    cleaned = cleaned.strip()
    if cleaned in {"", ".", ".."}:
        return ""
    return cleaned


def _resolve_local_image_path(image_url: str, markdown_path: Path | None) -> Path:
    parsed = urllib.parse.urlparse(image_url)
    if parsed.scheme == "file":
        path = Path(urllib.parse.unquote(parsed.path))
    else:
        candidate = Path(image_url)
        if candidate.is_absolute():
            path = candidate
        else:
            if markdown_path is None:
                raise ValueError(
                    f"Relative image path {image_url} requires a markdown source path."
                )
            path = (markdown_path.parent / candidate).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")
    return path


def _download_remote_image(image_url: str) -> tuple[bytes, str | None, str | None]:
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    parsed = urllib.parse.urlparse(image_url)
    filename = os.path.basename(parsed.path)
    if filename:
        filename = urllib.parse.unquote(filename)
    return response.content, response.headers.get("Content-Type"), filename or None


def build_image_assets(
    markdown_text: str, markdown_path: Path | None
) -> dict[str, dict]:
    image_urls = _extract_image_urls(markdown_text)
    if not image_urls:
        return {}

    assets: dict[str, dict] = {}
    used_filenames: set[str] = set()
    for raw_url in image_urls:
        normalized_url = _normalize_image_url(raw_url)
        if normalized_url.startswith("data:"):
            logger.info("Skipping inline data image")
            continue
        if normalized_url in assets:
            continue

        if normalized_url.startswith(("http://", "https://")):
            content, content_type, filename = _download_remote_image(normalized_url)
        else:
            image_path = _resolve_local_image_path(normalized_url, markdown_path)
            content = image_path.read_bytes()
            content_type = mimetypes.guess_type(image_path.name)[0]
            filename = image_path.name

        if not filename:
            extension = _guess_extension(content_type)
            if not extension:
                raise ValueError(
                    f"Unable to infer extension for image {normalized_url}"
                )
            short_hash = hashlib.sha1(normalized_url.encode()).hexdigest()[:12]
            filename = f"image-{short_hash}{extension}"
            logger.warning(
                "Image URL {} has no filename; using {}", normalized_url, filename
            )
        else:
            filename = _sanitize_filename(filename)
            if not filename:
                extension = _guess_extension(content_type)
                if not extension:
                    raise ValueError(
                        f"Unable to infer extension for image {normalized_url}"
                    )
                short_hash = hashlib.sha1(normalized_url.encode()).hexdigest()[:12]
                filename = f"image-{short_hash}{extension}"
                logger.warning(
                    "Image URL {} produced an unsafe filename; using {}",
                    normalized_url,
                    filename,
                )

        filename = _dedupe_filename(filename, used_filenames, normalized_url)
        assets[normalized_url] = {"filename": filename, "content": content}

    return assets


def build_raw_url(owner_login: str, gist_id: str, filename: str) -> str:
    return f"https://gist.githubusercontent.com/{owner_login}/{gist_id}/raw/{filename}"


def rewrite_markdown_images(markdown_text: str, url_map: dict[str, str]) -> str:
    def replace_markdown(match: re.Match) -> str:
        original_url = match.group("url")
        normalized_url = _normalize_image_url(original_url)
        new_url = url_map.get(normalized_url)
        if not new_url:
            return match.group(0)
        formatted_url = f"<{new_url}>" if original_url.startswith("<") else new_url
        title = match.group("title") or ""
        return f"![{match.group('alt')}]({formatted_url}{title})"

    def replace_link(match: re.Match) -> str:
        if match.group("text"):
            return match.group(0)
        original_url = match.group("url")
        normalized_url = _normalize_image_url(original_url)
        if not _looks_like_image_url(normalized_url):
            return match.group(0)
        new_url = url_map.get(normalized_url)
        if not new_url:
            return match.group(0)
        formatted_url = f"<{new_url}>" if original_url.startswith("<") else new_url
        title = match.group("title") or ""
        return f"![]({formatted_url}{title})"

    def replace_html(match: re.Match) -> str:
        original_url = match.group("url")
        normalized_url = _normalize_image_url(original_url)
        new_url = url_map.get(normalized_url)
        if not new_url:
            return match.group(0)
        return f"{match.group(1)}{match.group('quote')}{new_url}{match.group('quote')}"

    updated = MD_IMAGE_PATTERN.sub(replace_markdown, markdown_text)
    updated = MD_LINK_PATTERN.sub(replace_link, updated)
    return HTML_IMAGE_PATTERN.sub(replace_html, updated)


def calculate_content_signature(
    markdown_text: str, image_assets: dict[str, dict]
) -> str:
    signature = hashlib.sha1()
    signature.update(markdown_text.encode())
    for asset_key in sorted(image_assets.keys()):
        asset = image_assets[asset_key]
        signature.update(asset["filename"].encode())
        signature.update(asset["content"])
    return signature.hexdigest()


def _mask_token(value: str, token: str | None) -> str:
    if not token:
        return value
    return value.replace(token, "***")


def _run_git(command: list[str], cwd: Path | None = None) -> None:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        ["git", *command],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Git command failed: {}", " ".join(command))
        if result.stdout.strip():
            logger.error("Git stdout: {}", result.stdout.strip())
        if result.stderr.strip():
            logger.error("Git stderr: {}", result.stderr.strip())
        raise RuntimeError("Git command failed")


def sync_images_with_gist_repo(
    gist_id: str, image_assets: dict[str, dict], gh_api_key: str
) -> None:
    if not image_assets:
        return
    if not gh_api_key:
        raise RuntimeError("gh_api_key is required to push gist images")

    token = urllib.parse.quote(gh_api_key, safe="")
    remote = f"https://{token}@gist.github.com/{gist_id}.git"

    with tempfile.TemporaryDirectory() as temp_dir:
        repo_dir = Path(temp_dir) / "gist"
        logger.info("Cloning gist for image sync")
        _run_git(["clone", remote, str(repo_dir)])
        _run_git(["config", "user.email", "gist-bot@local"], cwd=repo_dir)
        _run_git(["config", "user.name", "gist-bot"], cwd=repo_dir)

        for asset in image_assets.values():
            file_path = repo_dir / asset["filename"]
            file_path.write_bytes(asset["content"])

        _run_git(
            ["add", "--"] + [asset["filename"] for asset in image_assets.values()],
            cwd=repo_dir,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if status_result.returncode != 0:
            logger.error("Git status failed: {}", status_result.stderr.strip())
            raise RuntimeError("Git status failed")
        if not status_result.stdout.strip():
            logger.info("No image changes to push")
            return

        _run_git(["commit", "-m", "Add gist images"], cwd=repo_dir)
        _run_git(["push", "origin", "HEAD"], cwd=repo_dir)
