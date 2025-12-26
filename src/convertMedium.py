import article_utils
from convertArticle import convertArticle


def convertMedium(url: str, forceRefresh: bool):
    cleaned_url = article_utils.normalize_url(url)
    cleaned_url = article_utils.strip_tracking_params(
        cleaned_url, drop_params={"source"}, keep_params={"sk"}
    )
    return convertArticle(
        cleaned_url,
        forceRefresh,
        prefix="MED",
        source_label="Medium article",
    )
