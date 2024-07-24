from PyTweetToolkit import PyTweetClient
import subprocess
import traceback
import time
import pickle
import json
from datetime import datetime, timedelta
import utilities
import re
from dotenv import load_dotenv
import os


load_dotenv()

auth_token = os.getenv("TWITTER_AUTH_TOKEN")
csrf_token = os.getenv("TWITTER_CT0_TOKEN")

ignored_accounts = ["memdotai", "threadreaderapp"]


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
            f"{indent}<br><details open><summary>{level+1}. {tweetText}</summary>\n"
        )
        # outStr += f"{indent}<ul>\n"
        for childId in tweet["children"]:
            outStr += convert_to_html(childId, level + 1)
        # outStr += f"{indent}</ul>\n"
        outStr += f"{indent}</details>\n"
        return outStr

    # outStr = "<ul>\n"
    outStr = convert_to_html(topTweet, 0)
    # outStr += "</ul>\n"
    return outStr


def getReplies(client, tweet_id, onlyOp, all_tweets=None):
    print(tweet_id)
    rawReplies = []

    if all_tweets is None:
        all_tweets = []
        mainTweet = client.get_tweet(tweet_id)
        opUsername = mainTweet.user.screen_name
        if onlyOp:
            query = f"conversation_id:{mainTweet.rest_id} from:{opUsername}"
        else:
            query = f"conversation_id:{mainTweet.rest_id}"
        cursor = None
        i = 0
        while True:
            try:
                if cursor:
                    tweets, next_cursor, _ = client.search_latest(query, cursor=cursor)
                else:
                    tweets, next_cursor, _ = client.search_latest(query)
                i += 1
                all_tweets.extend(tweets)
                # print("cursor", cursor, "len of tweets", len(tweets))
                if next_cursor is None or next_cursor == "" or len(tweets) == 0:
                    break
                cursor = next_cursor
            except Exception as e:
                print(traceback.format_exc())
                print("network error", e, "sleeping for 5 minutes")
                subprocess.run(
                    ["notify-send", "sleep", "sleeping for 5 minutes" + str(e)]
                )
                time.sleep(300)
                pass
        all_tweets.append(mainTweet)

    print("length of all_tweets", len(all_tweets))
    for reply in all_tweets:
        print(reply)
        print("\n" * 10)
        if reply.rest_id == tweet_id or reply.reply_count == 0:
            rawReplies.append(reply)
            continue
        if reply.in_reply_to_tweet_id_str != tweet_id:
            continue
        print("down")
        rawReplies.extend(getReplies(client, reply.rest_id, onlyOp, all_tweets))
        print("up")

    return rawReplies


def parseReplies(rawReplies):
    replies_dict = {}
    for reply in rawReplies:
        if reply.user.screen_name.lower() in ignored_accounts:
            continue
        onlyTagsSoFar = True
        contentWords = []
        if not hasattr(reply, "full_text"):
            continue
        for word in reply.full_text.split(" "):
            if "@" in word:
                if onlyTagsSoFar:
                    continue
            else:
                onlyTagsSoFar = False
            contentWords.append(word)
        text = " ".join(contentWords)
        text = "{" + reply.user.screen_name + "} " + text
        if reply.quoted_tweet and hasattr(reply.quoted_tweet, "full_text"):
            text += " {Quoted tweet} " + reply.quoted_tweet.full_text
        if reply.retweeted_tweet and hasattr(reply.retweeted_tweet, "full_text"):
            text += " {RT'd tweet} " + reply.retweeted_tweet.full_text
        tweetUrl = (
            "https://twitter.com/"
            + reply.user.screen_name
            + "/status/"
            + str(reply.rest_id)
        )

        image_url = ""
        if reply.media and len(reply.media) > 0:
            image_url = reply.media[0]["url"]

        if reply.rest_id in replies_dict:
            replies_dict[reply.rest_id]["text"] = text
            replies_dict[reply.rest_id]["link"] = tweetUrl
            replies_dict[reply.rest_id]["image_url"] = image_url
            replies_dict[reply.rest_id]["likes"] = reply.favorite_count
            replies_dict[reply.rest_id]["retweets"] = reply.retweet_count
        else:
            replies_dict[reply.rest_id] = {
                "text": text,
                "children": [],
                "link": tweetUrl,
                "image_url": image_url,
                "likes": reply.favorite_count,
                "retweets": reply.retweet_count,
            }
        if reply.in_reply_to_tweet_id_str:
            parent_id = reply.in_reply_to_tweet_id_str
            if parent_id in replies_dict:
                replies_dict[parent_id]["children"].append(reply.rest_id)
                replies_dict[parent_id]["children"] = list(
                    set(replies_dict[parent_id]["children"])
                )
            else:
                replies_dict[parent_id] = {
                    "text": "",
                    "children": [reply.rest_id],
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


def convertTwitter(url, forceRefresh):
    if "#convo" in url:
        onlyOp = False
    elif "#thread" in url:
        onlyOp = True
    else:
        return url
    tweet_id = url.split("/")[-1].strip(".html").split("#")[0]
    gistUrl = utilities.getGistUrl(tweet_id)
    if gistUrl and not forceRefresh:
        return gistUrl
    client = PyTweetClient(auth_token=auth_token, csrf_token=csrf_token)
    rawReplies = getReplies(client, tweet_id, onlyOp)
    # pickle.dump(rawReplies, open("tmp/rawReplies.pickle", "wb"))
    # rawReplies = pickle.load(open("tmp/rawReplies.pickle", "rb"))
    replies = parseReplies(rawReplies)
    op_username = rawReplies[-1].user.screen_name
    html = f"<a href={url}>Original</a><br><br>" + json_to_html(
        replies, tweet_id, op_username
    )
    title = replies[tweet_id]["text"][:50]
    urlToOpen = utilities.writeGist(html, "TWTR: " + title, tweet_id)
    return urlToOpen


if __name__ == "__main__":
    print(
        convertTwitter(
            "https://twitter.com/colludingnode/status/1775792986955096435#convo"
        )
    )
