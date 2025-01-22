import traceback
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


load_dotenv()

csrf_token = os.getenv("TWITTER_CT0_TOKEN")
bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
xClientTxid = os.getenv("TWITTER_XCLIENTTXID")
cookie = os.getenv("TWITTER_COOKIE")

ignored_accounts = ["memdotai", "threadreaderapp"]

features = '{"profile_label_improvements_pcf_account_label_enabled":false,"rweb_tipjar_consumption_enabled":true,"responsive_web_graphql_exclude_directive_enabled":true,"verified_phone_label_enabled":false,"creator_subscriptions_tweet_preview_api_enabled":true,"responsive_web_graphql_timeline_navigation_enabled":true,"responsive_web_graphql_skip_user_profile_image_extensions_enabled":false,"communities_web_enable_tweet_community_results_fetch":true,"c9s_tweet_anatomy_moderator_badge_enabled":true,"articles_preview_enabled":true,"responsive_web_edit_tweet_api_enabled":true,"graphql_is_translatable_rweb_tweet_is_translatable_enabled":true,"view_counts_everywhere_api_enabled":true,"longform_notetweets_consumption_enabled":true,"responsive_web_twitter_article_tweet_consumption_enabled":true,"tweet_awards_web_tipping_enabled":false,"creator_subscriptions_quote_tweet_preview_enabled":false,"freedom_of_speech_not_reach_fetch_enabled":true,"standardized_nudges_misinfo":true,"tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled":true,"rweb_video_timestamps_enabled":true,"longform_notetweets_rich_text_read_enabled":true,"longform_notetweets_inline_media_enabled":true,"responsive_web_enhance_cards_enabled":false}'



headers = {
    'accept': '*/*',
    'accept-language': 'en-GB,en;q=0.9',
    'authorization': f'Bearer {bearer_token}',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'cookie': cookie,
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://x.com/search?q=conversation_id%3A1862299845710757980+min_faves%3A2&src=typed_query&f=live',
    'sec-ch-ua': '"Brave";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'sec-gpc': '1',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'x-client-transaction-id': xClientTxid,
    'x-client-uuid': 'd8c95e47-29a5-4548-9cd4-b4a0db7afd05',
    'x-csrf-token': csrf_token,
    'x-twitter-active-user': 'yes',
    'x-twitter-auth-type': 'OAuth2Session',
    'x-twitter-client-language': 'en'
}

def get_tweet_by_id(tweet_id):
    base_url = "https://x.com/i/api/graphql/nBS-WpgA6ZG0CyNHD517JQ/TweetDetail"
    
    # Request parameters
    variables = {
        "focalTweetId": tweet_id,
        "with_rux_injections": True,
        "rankingMode": "Relevance",
        "includePromotedContent": True,
        "withCommunity": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withBirdwatchNotes": True,
        "withVoice": True
    }
    
    field_toggles = {
        "withArticleRichContentState": True,
        "withArticlePlainText": False,
        "withGrokAnalyze": False,
        "withDisallowedReplyControls": False
    }

    # URL parameters
    params = {
        'variables': json.dumps(variables),
        'features': features,
        'fieldToggles': json.dumps(field_toggles)
    }
    
    try:
        # Make the request
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()  # Raise exception for bad status codes
        response_data = response.json()

        try:
            entries = response_data['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']
        except (KeyError, IndexError):
            return None

        # Helper function to extract tweet from different response structures
        def get_tweet_result(content):
            if not content.get('itemContent'):
                return None
            
            tweet_results = content['itemContent'].get('tweet_results', {})
            if not tweet_results:
                return None
                
            result = tweet_results.get('result')
            if not result:
                return None
                
            # Handle both direct tweets and tweets with visibility results
            if result['__typename'] == 'TweetWithVisibilityResults':
                return result.get('tweet')
            return result if result['__typename'] == 'Tweet' else None

        # Iterate through entries to find matching tweet
        for entry in entries:
            if 'content' in entry:
                # Handle single tweets
                if entry['content']['entryType'] == 'TimelineTimelineItem':
                    tweet = get_tweet_result(entry['content'])
                    if tweet and tweet.get('rest_id') == tweet_id:
                        return tweet
                        
                # Handle conversation threads
                elif entry['content']['entryType'] == 'TimelineTimelineModule':
                    for item in entry['content'].get('items', []):
                        if 'item' in item:
                            tweet = get_tweet_result(item['item'])
                            if tweet and tweet.get('rest_id') == tweet_id:
                                return tweet

        return None

    except requests.RequestException as e:
        print(f"Error making request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None


def identifyLowQualityTweet(tweet, opUsername, highQuality, allTweets):
    image_url = ""
    if "extended_entities" in tweet["legacy"] and "media" in tweet["legacy"]["extended_entities"]:
        media = tweet["legacy"]["extended_entities"]["media"]
        if len(media) > 0 and "media_url_https" in media[0]:
            image_url = media[0]["media_url_https"]
    tweet["legacy"]["full_text"] = tweet["legacy"]["full_text"].replace(image_url, "") ##so images not counted as links
    noReplies = len([twt for twt in allTweets if "in_reply_to_status_id_str" in twt["legacy"] and twt["legacy"]["in_reply_to_status_id_str"] == tweet["rest_id"]]) == 0
    isReplyToOP = "in_reply_to_screen_name" in tweet["legacy"] and tweet["legacy"]["in_reply_to_screen_name"].lower() == opUsername.lower()
    # fewLikes = tweet["legacy"]["favorite_count"] < 3
    manyWords = len(tweet["legacy"]["full_text"].split(" ")) > 7
    byOp = tweet["core"]["user_results"]["result"]["legacy"]["screen_name"].lower() == opUsername.lower()
    noLinks = "https://" not in tweet["legacy"]["full_text"] or "full_text" not in tweet["legacy"]
    lowQuality = (not manyWords) and noReplies and (not byOp) and noLinks
    lowQualReplyToOp = isReplyToOP and lowQuality
    lowQualReply = lowQuality
    if (lowQualReplyToOp or lowQualReply) and highQuality:
        print(f"skipping tweet: {tweet['legacy']['full_text'][:60]} |||| https://x.com/{tweet['core']['user_results']['result']['legacy']['screen_name']}/status/{tweet['rest_id']},  due to: lowQualReplyToOp: {lowQualReplyToOp}, lowQualReply: {lowQualReply}\n")
        return True
    return False


def getReplies(conversation_id, onlyOp=False, max_retries=10, retry_delay=180):  # 180 seconds = 3 minutes
    print(conversation_id)
    mainTweet = get_tweet_by_id(conversation_id)
    opUsername = mainTweet["core"]["user_results"]["result"]["legacy"]["screen_name"]
    if not mainTweet:
        print("Main tweet not found.")
        return None
    if onlyOp:
        query = f"conversation_id:{conversation_id} from:{opUsername}"
    # elif highQuality:
    #     query = f"conversation_id:{conversation_id} min_faves:2" # this is actually bad as a single reply in a convo with <2 likes will cut off rest of convo
    else:
        query = f"conversation_id:{conversation_id}"
    
    url = 'https://x.com/i/api/graphql/MJuDXJXZ8bB--c9Ujhy-0g/SearchTimeline'
    print("query", query)

    all_tweets = [mainTweet]
    cursor = None

    while True:
        variables = {
            "rawQuery": query,
            "count": 20,
            "querySource": "typed_query",
            "product": "Latest",
        }
        if cursor:
            variables["cursor"] = cursor

        params = {
            'variables': json.dumps(variables),
            'features': features
        }

        retry_count = 0
        while retry_count < max_retries:
            try:
                response = requests.get(url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                break  # If successful, break out of the retry loop
            except (requests.RequestException, json.JSONDecodeError) as e:
                retry_count += 1
                if retry_count == max_retries:
                    print(f"Failed after {max_retries} attempts: {e}")
                    return all_tweets
                print(f"Attempt {retry_count} failed: {e}")
                print(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)

        instructions = (
            data.get('data', {})
                .get('search_by_raw_query', {})
                .get('search_timeline', {})
                .get('timeline', {})
                .get('instructions', [])
        )
        if not instructions:
            print("No instructions found in response.")
            break

        bottom_cursor = None
        newtweets = 0
        for instruction in instructions:
            entries = instruction.get('entries', []) or [instruction.get('entry', {})]
            for entry in entries:
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                tweet = item_content.get('tweet_results', {}).get('result')
                if tweet and "rest_id" in tweet and tweet["rest_id"] not in [tweet["rest_id"] for tweet in all_tweets]:
                    all_tweets.append(tweet)
                    newtweets += 1 
                if "cursor-bottom" in entry.get('entryId', "") or "cursor-bottom" in entry.get("entry_id_to_replace", ""):
                    bottom_cursor = entry.get('content', {}).get('value')
        if bottom_cursor and newtweets > 0:
            cursor = bottom_cursor
            print(f"Fetching next page with cursor: {cursor}, newtweets: {newtweets}")
            time.sleep(1)  # Respect rate limits
        elif newtweets == 0:
            print("no new tweets. New cursor:", cursor)
            # with open("tmp/noNewTweets.json", "w") as f:
            #     f.write(json.dumps(data, indent=4))
            break
        else:
            print(f"no new cursor, {newtweets} new tweets")
            break
    
    return all_tweets


def parseReplies(rawReplies, opUsername, highQuality):
    replies_dict = {}
    for reply in rawReplies:
        if reply["core"]["user_results"]["result"]["legacy"]["screen_name"].lower() in ignored_accounts:
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
            full_text = reply.get("note_tweet").get("note_tweet_results").get("result").get("text")
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
        text = "{" + reply["core"]["user_results"]["result"]["legacy"]["screen_name"] + "} " + text
        
        # Handle quoted tweets
        if "quoted_status_result" in reply and "result" in reply["quoted_status_result"]:
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
        if "extended_entities" in reply["legacy"] and "media" in reply["legacy"]["extended_entities"]:
            media = reply["legacy"]["extended_entities"]["media"]
            if len(media) > 0 and "media_url_https" in media[0]:
                image_url = media[0]["media_url_https"]

        if reply["rest_id"] in replies_dict:
            replies_dict[reply["rest_id"]]["text"] = text
            replies_dict[reply["rest_id"]]["link"] = tweetUrl
            replies_dict[reply["rest_id"]]["image_url"] = image_url
            replies_dict[reply["rest_id"]]["likes"] = reply["legacy"].get("favorite_count", 0)
            replies_dict[reply["rest_id"]]["retweets"] = reply["legacy"].get("retweet_count", 0)
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
        
    max_child_length = max(get_longest_chain_length(child, json_data, cache) for child in children)
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
        return text.replace(endDetailsStr, "").replace("</ul>", "").replace(" ", "").replace("\n", "")

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
        if cleanedText.endswith(cleanedNotReplyStr): ## prevent duplication of this element due to > 1 consecutive de-indents
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
    op_username = rawReplies[0]["core"]["user_results"]["result"]["legacy"]["screen_name"]
    replies = parseReplies(rawReplies, op_username, highQuality)
    html = f"<a href={url}>Original</a><br><br>" + json_to_html(
        replies, tweet_id, op_username
    )
    title = replies[tweet_id]["text"][:50]
    urlToOpen = utilities.writeGist(html, "TWTR: " + title, tweet_id)
    return urlToOpen


if __name__ == "__main__":
    print(
        convertTwitter(
            "https://x.com/metaproph3t/status/1863281120927760692###convo", forceRefresh=True
        )
    )
    # print(json.dumps(get_tweet_by_id("1858629520871375295"), indent=4))
