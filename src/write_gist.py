import argparse
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

gh_api_key = os.getenv("gh_api_key")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
GUIDS_PATH = DATA_DIR / "guidsToGistIds.json"
HASHES_PATH = DATA_DIR / "textCacheHashes.json"
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "write_gist.log", rotation="256 KB", retention=5, enqueue=False)

MD_IMAGE_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<url><[^>]+>|[^)\s]+)(?P<title>\s+(?:\"[^\"]*\"|'[^']*'))?\)"
)
HTML_IMAGE_PATTERN = re.compile(
    r'(<img[^>]*\s+src=)(?P<quote>["\'])(?P<url>[^"\']+)(?P=quote)',
    re.IGNORECASE,
)


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        path.write_text("{}")
        return {}
    content = path.read_text().strip()
    if not content:
        return {}
    return json.loads(content)


def _write_json_file(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=4))


def _normalize_image_url(url: str) -> str:
    cleaned_url = url.strip()
    if cleaned_url.startswith("<") and cleaned_url.endswith(">"):
        cleaned_url = cleaned_url[1:-1].strip()
    return cleaned_url


def _extract_image_urls(markdown_text: str) -> list[str]:
    urls = [match.group("url") for match in MD_IMAGE_PATTERN.finditer(markdown_text)]
    urls.extend(
        match.group("url") for match in HTML_IMAGE_PATTERN.finditer(markdown_text)
    )
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


def _build_image_assets(
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

        filename = _dedupe_filename(filename, used_filenames, normalized_url)
        assets[normalized_url] = {"filename": filename, "content": content}

    return assets


def _build_raw_url(owner_login: str, gist_id: str, filename: str) -> str:
    return f"https://gist.githubusercontent.com/{owner_login}/{gist_id}/raw/{filename}"


def _rewrite_markdown_images(markdown_text: str, url_map: dict[str, str]) -> str:
    def replace_markdown(match: re.Match) -> str:
        original_url = match.group("url")
        normalized_url = _normalize_image_url(original_url)
        new_url = url_map.get(normalized_url)
        if not new_url:
            return match.group(0)
        formatted_url = f"<{new_url}>" if original_url.startswith("<") else new_url
        title = match.group("title") or ""
        return f"![{match.group('alt')}]({formatted_url}{title})"

    def replace_html(match: re.Match) -> str:
        original_url = match.group("url")
        normalized_url = _normalize_image_url(original_url)
        new_url = url_map.get(normalized_url)
        if not new_url:
            return match.group(0)
        return f"{match.group(1)}{match.group('quote')}{new_url}{match.group('quote')}"

    updated = MD_IMAGE_PATTERN.sub(replace_markdown, markdown_text)
    return HTML_IMAGE_PATTERN.sub(replace_html, updated)


def _calculate_content_signature(
    markdown_text: str, image_assets: dict[str, dict]
) -> str:
    signature = hashlib.sha1()
    signature.update(markdown_text.encode())
    for asset_key in sorted(image_assets.keys()):
        asset = image_assets[asset_key]
        signature.update(asset["filename"].encode())
        signature.update(asset["content"])
    return signature.hexdigest()


def _mask_token(value: str) -> str:
    if not gh_api_key:
        return value
    return value.replace(gh_api_key, "***")


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
        logger.error("Git command failed: {}", _mask_token(" ".join(command)))
        if result.stdout.strip():
            logger.error("Git stdout: {}", _mask_token(result.stdout.strip()))
        if result.stderr.strip():
            logger.error("Git stderr: {}", _mask_token(result.stderr.strip()))
        raise RuntimeError("Git command failed")


def _sync_images_with_gist_repo(
    gist_id: str, image_assets: dict[str, dict]
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
            logger.error(
                "Git status failed: {}",
                _mask_token(status_result.stderr.strip()),
            )
            raise RuntimeError("Git status failed")
        if not status_result.stdout.strip():
            logger.info("No image changes to push")
            return

        _run_git(["commit", "-m", "Add gist images"], cwd=repo_dir)
        _run_git(["push", "origin", "HEAD"], cwd=repo_dir)


def _get_gist_metadata(gist_id: str, headers: dict) -> dict | None:
    gist_endpoint = f"https://api.github.com/gists/{gist_id}"
    gist_response = requests.get(gist_endpoint, headers=headers)
    if gist_response.status_code != 200:
        logger.error("Error fetching gist metadata: {} {}", gist_id, gist_response.text)
        return None
    return gist_response.json()


def _create_gist(
    markdown_text: str, gist_file_name: str, headers: dict
) -> dict | None:
    data = {
        "description": gist_file_name,
        "files": {
            f"{gist_file_name}.md": {"content": markdown_text, "type": "text/plain"}
        },
        "public": False,
    }
    response = requests.post("https://api.github.com/gists", json=data, headers=headers)
    if response.status_code not in [200, 201]:
        logger.error("Error when creating gist: {}", gist_file_name)
        logger.error("Response: {}", response.text)
        logger.error("Payload: {}", json.dumps(data, indent=4))
        return None
    return response.json()


def _update_gist(
    gist_id: str, markdown_text: str, gist_file_name: str, headers: dict
) -> dict | None:
    data = {
        "description": gist_file_name,
        "files": {
            f"{gist_file_name}.md": {"content": markdown_text, "type": "text/plain"}
        },
    }
    endpoint = f"https://api.github.com/gists/{gist_id}"
    response = requests.post(endpoint, json=data, headers=headers)
    if response.status_code not in [200, 201]:
        logger.error("Error when updating gist: {} {}", gist_id, gist_file_name)
        logger.error("Response: {}", response.text)
        logger.error("Payload: {}", json.dumps(data, indent=4))
        return None
    return response.json()


def check_if_updated(content_signature: str, gist_id: str) -> bool:
    hash_dict = {}
    while hash_dict == {}:
        try:
            hash_dict = _read_json_file(HASHES_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", HASHES_PATH, exc)
            time.sleep(1)
    if (gist_id not in hash_dict) or (content_signature != hash_dict[gist_id]):
        hash_dict[gist_id] = content_signature
        _write_json_file(HASHES_PATH, hash_dict)
        return True
    return False


def write_to_gist(
    text: str,
    gist_file_name: str,
    gist_id: str | None = None,
    markdown_path: Path | None = None,
):
    gist_file_name = "".join(c if c.isalnum() else " " for c in gist_file_name)

    logger.info("Writing to gist")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_api_key}",
    }

    image_assets = _build_image_assets(text, markdown_path)

    owner_login = None
    is_new_gist = gist_id is None
    if gist_id:
        gist_metadata = _get_gist_metadata(gist_id, headers)
        if gist_metadata is None:
            return None
        owner_login = gist_metadata.get("owner", {}).get("login")

    if not owner_login and gist_id:
        logger.error("Missing gist owner for {}", gist_id)
        return None

    if not gist_id:
        created = _create_gist(text, gist_file_name, headers)
        if created is None:
            return None
        gist_id = created["id"]
        owner_login = created.get("owner", {}).get("login")
        if not owner_login:
            logger.error("Missing gist owner after creation for {}", gist_id)
            return None

    raw_url_map = {
        source_url: _build_raw_url(owner_login, gist_id, asset["filename"])
        for source_url, asset in image_assets.items()
    }
    updated_text = _rewrite_markdown_images(text, raw_url_map)
    content_signature = _calculate_content_signature(updated_text, image_assets)

    if not is_new_gist:
        if not check_if_updated(content_signature, gist_id):
            return gist_id

    update_result = _update_gist(gist_id, updated_text, gist_file_name, headers)
    if update_result is None:
        return None

    _sync_images_with_gist_repo(gist_id, image_assets)
    check_if_updated(content_signature, gist_id)
    return gist_id


def getGistIdFromGUID(guid: str):
    guid_to_gist_id_dict = {}
    while guid_to_gist_id_dict == {}:
        try:
            guid_to_gist_id_dict = _read_json_file(GUIDS_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", GUIDS_PATH, exc)
            time.sleep(1)
            continue
    gist_id = guid_to_gist_id_dict[guid] if guid in guid_to_gist_id_dict else None
    return gist_id


def setGistIdForGUID(guid: str, gist_id: str):
    guid_to_gist_id_dict = {}
    while guid_to_gist_id_dict == {}:
        try:
            guid_to_gist_id_dict = _read_json_file(GUIDS_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", GUIDS_PATH, exc)
            time.sleep(1)
            continue
    guid_to_gist_id_dict[guid] = gist_id
    _write_json_file(GUIDS_PATH, guid_to_gist_id_dict)


# Adjusted CLI functions with minimal KVP dict and specialized JSON conversion
def getGistUrl(name: str):
    gist_id = getGistIdFromGUID(name)
    if not gist_id:
        return False
    return "https://gist.github.com/" + gist_id


def writeContent(url, guid, name, textFilePath):
    name = "" if not name else name
    text_file_path = Path(textFilePath)
    with text_file_path.open("r") as file:
        markdown_text = file.read()
    if url:
        gist_id = url.split("/")[-1]
        write_to_gist(markdown_text, name, gist_id, markdown_path=text_file_path)
    elif guid:
        gist_id = write_to_gist(
            markdown_text,
            name,
            gist_id=getGistIdFromGUID(guid),
            markdown_path=text_file_path,
        )
        setGistIdForGUID(guid, gist_id)
    else:
        gist_id = write_to_gist(markdown_text, name, markdown_path=text_file_path)

    return "https://gist.github.com/" + gist_id


def main():
    parser = argparse.ArgumentParser(
        description="A CLI tool for managing GitHub Gists."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("url", help="Get a gist's URL given its GUID")
    info_parser.add_argument("--guid", type=str, help="GUID of the gist.")

    write_parser = subparsers.add_parser(
        "write",
        help="Write or update a gist's content from a text file, given the gist's GUID or URL.",
    )
    write_parser.add_argument("--path", type=str, help="Path to the text file.")
    write_parser.add_argument("--url", type=str, help="URL of the gist.", default=None)
    write_parser.add_argument(
        "--guid", type=str, help="GUID of the gist.", default=None
    )
    write_parser.add_argument("--name", type=str, help="Name of the gist.")

    delete_parser = subparsers.add_parser(
        "delete", help="Delete a gist, given the its GUID or URL."
    )
    delete_parser.add_argument("--url", type=str, help="URL of the gist.", default=None)
    delete_parser.add_argument(
        "--guid", type=str, help="GUID of the gist.", default=None
    )

    args = parser.parse_args()

    result = None
    if args.command == "url":
        result = getGistUrl(args.guid)
    elif args.command == "write":
        result = writeContent(args.url, args.guid, args.name, args.path)

    print(result)


if __name__ == "__main__":
    main()
