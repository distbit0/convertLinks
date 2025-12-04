import re
from pathlib import Path

import requests
from loguru import logger

import utilities


def getUniqueUrl(url: str) -> str:
    unique_url = url.lower()
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)
    return unique_url


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "convertDiscourse.log",
    rotation="256 KB",
    retention=5,
    enqueue=True,
)


def _extract_title(markdown_content: str, fallback: str) -> str:
    for line in markdown_content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _build_raw_url(url: str) -> str | None:
    cleaned = re.sub(r"[#?].*$", "", url).rstrip("/")

    if "/raw/" in cleaned:
        return cleaned

    match = re.search(
        r"^(https?://[^/]+)/t/(?:[^/]+/)?(?P<topic_id>\d+)(?:/.*)?$", cleaned
    )
    if not match:
        logger.error(f"Unable to parse discourse url: {url}")
        return None

    base = match.group(1)
    topic_id = match.group("topic_id")
    return f"{base}/raw/{topic_id}"


def convertDiscourse(url: str, forceRefresh: bool):
    raw_url = _build_raw_url(url)
    if not raw_url:
        return False

    unique_url = getUniqueUrl(raw_url)
    gist_url = utilities.getGistUrl(unique_url)
    if gist_url and not forceRefresh:
        return gist_url

    try:
        response = requests.get(raw_url, timeout=20)
        response.raise_for_status()
    except Exception as exc:
        logger.error(f"Failed to fetch markdown from {raw_url}: {exc}")
        return False

    markdown_content = response.text.strip()
    if not markdown_content:
        logger.error(f"Received empty markdown response from {raw_url}")
        return False

    title = _extract_title(markdown_content, unique_url)

    gist_url = utilities.writeGist(
        markdown_content,
        "DISC: " + title,
        unique_url,
        update=True,
        source_url=url,
    )
    return gist_url


if __name__ == "__main__":
    sample = (
        "https://research.lido.fi/t/"
        "liquid-buybacks-nest-execution-with-ldo-wsteth-liquidity/10894"
    )
    print(_build_raw_url(sample))
