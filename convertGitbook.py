import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from loguru import logger

import utilities


def getUniqueUrl(url):
    unique_url = url.lower()
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)
    return unique_url


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "convertGitbook.log",
    rotation="256 KB",
    retention=5,
    enqueue=True,
)


def _build_markdown_url(url: str) -> str:
    sanitized = url.rstrip("/")
    return sanitized if sanitized.endswith(".md") else f"{sanitized}.md"


def _is_domain_only(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path or ""
    return path in ("", "/")


def _extract_title(markdown_content: str, fallback: str) -> str:
    for line in markdown_content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def convertGitbook(url, forceRefresh):
    if "docs.google.com" in url:
        return url
    if ".pdf" in url:
        return url
    if _is_domain_only(url):
        return url
    url = re.sub(r"#.*", "", url)  # Remove #comments from the URL
    unique_url = getUniqueUrl(url)
    gistUrl = utilities.getGistUrl(unique_url)
    if gistUrl and not forceRefresh:
        return gistUrl
    markdown_url = _build_markdown_url(url)
    try:
        response = requests.get(markdown_url, timeout=20)
        response.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch markdown from {markdown_url}: {exc}")
        return False

    markdown_content = response.text.strip()
    if not markdown_content:
        logger.error(f"Received empty markdown response from {markdown_url}")
        return False

    title = _extract_title(markdown_content, unique_url)

    gist_url = utilities.writeGist(
        markdown_content,
        "GITB: " + title,
        unique_url,
        update=True,
        source_url=url,
    )
    return gist_url


if __name__ == "__main__":
    print(convertGitbook("https://docs.butter.markets/user-guide/how-to-trade", True))
