import json
import os
import re
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import utilities
from dotenv import load_dotenv
from loguru import logger
from http.cookies import SimpleCookie

load_dotenv()

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "convertTwitter.log",
    rotation="512 KB",
    retention=5,
    enqueue=True,
    serialize=False,
)

ignored_accounts = ["memdotai", "threadreaderapp"]


class TwitterAuthError(RuntimeError):
    """Raised when Twitter authentication fails."""


class TwitterGraphQLError(RuntimeError):
    """Raised when the Twitter GraphQL API returns an error."""


_TWITTER_SESSION: Optional[requests.Session] = None

TWITTER_USER_AGENT = (
    os.getenv("TWITTER_USER_AGENT")
    or "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

TWEET_RESULT_FEATURES: Dict[str, bool] = {
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": False,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analysis_button_from_backend": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "payments_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "verified_phone_label_enabled": False,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
}

TWEET_DETAIL_FEATURES: Dict[str, bool] = {
    "rweb_video_screen_enabled": False,
    "payments_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "rweb_tipjar_consumption_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "responsive_web_grok_show_grok_translated_post": False,
    "responsive_web_grok_analysis_button_from_backend": True,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}

TWEET_DETAIL_FIELD_TOGGLES: Dict[str, bool] = {
    "withArticleRichContentState": True,
    "withArticlePlainText": False,
    "withGrokAnalyze": False,
    "withDisallowedReplyControls": False,
}


def _load_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise TwitterAuthError(
            f"Environment variable {name} is required to access Twitter's API."
        )
    return value.strip()


def _build_twitter_session() -> requests.Session:
    global _TWITTER_SESSION
    if _TWITTER_SESSION is not None:
        return _TWITTER_SESSION

    bearer = _load_required_env("TWITTER_BEARER_TOKEN")
    ct0 = _load_required_env("TWITTER_CT0_TOKEN")
    cookie_raw = _load_required_env("TWITTER_COOKIE")
    x_client_txid = os.getenv("TWITTER_XCLIENTTXID")
    x_client_uuid = os.getenv(
        "TWITTER_XCLIENTUUID", "d8c95e47-29a5-4548-9cd4-b4a0db7afd05"
    )

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {bearer}",
            "X-Csrf-Token": ct0,
            "User-Agent": TWITTER_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Referer": "https://x.com/",
            "X-Twitter-Active-User": "yes",
            "X-Twitter-Client-Language": "en",
            "X-Twitter-Auth-Type": "OAuth2Session",
        }
    )
    if x_client_txid:
        session.headers["X-Client-Transaction-Id"] = x_client_txid
    if x_client_uuid:
        session.headers["X-Client-Uuid"] = x_client_uuid

    cookie = SimpleCookie()
    cookie.load(cookie_raw)
    cookie_jar = {key: morsel.value for key, morsel in cookie.items()}
    session.cookies.update(cookie_jar)
    session.headers["Cookie"] = cookie_raw

    _TWITTER_SESSION = session
    return session


def _twitter_graphql_request(
    query_id: str,
    query_name: str,
    variables: Dict[str, Any],
    features: Dict[str, Any],
    field_toggles: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    session = _build_twitter_session()
    params = {
        "variables": json.dumps(variables, separators=(",", ":")),
        "features": json.dumps(features, separators=(",", ":")),
    }
    if field_toggles is not None:
        params["fieldToggles"] = json.dumps(field_toggles, separators=(",", ":"))

    url = f"https://x.com/i/api/graphql/{query_id}/{query_name}"
    try:
        response = session.get(url, params=params, timeout=15)
    except requests.RequestException as exc:
        logger.error(f"Twitter GraphQL request failed: {exc}")
        raise TwitterGraphQLError("Twitter GraphQL request failed") from exc

    if response.status_code in (401, 403):
        logger.error(
            "Twitter authentication failed with status %s: %.200s",
            response.status_code,
            response.text,
        )
        raise TwitterAuthError("Twitter authentication failed. Refresh credentials.")
    if response.status_code >= 400:
        logger.error(
            "Twitter GraphQL returned status %s: %.200s",
            response.status_code,
            response.text,
        )
        raise TwitterGraphQLError(
            f"Twitter GraphQL returned status {response.status_code}"
        )

    try:
        data = response.json()
    except json.JSONDecodeError as exc:
        logger.error(f"Twitter GraphQL returned invalid JSON: {exc}")
        raise TwitterGraphQLError("Twitter GraphQL returned invalid JSON") from exc

    if data.get("errors"):
        logger.error("Twitter GraphQL errors: %s", data["errors"])
        raise TwitterGraphQLError("Twitter GraphQL returned errors")

    return data


def _coerce_tweet(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(result, dict):
        return None
    typename = result.get("__typename")
    if typename == "Tweet":
        return result
    if typename == "TweetWithVisibilityResults":
        return _coerce_tweet(result.get("tweet"))
    return None


def _get_user_result(tweet: Dict[str, Any]) -> Dict[str, Any]:
    core = tweet.get("core", {})
    user_results = core.get("user_results", {})
    result = user_results.get("result")
    return result if isinstance(result, dict) else {}


def _get_user_screen_name(tweet: Dict[str, Any]) -> Optional[str]:
    user = _get_user_result(tweet)
    legacy = user.get("legacy")
    if isinstance(legacy, dict) and legacy.get("screen_name"):
        return legacy["screen_name"]
    core = user.get("core")
    if isinstance(core, dict) and core.get("screen_name"):
        return core["screen_name"]
    if isinstance(user.get("screen_name"), str):
        return user["screen_name"]
    return None


def _extract_tweets_from_structure(node: Any, visited: Optional[set] = None) -> List[Dict[str, Any]]:
    if visited is None:
        visited = set()
    tweets: List[Dict[str, Any]] = []
    if not isinstance(node, dict):
        return tweets
    node_id = id(node)
    if node_id in visited:
        return tweets
    visited.add(node_id)

    tweet_results = node.get("tweet_results")
    if isinstance(tweet_results, dict):
        tweet = _coerce_tweet(tweet_results.get("result"))
        if tweet:
            tweets.append(tweet)

    # Nested data
    if "tweet" in node and isinstance(node["tweet"], dict):
        tweets.extend(_extract_tweets_from_structure(node["tweet"], visited))

    for key in ("itemContent", "content", "item"):
        if key in node and isinstance(node[key], dict):
            tweets.extend(_extract_tweets_from_structure(node[key], visited))

    if "items" in node and isinstance(node["items"], list):
        for item in node["items"]:
            tweets.extend(_extract_tweets_from_structure(item, visited))

    return tweets


def _parse_tweet_detail_response(
    data: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    instructions = (
        data.get("data", {})
        .get("threaded_conversation_with_injections_v2", {})
        .get("instructions", [])
    )
    tweets: List[Dict[str, Any]] = []
    cursors: List[tuple[str, str]] = []
    for instruction in instructions:
        entries = instruction.get("entries")
        if not entries and instruction.get("entry"):
            entries = [instruction["entry"]]
        if not entries:
            continue
        for entry in entries:
            content = entry.get("content") or {}
            entry_id = entry.get("entryId") or entry.get("entry_id") or ""
            tweets.extend(_extract_tweets_from_structure(content))
            cursor_value = content.get("value")
            if cursor_value:
                cursor_type = content.get("cursorType")
                entry_id_lower = entry_id.lower()
                if cursor_type == "Bottom" or "cursor-bottom" in entry_id_lower:
                    cursors.append(("bottom", cursor_value))
                elif cursor_type == "Top" or "cursor-top" in entry_id_lower:
                    cursors.append(("top", cursor_value))
    return tweets, cursors


def fetch_tweet_by_rest_id(tweet_id: str) -> Optional[Dict[str, Any]]:
    data = _twitter_graphql_request(
        "f2sagi1jweVHFkTUIHzmMQ",
        "TweetResultByRestId",
        {
            "tweetId": tweet_id,
            "withCommunity": False,
            "includePromotedContent": False,
            "withVoice": False,
        },
        TWEET_RESULT_FEATURES,
    )
    result = (
        data.get("data", {})
        .get("tweetResult", {})
        .get("result")
    )
    tweet = _coerce_tweet(result)
    if tweet:
        logger.debug(f"Fetched primary tweet {tweet_id} via TweetResultByRestId")
    return tweet


def fetch_tweet_detail(tweet_id: str, cursor: Optional[str] = None) -> Dict[str, Any]:
    variables = {
        "focalTweetId": tweet_id,
        "with_rux_injections": False,
        "rankingMode": "Relevance",
        "includePromotedContent": False,
        "withCommunity": False,
        "withQuickPromoteEligibilityTweetFields": False,
        "withBirdwatchNotes": True,
        "withVoice": False,
        "cursor": cursor,
    }
    return _twitter_graphql_request(
        "R9IzzyzQBV87-DOWpcvDmw",
        "TweetDetail",
        variables,
        TWEET_DETAIL_FEATURES,
        TWEET_DETAIL_FIELD_TOGGLES,
    )


def identifyLowQualityTweet(tweet, opUsername, highQuality, allTweets):
    screen_name = _get_user_screen_name(tweet)
    op_username_lower = (opUsername or "").lower()
    image_url = ""
    if (
        "extended_entities" in tweet["legacy"]
        and "media" in tweet["legacy"]["extended_entities"]
    ):
        media = tweet["legacy"]["extended_entities"]["media"]
        if len(media) > 0 and "media_url_https" in media[0]:
            image_url = media[0]["media_url_https"]
    tweet["legacy"]["full_text"] = tweet["legacy"]["full_text"].replace(
        image_url, ""
    )  ##so images not counted as links
    noReplies = (
        len(
            [
                twt
                for twt in allTweets
                if "in_reply_to_status_id_str" in twt["legacy"]
                and twt["legacy"]["in_reply_to_status_id_str"] == tweet["rest_id"]
            ]
        )
        == 0
    )
    isReplyToOP = (
        "in_reply_to_screen_name" in tweet["legacy"]
        and tweet["legacy"]["in_reply_to_screen_name"].lower() == op_username_lower
    )
    # fewLikes = tweet["legacy"]["favorite_count"] < 3
    manyWords = len(tweet["legacy"]["full_text"].split(" ")) > 7
    byOp = screen_name and screen_name.lower() == op_username_lower
    noLinks = (
        "https://" not in tweet["legacy"]["full_text"]
        or "full_text" not in tweet["legacy"]
    )
    lowQuality = (not manyWords) and noReplies and (not byOp) and noLinks
    lowQualReplyToOp = isReplyToOP and lowQuality
    lowQualReply = lowQuality
    if (lowQualReplyToOp or lowQualReply) and highQuality:
        logger.debug(
            f"Skipping tweet {tweet['rest_id']} due to low quality "
            f"(to_op={lowQualReplyToOp}, low_reply={lowQualReply})"
        )
        return True
    return False


def getReplies(
    conversation_id: str,
    onlyOp: bool = False,
    max_pages: int = 25,
) -> List[Dict[str, Any]]:
    logger.info(f"Fetching conversation for {conversation_id} (onlyOp={onlyOp})")

    tweets_by_id: Dict[str, Dict[str, Any]] = {}
    cursor_queue: List[Optional[str]] = [None]
    seen_cursors: set = set()
    pages_processed = 0

    while cursor_queue and pages_processed < max_pages:
        cursor = cursor_queue.pop(0)
        if cursor in seen_cursors:
            continue
        if cursor is not None:
            seen_cursors.add(cursor)
        pages_processed += 1

        detail_data = fetch_tweet_detail(conversation_id, cursor)
        tweets, cursors = _parse_tweet_detail_response(detail_data)
        new_count = 0

        for tweet in tweets:
            if not tweet:
                continue
            rest_id = tweet.get("rest_id")
            legacy = tweet.get("legacy")
            core = tweet.get("core", {})
            if not rest_id or rest_id in tweets_by_id or not legacy or not core:
                continue
            screen_name = _get_user_screen_name(tweet)
            if not screen_name:
                continue
            tweets_by_id[rest_id] = tweet
            new_count += 1

        for direction, cursor_value in cursors:
            if cursor_value and cursor_value not in seen_cursors:
                cursor_queue.append(cursor_value)

        if new_count == 0 and not cursor_queue:
            break

    if conversation_id not in tweets_by_id:
        main_tweet = fetch_tweet_by_rest_id(conversation_id)
        if main_tweet:
            tweets_by_id[conversation_id] = main_tweet

    if not tweets_by_id:
        raise TwitterGraphQLError(
            f"Twitter returned no conversation data for tweet {conversation_id}"
        )

    tweets: List[Dict[str, Any]] = list(tweets_by_id.values())
    tweets.sort(
        key=lambda tweet: (
            0 if tweet.get("rest_id") == conversation_id else 1,
            tweet.get("rest_id"),
        )
    )

    if onlyOp and tweets:
        op_username = _get_user_screen_name(tweets[0])
        if not op_username:
            return []
        op_username = op_username.lower().strip()
        op_tweets = [
            tweet
            for tweet in tweets
            if (
                (_get_user_screen_name(tweet) or "").lower().strip()
                == op_username
            )
        ]
        logger.info(
            f"Filtered thread to {len(op_tweets)} tweet(s) from OP {op_username}"
        )
        return op_tweets

    return tweets


def parseReplies(rawReplies, opUsername, highQuality):
    replies_dict = {}
    for reply in rawReplies:
        screen_name = _get_user_screen_name(reply)
        if not screen_name:
            continue
        if screen_name.lower() in ignored_accounts:
            continue
        try:
            if identifyLowQualityTweet(reply, opUsername, highQuality, rawReplies):
                continue
        except Exception:
            logger.exception("Failed to process reply while filtering quality")
            try:
                logger.debug(json.dumps(reply)[:1000])
            except Exception:
                logger.debug(f"Reply (repr): {repr(reply)}")
            continue

        onlyTagsSoFar = True
        contentWords = []
        full_text = reply["legacy"].get("full_text")
        if "note_tweet" in reply:
            full_text = (
                reply.get("note_tweet")
                .get("note_tweet_results")
                .get("result")
                .get("text")
            )
        if not full_text:
            continue

        for word in full_text.split(" "):
            if "@" in word:
                if onlyTagsSoFar:
                    continue
            else:
                onlyTagsSoFar = False
            contentWords.append(word)

        text = " ".join(contentWords)
        text = (
            "{"
            + screen_name
            + "} "
            + text
        )

        # Handle quoted tweets
        if (
            "quoted_status_result" in reply
            and "result" in reply["quoted_status_result"]
        ):
            quoted_tweet = reply["quoted_status_result"]["result"]
            if "legacy" in quoted_tweet and "full_text" in quoted_tweet["legacy"]:
                text += " {Quoted tweet} " + quoted_tweet["legacy"]["full_text"]

        # Handle retweets (if present in the new format)
        if "retweeted_status_result" in reply:
            retweeted_tweet = reply["retweeted_status_result"]["result"]
            if "legacy" in retweeted_tweet and "full_text" in retweeted_tweet["legacy"]:
                text += " {RT'd tweet} " + retweeted_tweet["legacy"]["full_text"]

        tweetUrl = (
            "https://twitter.com/"
            + screen_name
            + "/status/"
            + str(reply["rest_id"])
        )

        image_url = ""
        if (
            "extended_entities" in reply["legacy"]
            and "media" in reply["legacy"]["extended_entities"]
        ):
            media = reply["legacy"]["extended_entities"]["media"]
            if len(media) > 0 and "media_url_https" in media[0]:
                image_url = media[0]["media_url_https"]

        if reply["rest_id"] in replies_dict:
            replies_dict[reply["rest_id"]]["text"] = text
            replies_dict[reply["rest_id"]]["link"] = tweetUrl
            replies_dict[reply["rest_id"]]["image_url"] = image_url
            replies_dict[reply["rest_id"]]["likes"] = reply["legacy"].get(
                "favorite_count", 0
            )
            replies_dict[reply["rest_id"]]["retweets"] = reply["legacy"].get(
                "retweet_count", 0
            )
        else:
            replies_dict[reply["rest_id"]] = {
                "text": text,
                "children": [],
                "link": tweetUrl,
                "image_url": image_url,
                "likes": reply["legacy"].get("favorite_count", 0),
                "retweets": reply["legacy"].get("retweet_count", 0),
            }

        if "in_reply_to_status_id_str" in reply["legacy"]:
            parent_id = reply["legacy"]["in_reply_to_status_id_str"]
            if parent_id in replies_dict:
                replies_dict[parent_id]["children"].append(reply["rest_id"])
                replies_dict[parent_id]["children"] = list(
                    set(replies_dict[parent_id]["children"])
                )
            else:
                replies_dict[parent_id] = {
                    "text": "",
                    "children": [reply["rest_id"]],
                    "link": "",
                    "image_url": "",
                    "likes": 0,
                    "retweets": 0,
                }

    # Sort tweets by likes + retweets
    for tweet_id in replies_dict:
        replies_dict[tweet_id]["children"].sort(
            key=lambda x: replies_dict[x]["likes"],
            reverse=True,
        )

    return replies_dict


def get_longest_chain_length(tweet_id, json_data, cache=None):
    """Calculate the length of the longest reply chain starting from this tweet."""
    if cache is None:
        cache = {}

    if tweet_id in cache:
        return cache[tweet_id]

    if tweet_id not in json_data:
        return 0

    children = json_data[tweet_id]["children"]
    if not children:
        return 0

    max_child_length = max(
        get_longest_chain_length(child, json_data, cache) for child in children
    )
    result = 1 + max_child_length
    cache[tweet_id] = result
    return result


def json_to_html(json_data, topTweet, op_username):
    def convert_https_to_md(string):
        pattern = r"https:\/\/\S+"
        links = re.findall(pattern, string)
        for link in links:
            string = string.replace(link, f'<a href="{link}">{link}</a>')
        return string

    def addTweetMdLink(tweet, link, isFirstTweet):
        pattern = r"\{.*?\}"
        username = re.findall(pattern, tweet)[0]
        destString = f'<a href="{link}">{username}</a>'
        isOp = username == "{" + op_username + "}"
        if isOp and (not isFirstTweet):
            destString = '<a href="' + link + '">{OP}</a>'
        string = tweet.replace(username, destString)
        return string

    def cleanText(text, endDetailsStr):
        return (
            text.replace(endDetailsStr, "")
            .replace("</ul>", "")
            .replace(" ", "")
            .replace("\n", "")
        )

    def convert_to_html(tweet_id, level):
        outStr = ""
        indent = "  " * level
        tweet = json_data[tweet_id]
        tweetText = convert_https_to_md(tweet["text"])
        tweetText = addTweetMdLink(tweetText, tweet["link"], level == 0).replace(
            "\n", "<br>"
        )

        if tweet["image_url"]:
            if "mp4" in tweet["image_url"]:
                tweetText += '<a href="' + tweet["image_url"] + '">[Video]</a>'
            else:
                tweetText += f'<br><img src="{tweet["image_url"]}">'

        outStr = (
            f"{indent}<br><details open><summary>{level+1}. {tweetText}</summary><br>\n"
        )

        # Sort children by their longest reply chain length
        # sorted_children = sorted(
        #     tweet["children"],
        #     key=lambda x: get_longest_chain_length(x, json_data),
        #     reverse=True
        # ) ###this is 100% depth first. a bit to extreme imo, because it makes other replies less contexualised. maybe some middle ground is optimal.
        outStr += f"{indent}<ul>\n"
        sorted_children = tweet["children"]
        for childId in sorted_children:
            outStr += convert_to_html(childId, level + 1)
        outStr += f"{indent}</ul>\n"
        endsWithNotReply = False
        notReplyStr = "<br><p>END THREAD</p>\n"
        endDetailsStr = "</details>\n"
        cleanedText = cleanText(outStr, endDetailsStr)
        cleanedNotReplyStr = cleanText(notReplyStr, endDetailsStr)
        if cleanedText.endswith(
            cleanedNotReplyStr
        ):  ## prevent duplication of this element due to > 1 consecutive de-indents
            endsWithNotReply = True
        outStr += f"{indent}{endDetailsStr}"
        if not endsWithNotReply:
            outStr += f"{indent}{notReplyStr}"
        return outStr

    outStr = convert_to_html(topTweet, 0)
    return outStr


def convertTwitter(url, forceRefresh):
    onlyOp = False
    highQuality = False
    if "#convo" in url:
        pass
    elif "#thread" in url:
        onlyOp = True
    elif "#hq" in url:
        highQuality = True
    else:
        return url
    tweet_id = url.split("/")[-1].strip(".html").split("#")[0].split("?")[0]
    gistUrl = utilities.getGistUrl(tweet_id)
    if gistUrl and not forceRefresh:
        return gistUrl
    rawReplies = getReplies(tweet_id, onlyOp)
    # pickle.dump(rawReplies, open("tmp/rawReplies.pickle", "wb"))
    # rawReplies = pickle.load(open("tmp/rawReplies.pickle", "rb"))

    op_tweet = next(
        (
            tweet
            for tweet in rawReplies
            if tweet.get("rest_id") == tweet_id and _get_user_screen_name(tweet)
        ),
        None,
    )
    if op_tweet is None:
        op_tweet = next(
            (tweet for tweet in rawReplies if _get_user_screen_name(tweet)),
            None,
        )
    if op_tweet is None:
        raise TwitterGraphQLError(
            f"Could not locate operator tweet for conversation {tweet_id}"
        )
    op_username = _get_user_screen_name(op_tweet)
    if not op_username:
        raise TwitterGraphQLError(
            f"Operator tweet missing screen_name for conversation {tweet_id}"
        )
    replies = parseReplies(rawReplies, op_username, highQuality)
    html = f'<a href="{url}">Original</a><br><br>' + json_to_html(
        replies, tweet_id, op_username
    )
    title = replies[tweet_id]["text"][:50]
    urlToOpen = utilities.writeGist(html, "TWTR: " + title, tweet_id)
    return urlToOpen


if __name__ == "__main__":
    print(
        convertTwitter(
            "https://x.com/metaproph3t/status/1863281120927760692###convo",
            forceRefresh=True,
        )
    )
    # print(json.dumps(get_tweet_by_id("1858629520871375295"), indent=4))
