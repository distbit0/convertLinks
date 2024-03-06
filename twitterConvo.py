import snscrape.modules.twitter as sntwitter
from datetime import datetime, timedelta
import subprocess
import json
import sys
import re
from pathlib import Path
import pyperclip
import notify2
import socket
import traceback


headHtml = """
<head>
  <meta content="text/html;charset=utf-8" http-equiv="Content-Type">
  <meta content="utf-8" http-equiv="encoding">
  <title>{{title}}</title>
  <style>
    html {
        background-color: black;
        color: white;
        font-family: Arial, sans-serif;
    }
      .indent {
        padding-left: 10px;
        margin-left: 10px;
        margin-bottom: 6px;
        border-radius: 5px;
      }
    p {
      margin: 5px;
      padding: 5px;
    }
  </style>
</head>"""


def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't even have to be reachable
        sock.connect(("10.255.255.255", 1))
        IP = sock.getsockname()[0]
    except Exception:
        IP = "127.0.0.1"
    finally:
        sock.close()
    return IP


def convert_https_to_html(string):
    # First, find all of the https links in the string using a regular expression
    pattern = r"https:\/\/\S+"
    links = re.findall(pattern, string)
    # Next, replace each link with an HTML `<a>` element
    for link in links:
        string = string.replace(link, f'<a href="{link}">{link}</a>')

    return string


def addTweetHtmlLink(tweet, link):
    # First, find all of the https links in the string using a regular expression
    pattern = r"\{.*?\}:"
    username = re.findall(pattern, tweet)[0]
    # Next, replace each link with an HTML `<a>` element
    string = tweet.replace(
        username, '<a style="color: white" href="' + link + '">' + username + "</a>"
    )

    return string


def get_first_arg():
    # sys.argv is a list that contains the command-line arguments
    # The first element of the list (sys.argv[0]) is the name of the script itself
    # The second element (sys.argv[1]) is the first argument, and so on
    if len(sys.argv) > 1:
        return sys.argv[1].split("/")[-1].strip(".html")
    else:
        return None


def getReplies(tweet_id):
    print(tweet_id)
    rawReplies = []

    # Get the date of the tweet
    mainTweet = next(sntwitter.TwitterTweetScraper(tweet_id).get_items())
    tweet_date = mainTweet.date

    # Calculate the date range for the search (2 or 3 days after the tweet post)
    start_date = tweet_date.strftime("%Y-%m-%d")
    end_date = (tweet_date + timedelta(days=3)).strftime("%Y-%m-%d")

    # Use the TwitterSearchScraper with the new query format
    scraper = sntwitter.TwitterSearchScraper(
        f"to:{mainTweet.user.username} since:{start_date} until:{end_date}",
        maxEmptyPages=5,
    )
    # Get all tweets from the search
    tweets = [tweet for tweet in scraper.get_items()]
    tweets.append(mainTweet)

    # Iterate through the tweets and check if the inReplyToTweetId matches the original tweet ID
    for reply in tweets:
        if reply.id == mainTweet.id or reply.replyCount == 0:
            rawReplies.append(reply)
            continue
        if reply.inReplyToTweetId != mainTweet.id:
            continue
        print("down")
        rawReplies.extend(getReplies(reply.id))
        print("up")

    return rawReplies


def parseReplies(rawReplies):
    replies_dict = {}
    for reply in rawReplies:
        onlyTagsSoFar = True
        contentWords = []
        if not hasattr(reply, "rawContent"):
            continue
        for word in reply.rawContent.split(" "):
            if "@" in word:
                if onlyTagsSoFar:
                    continue
            else:
                onlyTagsSoFar = False
            contentWords.append(word)
        text = " ".join(contentWords)
        text = "{" + reply.user.username + "}: " + text
        if reply.quotedTweet != None and hasattr(reply.quotedTweet, "rawContent"):
            text += " {Quoted tweet}: " + reply.quotedTweet.rawContent
        if reply.retweetedTweet != None and hasattr(reply.retweetedTweet, "rawContent"):
            text += " {RT'd tweet}: " + reply.retweetedTweet.rawContent
        if reply.id in replies_dict:
            replies_dict[reply.id]["text"] = text
            replies_dict[reply.id]["link"] = reply.url
        else:
            replies_dict[reply.id] = {"text": text, "children": [], "link": reply.url}
        # If the reply has a parent tweet, add it as a child to the parent tweet in the dictionary structure
        if reply.inReplyToTweetId:
            parent_id = reply.inReplyToTweetId
            if parent_id in replies_dict:
                replies_dict[parent_id]["children"].append(reply.id)
                replies_dict[parent_id]["children"] = list(
                    set(replies_dict[parent_id]["children"])
                )
            else:
                replies_dict[parent_id] = {
                    "text": "",
                    "children": [reply.id],
                    "link": "",
                }

    return replies_dict


def json_to_md(json_data, topTweet):
    # Initialize an empty HTML string
    # Recursively convert each tweet and its children to HTML
    def convert_to_md(tweet_id, level):
        outStr = ""
        # Indent the tweet based on its level in the hierarchy
        indent = "    " * level + "- "
        tweet = json_data[int(tweet_id)]
        # Add the tweet text to the HTML string
        outStr = indent + tweet["text"].replace("\n", "") + "\n"
        # print(sorted(tweet["children"]), tweet_id)
        # Recursively convert the children of the tweet to HTML
        for childId in tweet["children"]:
            outStr += convert_to_md(childId, level + 1)

        return outStr

    # Convert the top-level tweets to HTML

    outStr = convert_to_md(topTweet, 0)

    return outStr


def jsonToHtml(json_data, topTweetId, headHtml):
    # Initialize an empty HTML string
    # Recursively convert each tweet and its children to HTML
    def convert_to_html(tweet_id, level):
        outStr = ""
        # Indent the tweet based on its level in the hierarchy

        if level % 2 == 0:
            outStr += '<div class="indent" style="background-color: black">\n'
        else:
            outStr += '<div class="indent" style="background-color: #303030">\n'
        indent = "    " * level + "- "
        tweet = json_data[int(tweet_id)]
        # Add the tweet text to the HTML string
        tweetText = convert_https_to_html(tweet["text"])
        tweetText = addTweetHtmlLink(tweetText, tweet["link"]).replace("\n", "<br>")
        outStr += "<p>" + tweetText + "</p>\n"
        # Recursively convert the children of the tweet to HTML
        for childId in tweet["children"]:
            outStr += convert_to_html(childId, level + 1)

        outStr += "</div>\n"
        return outStr

    topTweetText = json_data[int(topTweetId)]["text"]
    ##Remove all non-alphabetic characters from topTweetText
    topTweetText = re.sub(r"[^a-zA-Z ]", "", topTweetText)
    topTweetText = " ".join(topTweetText.split(" ")[1:]).lower()[:100]
    # Convert the top-level tweets to HTML
    headHtml = headHtml.replace("{{title}}", topTweetText)
    outStr = convert_to_html(topTweetId, 0)
    outStr = "<html>\n" + headHtml + "\n<body>\n" + outStr + "\n</body>\n</html>"

    return outStr


def main(tweet_id):
    config = json.loads(open("config.json").read())
    notify2.init("TwitterConvo")
    n = notify2.Notification("convo id:", str(tweet_id))
    n.show()
    rawReplies = getReplies(tweet_id)
    replies = parseReplies(rawReplies)

    outputMd = json_to_md(replies, tweet_id)
    with open("output.md", "w") as outputMdFile:
        outputMdFile.write(outputMd)

    html = jsonToHtml(replies, tweet_id, headHtml)
    htmlPath = config["htmlFolderPath"] + tweet_id + ".html"
    if config["htmlFolderUrl"]:
        localIP = get_local_ip()
        urlToOpen = (
            config["htmlFolderUrl"].replace("localhost", localIP) + tweet_id + ".html"
        )
        pyperclip.copy(urlToOpen)
    else:
        urlToOpen = htmlPath
    with open(htmlPath, "w+") as outputHtmlFile:
        outputHtmlFile.write(html)

    subprocess.run(["xdg-open", urlToOpen])


if __name__ == "__main__":
    notify2.init("TwitterConvo")
    tweet_id = get_first_arg()

    try:
        main(tweet_id)
    except:
        traceback.print_exc()
        n = notify2.Notification("failed: ", str(tweet_id))
        subprocess.run(
            [
                "xdg-open",
                "https://twitter.com/bob/status/" + tweet_id + "##CONVOGENFAILED",
            ]
        )
    else:
        n = notify2.Notification("success: ", str(tweet_id))
    n.show()
