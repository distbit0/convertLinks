import os
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import html2text
import requests
from bs4 import BeautifulSoup
from loguru import logger
from readability import Document

DEFAULT_USER_AGENT = os.getenv("ARTICLE_USER_AGENT") or (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def is_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    return urlunparse(parsed._replace(fragment=""))


def strip_tracking_params(
    url: str, *, drop_params: set[str] | None = None, keep_params: set[str] | None = None
) -> str:
    parsed = urlparse(url)
    if not parsed.query:
        return url

    drop = {param.lower() for param in (drop_params or set())}
    keep = {param.lower() for param in (keep_params or set())}
    filtered_params = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in keep:
            filtered_params.append((key, value))
            continue
        if lowered.startswith("utm_") or lowered in drop:
            continue
        filtered_params.append((key, value))

    cleaned_query = urlencode(filtered_params, doseq=True)
    return urlunparse(parsed._replace(query=cleaned_query))


def fetch_html(url: str, *, timeout: int = 20) -> str:
    response = requests.get(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    html = response.text
    if not html.strip():
        raise ValueError(f"Empty HTML response for {url}")
    return html


def _extract_title(document: Document) -> str:
    title = ""
    try:
        title = document.short_title()
    except Exception as exc:
        logger.debug("Failed to read short_title: {}", exc)

    if not title:
        try:
            title = document.title()
        except Exception as exc:
            logger.debug("Failed to read title: {}", exc)

    if not title:
        return ""
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _html_to_markdown(html: str, base_url: str | None) -> str:
    converter = html2text.HTML2Text()
    converter.body_width = 0
    if base_url and hasattr(converter, "baseurl"):
        converter.baseurl = base_url
    return converter.handle(html)


def _normalize_markdown(markdown: str) -> str:
    cleaned = markdown.replace("\r\n", "\n").strip()
    cleaned = _convert_empty_image_links(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def _looks_like_image_url(url: str) -> bool:
    lowered = url.lower()
    if any(
        lowered.endswith(ext)
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff")
    ):
        return True
    if "substackcdn.com/image" in lowered:
        return True
    if "substack-post-media.s3.amazonaws.com" in lowered:
        return True
    return False


def _convert_empty_image_links(markdown: str) -> str:
    pattern = re.compile(
        r"(?<!!)\[(?P<text>[^\]]*)\]\((?P<url><[^>]+>|[^)\s]+)(?P<title>\s+(?:\"[^\"]*\"|'[^']*'))?\)"
    )

    def replace(match: re.Match) -> str:
        if match.group("text"):
            return match.group(0)
        url = match.group("url").strip()
        if url.startswith("<") and url.endswith(">"):
            url = url[1:-1].strip()
        if not _looks_like_image_url(url):
            return match.group(0)
        formatted_url = f"<{url}>" if match.group("url").startswith("<") else url
        title = match.group("title") or ""
        return f"![]({formatted_url}{title})"

    return pattern.sub(replace, markdown)


def _is_substack_url(base_url: str | None) -> bool:
    if not base_url:
        return False
    hostname = urlparse(base_url).netloc.lower()
    return hostname.endswith("substack.com")


def _extract_substack_body_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("div.body.markup") or soup.select_one("div.body")
    if not body:
        raise ValueError("Substack body markup not found in HTML")
    return str(body)


def extract_article_markdown(html: str, base_url: str | None) -> tuple[str, str]:
    document = Document(html)
    title = _extract_title(document)
    if _is_substack_url(base_url):
        content_html = _extract_substack_body_html(html)
    else:
        content_html = document.summary()
    markdown = _html_to_markdown(content_html, base_url)
    markdown = _normalize_markdown(markdown)
    if title and not markdown.lstrip().startswith("#"):
        markdown = f"# {title}\n\n{markdown}"
    return markdown, title
