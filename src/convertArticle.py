import sys
from pathlib import Path

from loguru import logger

import article_utils
import utilities

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(sys.stdout, level="INFO")
logger.add(
    LOG_DIR / "convertArticle.log",
    rotation="256 KB",
    retention=5,
    enqueue=True,
)


def convertArticle(
    url: str,
    forceRefresh: bool,
    *,
    prefix: str = "ART",
    source_label: str = "article",
):
    cleaned_url = article_utils.normalize_url(url)
    if not article_utils.is_http_url(cleaned_url):
        logger.warning("Skipping non-http URL {}", url)
        return False

    unique_url = utilities.build_guid_from_url(cleaned_url)
    gist_url = utilities.get_gist_url_for_guid(unique_url)
    if gist_url and not forceRefresh:
        return gist_url

    try:
        html = article_utils.fetch_html(cleaned_url)
        markdown, title = article_utils.extract_article_markdown(html, cleaned_url)
    except Exception as exc:
        logger.error("Failed to convert {} {}: {}", source_label, cleaned_url, exc)
        return False

    if not markdown.strip():
        logger.error("Empty markdown extracted from {}", cleaned_url)
        return False

    gist_url = utilities.writeGist(
        markdown,
        f"{prefix}: {title or unique_url}",
        unique_url,
        update=True,
        source_url=cleaned_url,
    )
    return gist_url
