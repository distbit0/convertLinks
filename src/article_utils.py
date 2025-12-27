import json
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
MAX_COMMENTS = 20
MAX_COMMENT_DEPTH = 4


def is_http_url(url: str) -> bool:
    return url.startswith(("http://", "https://"))


def normalize_url(url: str) -> str:
    cleaned = url.strip()
    parsed = urlparse(cleaned)
    return urlunparse(parsed._replace(fragment=""))


def strip_tracking_params(
    url: str,
    *,
    drop_params: set[str] | None = None,
    keep_params: set[str] | None = None,
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


def _prepare_html_for_readability(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    updated = False

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if not _looks_like_image_url(href):
            continue
        if anchor.get_text(strip=True):
            continue
        if anchor.find(["img", "picture", "source"]) is None:
            continue
        anchor.unwrap()
        updated = True

    for container in list(soup.find_all(["figure", "div"])):
        imgs = container.find_all("img")
        if not imgs:
            continue
        text = container.get_text(" ", strip=True)
        if text and len(text) > 200:
            continue
        next_paragraph = container.find_next_sibling("p")
        previous_paragraph = container.find_previous_sibling("p")
        target = next_paragraph or previous_paragraph
        if not target:
            continue
        for img in imgs:
            if target is next_paragraph:
                target.insert(0, img)
            else:
                target.append(img)
        if text:
            target.append(soup.new_string(f" {text}"))
        container.decompose()
        updated = True

    return str(soup) if updated else html


def _normalize_comment_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def _format_comment_author(display_name: str | None, username: str | None) -> str:
    if display_name:
        return display_name.strip()
    if username:
        return username.strip()
    logger.warning("Comment missing username and display name")
    return "[missing username]"


def _parse_lesswrong_post_id(url: str) -> str | None:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if "posts" not in parts:
        return None
    idx = parts.index("posts")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def _fetch_lesswrong_comments(post_id: str) -> list[dict]:
    query = """
    query PostComments($postId: String!, $limit: Int, $offset: Int) {
      comments(
        selector: {postCommentsTop: {postId: $postId}}
        limit: $limit
        offset: $offset
        enableTotal: true
      ) {
        results {
          _id
          parentCommentId
          deleted
          pageUrl
          user { displayName username }
          contents { plaintextMainText }
        }
      }
    }
    """
    response = requests.post(
        "https://www.lesswrong.com/graphql",
        json={
            "query": query,
            "variables": {"postId": post_id, "limit": 200, "offset": 0},
        },
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise ValueError(f"LessWrong GraphQL errors: {payload['errors']}")
    return payload.get("data", {}).get("comments", {}).get("results", []) or []


def _build_lesswrong_comment_tree(comments: list[dict]) -> list[dict]:
    nodes: dict[str, dict] = {}
    order_index: dict[str, int] = {}
    for idx, comment in enumerate(comments):
        comment_id = comment.get("_id")
        if not comment_id:
            continue
        order_index[comment_id] = idx
        if comment.get("deleted"):
            continue
        user = comment.get("user") or {}
        author = _format_comment_author(user.get("displayName"), user.get("username"))
        text = _normalize_comment_text(
            (comment.get("contents") or {}).get("plaintextMainText")
        )
        nodes[comment_id] = {
            "id": comment_id,
            "parent_id": comment.get("parentCommentId"),
            "author": author,
            "text": text,
            "url": comment.get("pageUrl"),
            "children": [],
            "order": idx,
        }

    roots: list[dict] = []
    for node in nodes.values():
        parent_id = node.get("parent_id")
        parent = nodes.get(parent_id) if parent_id else None
        if parent:
            parent["children"].append(node)
        else:
            roots.append(node)

    def sort_children(node: dict) -> None:
        node["children"].sort(key=lambda child: child.get("order", 0))
        for child in node["children"]:
            sort_children(child)

    roots.sort(key=lambda node: node.get("order", 0))
    for root in roots:
        sort_children(root)
    return roots


def _extract_substack_preloads(html: str) -> dict | None:
    marker = "window._preloads"
    idx = html.find(marker)
    if idx == -1:
        return None
    start = html.find('JSON.parse("', idx)
    if start == -1:
        return None
    start += len('JSON.parse("')
    chars: list[str] = []
    escaped = False
    for ch in html[start:]:
        if escaped:
            chars.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            chars.append(ch)
            continue
        if ch == '"':
            break
        chars.append(ch)
    raw = "".join(chars)
    if not raw:
        return None
    try:
        decoded = json.loads(f'"{raw}"')
        return json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse Substack preloads JSON: {exc}") from exc


def _parse_substack_slug(canonical_url: str | None) -> str | None:
    if not canonical_url:
        return None
    parsed = urlparse(canonical_url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] != "p":
        return None
    return parts[1]


def _fetch_substack_comments(base_url: str, post_id: int) -> list[dict]:
    response = requests.get(
        f"{base_url}/api/v1/post/{post_id}/comments",
        params={"token": "", "all_comments": "true", "sort": "best_first"},
        headers={"User-Agent": DEFAULT_USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("comments", []) or []


def _build_substack_comment_tree(comments: list[dict], base_url: str, slug: str) -> list[dict]:
    roots: list[dict] = []

    def build_node(comment: dict) -> dict:
        author = _format_comment_author(comment.get("name"), comment.get("handle"))
        text = _normalize_comment_text(comment.get("body"))
        comment_id = comment.get("id")
        url = (
            f"{base_url}/p/{slug}/comment/{comment_id}" if comment_id else None
        )
        children = [
            build_node(child)
            for child in (comment.get("children") or [])
            if not child.get("deleted")
        ]
        return {
            "id": comment_id,
            "author": author,
            "text": text,
            "url": url,
            "children": children,
        }

    for comment in comments:
        if comment.get("deleted") or comment.get("type") != "comment":
            continue
        roots.append(build_node(comment))
    return roots


def _render_comment_tree(nodes: list[dict]) -> tuple[str, str | None]:
    lines: list[str] = []
    count = 0
    last_url: str | None = None

    def visit(node: dict, depth: int) -> None:
        nonlocal count, last_url
        if count >= MAX_COMMENTS or depth > MAX_COMMENT_DEPTH:
            return
        text = node.get("text", "")
        if not text:
            logger.warning("Skipping empty comment {}", node.get("id"))
            return
        indent = "  " * (depth - 1)
        author = node.get("author", "[missing username]")
        lines.append(f"{indent}- **{author}**: {text}")
        count += 1
        if node.get("url"):
            last_url = node["url"]
        if depth == MAX_COMMENT_DEPTH:
            return
        for child in node.get("children", []):
            if count >= MAX_COMMENTS:
                break
            visit(child, depth + 1)

    for node in nodes:
        if count >= MAX_COMMENTS:
            break
        visit(node, 1)

    return "\n".join(lines), last_url


def _extract_comments_markdown(html: str, base_url: str | None) -> str:
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    if host.endswith("lesswrong.com"):
        post_id = _parse_lesswrong_post_id(base_url)
        if not post_id:
            raise ValueError(f"Unable to parse LessWrong post id from {base_url}")
        comments = _fetch_lesswrong_comments(post_id)
        tree = _build_lesswrong_comment_tree(comments)
        rendered, last_url = _render_comment_tree(tree)
        if not rendered:
            return ""
        section = f"## Comments\n{rendered}"
        if last_url:
            section = f"{section}\n\n[Continue thread]({last_url})"
        return section

    if "substack.com" not in host and "substackcdn.com" not in html:
        return ""

    preloads = _extract_substack_preloads(html)
    if not preloads:
        return ""
    post = preloads.get("post") or {}
    post_id = post.get("id")
    if not post_id:
        return ""
    base_url = preloads.get("base_url")
    canonical_url = preloads.get("canonicalUrl")
    slug = post.get("slug") or _parse_substack_slug(canonical_url)
    if not base_url or not slug:
        return ""
    comments = _fetch_substack_comments(base_url, post_id)
    tree = _build_substack_comment_tree(comments, base_url, slug)
    rendered, last_url = _render_comment_tree(tree)
    if not rendered:
        return ""
    section = f"## Comments\n{rendered}"
    if last_url:
        section = f"{section}\n\n[Continue thread]({last_url})"
    return section


def extract_article_markdown(
    html: str, base_url: str | None, *, include_comments: bool = False
) -> tuple[str, str]:
    prepared_html = _prepare_html_for_readability(html)
    document = Document(prepared_html)
    title = _extract_title(document)
    content_html = document.summary()
    markdown = _html_to_markdown(content_html, base_url)
    markdown = _normalize_markdown(markdown)
    if title and not markdown.lstrip().startswith("#"):
        markdown = f"# {title}\n\n{markdown}"
    if include_comments:
        comments_markdown = _extract_comments_markdown(html, base_url)
        if comments_markdown:
            markdown = f"{markdown}\n\n{comments_markdown}"
    return markdown, title
