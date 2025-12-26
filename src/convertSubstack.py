import article_utils
from convertArticle import convertArticle


def convertSubstack(url: str, forceRefresh: bool):
    cleaned_url = article_utils.normalize_url(url)
    cleaned_url = article_utils.strip_tracking_params(cleaned_url)
    return convertArticle(
        cleaned_url,
        forceRefresh,
        prefix="SUB",
        source_label="Substack article",
    )
