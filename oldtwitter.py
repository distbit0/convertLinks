
import traceback
import urllib
import re
import time
import pickle
import json
from datetime import datetime, timedelta
import utilities
import re
from dotenv import load_dotenv
import os
import requests
import xRequests
import subprocess
import shlex


load_dotenv()

ignored_accounts = ["memdotai", "threadreaderapp"]

# Functions to modify tweet and replies requests based on IDs

def _sub(pattern: str, repl: str, text: str) -> str:
    """
    Small helper: regex-sub everywhere in *text*.
    The patterns we use are look-behind / look-ahead anchored, so they never
    disturb the surrounding JSON-or-URL noise.
    """
    return re.sub(pattern, repl, text, flags=re.DOTALL)


def modify_tweet_request(request_str: str, tweet_id: str) -> str:
    """
    Replace every place where the focal tweet ID is embedded:
      • the GraphQL variables block (focalTweetId) – URL-encoded JSON
      • the Referer header               …/status/<id>
    """
    # 1) focalTweetId inside the variables query-param
    out = _sub(r'(?<=focalTweetId%22%3A%22)\d+(?=%22)', tweet_id, request_str)
    # 2) …/status/<id> in the Referer header
    out = _sub(r'(?<=/status/)\d+', tweet_id, out)
    return out


def modify_replies_request(request_str, conversation_id, cursor=None, from_username=None):
    # 1. locate and decode the variables= blob
    m = re.search(r'variables=([^&\'\s]+)', request_str)
    if not m:
        raise ValueError("can't find variables=")
    var_enc = m.group(1)
    var_obj = json.loads(urllib.parse.unquote(var_enc))

    # 2. mutate the dict
    var_obj["rawQuery"] = f"conversation_id:{conversation_id}" + (
        f" from:{from_username}" if from_username else ""
    )
    if cursor is None:
        var_obj.pop("cursor", None)
    else:
        var_obj["cursor"] = cursor

    # 3. re-encode and re-insert
    new_enc = urllib.parse.quote(json.dumps(var_obj, separators=(',', ':')), safe='')
    request_str = request_str.replace(var_enc, new_enc, 1)

    # 4. also update the Referer header’s query string
    ref_q = urllib.parse.quote(var_obj["rawQuery"], safe='')
    request_str = re.sub(r'(?<=\?q=)[^&\'\s]+', ref_q, request_str)

    return request_str




def get_tweet_by_id(tweet_id):
    curlString = modify_tweet_request(xRequests.tweetRequest, tweet_id)
    
    try:
        # Execute curl command directly using subprocess
        args = shlex.split(curlString)   # turns the full command into a list
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        data = json.loads(result.stdout)

        try:
            entries = data["data"]["threaded_conversation_with_injections_v2"][
                "instructions"
            ][0]["entries"]
        except (KeyError, IndexError):
            return None

        # Helper function to extract tweet from different response structures
        def get_tweet_result(content):
            if not content.get("itemContent"):
                return None

            tweet_results = content["itemContent"].get("tweet_results", {})
            if not tweet_results:
                return None

            result = tweet_results.get("result")
            if not result:
                return None

            # Handle both direct tweets and tweets with visibility results
            if result["__typename"] == "TweetWithVisibilityResults":
                return result.get("tweet")
            return result if result["__typename"] == "Tweet" else None

        # Iterate through entries to find matching tweet
        for entry in entries:
            if "content" in entry:
                # Handle single tweets
                if entry["content"]["entryType"] == "TimelineTimelineItem":
                    tweet = get_tweet_result(entry["content"])
                    if tweet and tweet.get("rest_id") == tweet_id:
                        return tweet

                # Handle conversation threads
                elif entry["content"]["entryType"] == "TimelineTimelineModule":
                    for item in entry["content"].get("items", []):
                        if "item" in item:
                            tweet = get_tweet_result(item["item"])
                            if tweet and tweet.get("rest_id") == tweet_id:
                                return tweet

        return None

    except requests.RequestException as e:
        print(f"Error making request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print("Output: ", result.stdout)
        print("Curl command: ", curlString)
        return None


def identifyLowQualityTweet(tweet, opUsername, highQuality, allTweets):
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
        and tweet["legacy"]["in_reply_to_screen_name"].lower() == opUsername.lower()
    )
    # fewLikes = tweet["legacy"]["favorite_count"] < 3
    manyWords = len(tweet["legacy"]["full_text"].split(" ")) > 7
    byOp = (
        tweet["core"]["user_results"]["result"]["legacy"]["screen_name"].lower()
        == opUsername.lower()
    )
    noLinks = (
        "https://" not in tweet["legacy"]["full_text"]
        or "full_text" not in tweet["legacy"]
    )
    lowQuality = (not manyWords) and noReplies and (not byOp) and noLinks
    lowQualReplyToOp = isReplyToOP and lowQuality
    lowQualReply = lowQuality
    if (lowQualReplyToOp or lowQualReply) and highQuality:
        print(
            f"skipping tweet: {tweet['legacy']['full_text'][:60]} |||| https://x.com/{tweet['core']['user_results']['result']['legacy']['screen_name']}/status/{tweet['rest_id']},  due to: lowQualReplyToOp: {lowQualReplyToOp}, lowQualReply: {lowQualReply}\n"
        )
        return True
    return False


def getReplies(
    conversation_id, onlyOp=False, max_retries=10, retry_delay=4
):  # 180 seconds = 3 minutes
    print(conversation_id)
    mainTweet = get_tweet_by_id(conversation_id)
    if not mainTweet:
        print(f"Main tweet not found: {conversation_id}")
        return []
    opUsername = mainTweet["core"]["user_results"]["result"]["legacy"]["screen_name"]
    # elif highQuality:
    #     query = f"conversation_id:{conversation_id} min_faves:2" # this is actually bad as a single reply in a convo with <2 likes will cut off rest of convo

    all_tweets = [mainTweet]
    cursor = None

    attempts = 0
    while True:
        curlString = modify_replies_request(
            xRequests.repliesRequest, conversation_id, cursor, from_username=onlyOp and opUsername
        )
        
        # Make the request using curl directly
        try:
            # Execute curl command directly using subprocess
            args = shlex.split(curlString)   # turns the full command into a list
            result = subprocess.run(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Check for process execution errors
            if result.returncode != 0:
                if attempts > max_retries:
                    print(f"Maximum retries reached ({max_retries})")
                    print(f"Last error: Curl command failed: {result.stderr}")
                    return []
                else:
                    print(f"Curl command failed: {result.stderr}. Retrying in {retry_delay} seconds")
                    time.sleep(retry_delay)
                    attempts += 1
                    continue
                    
            # Parse the JSON response from curl output
            try:
                response_data = json.loads(result.stdout)
                
                # Check response for potential rate limiting indicators in the parsed data
                # Note: We need to check the response content since we won't have status codes directly
                if "errors" in response_data and any("rate limit" in str(error).lower() for error in response_data["errors"]):
                    if attempts > max_retries:
                        print(f"Maximum retries reached ({max_retries})")
                        print(f"Last error: Rate limit exceeded")
                        return []
                    else:
                        sleep_time = retry_delay + (30 * attempts)
                        print(f"Rate limit hit. Waiting {sleep_time} seconds")
                        time.sleep(sleep_time)
                        attempts += 1
                        continue
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON response: {e}")
                print("Output: ", result.stdout)
                print("Curl command: ", curlString)
                if attempts > max_retries:
                    return []
                else:
                    print(f"Retrying in 1 seconds")
                    time.sleep(1)
                    continue
            else:
                attempts = 0
                
            instructions = (
                response_data.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )
            if not instructions:
                print("No instructions found in response.")
                break

            bottom_cursor = None
            newtweets = 0
            for instruction in instructions:
                entries = instruction.get("entries", []) or [instruction.get("entry", {})]
                for entry in entries:
                    content = entry.get("content", {})
                    item_content = content.get("itemContent", {})
                    tweet = item_content.get("tweet_results", {}).get("result")
                    if (
                        tweet
                        and "rest_id" in tweet
                        and tweet["rest_id"]
                        not in [tweet["rest_id"] for tweet in all_tweets]
                    ):
                        all_tweets.append(tweet)
                        newtweets += 1
                    if "cursor-bottom" in entry.get(
                        "entryId", ""
                    ) or "cursor-bottom" in entry.get("entry_id_to_replace", ""):
                        bottom_cursor = entry.get("content", {}).get("value")
            if bottom_cursor and newtweets > 0:
                cursor = bottom_cursor
                print(f"Fetching next page with cursor: {cursor}, newtweets: {newtweets}")
                time.sleep(1)  # Respect rate limits
            elif newtweets == 0:
                print("no new tweets. New cursor:", cursor)
                break
            else:
                print(f"no new cursor, {newtweets} new tweets")
                break
        except Exception as e:
            print(f"Unexpected error: {e}")
            if attempts > max_retries:
                print(f"Maximum retries reached ({max_retries})")
                return []
            else:
                print(f"Retrying in {retry_delay} seconds")
                time.sleep(retry_delay)
                attempts += 1
                continue
        else:
            attempts = 0

    return all_tweets


def parseReplies(rawReplies, opUsername, highQuality):
    if not rawReplies:
        return {}
    replies_dict = {}
    for reply in rawReplies:
        if (
            reply["core"]["user_results"]["result"]["legacy"]["screen_name"].lower()
            in ignored_accounts
        ):
            continue
        try:
            if identifyLowQualityTweet(reply, opUsername, highQuality, rawReplies):
                continue
        except:
            print(traceback.format_exc())
            print(reply)
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
            + reply["core"]["user_results"]["result"]["legacy"]["screen_name"]
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
            + reply["core"]["user_results"]["result"]["legacy"]["screen_name"]
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
    if not rawReplies:
        return url
    # pickle.dump(rawReplies, open("tmp/rawReplies.pickle", "wb"))
    # rawReplies = pickle.load(open("tmp/rawReplies.pickle", "rb"))
    op_username = rawReplies[0]["core"]["user_results"]["result"]["legacy"][
        "screen_name"
    ]
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
