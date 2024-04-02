import re
import pysnooper
import subprocess
import json
import threading
from os import path
from convertDiscord import convertDiscord
from convertTelegram import convertTelegram
from convertYoutube import convertYoutube
from convertPodcast import convertPodcast
from convertGitbook import convertGitbook
from convertSoundcloud import convertSoundcloud
from convertMp4 import convertMp4
from convertStreameth import convertStreameth
import traceback
import os


def get_selected_text():
    try:
        selected_text = subprocess.check_output(
            ["xclip", "-o", "-selection", "clipboard"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return selected_text
    except subprocess.CalledProcessError as e:
        subprocess.run(["notify-send", "Clipboard Error", "Failed to read clipboard."])
        return None


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())
    return config


# URL extraction and opening
def find_urls_in_text(text):
    isValidUnixPath = os.path.isdir(text) or os.path.isfile(text)
    if isValidUnixPath:
        return [text]
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?:#[a-zA-Z0-9-_]*)?"
    )
    return [url.strip(")") for url in url_pattern.findall(text)]


def convertGDocs(url):
    url_parts = url.split("/")
    if "edit" in url_parts:
        edit_index = url_parts.index("edit")
        modified_url_parts = url_parts[:edit_index]
        modified_url_parts.append("export?format=txt")
        modified_url = "/".join(modified_url_parts)
        return modified_url
    else:
        return url


def convertWikipedia(url):
    url = url.replace("en.m.wikipedia.org", "en.wikipedia.org").strip()
    return url


def convertReddit(url):
    url = url.replace("https://www.reddit.com", "https://old.reddit.com").strip()
    return url


def convertMedium(url):
    if "-" in url:
        if len(url.split("-")[-1]) == 12:
            url = url.replace("medium.com", "scribe.rip").strip()
    return url


def convertDiscourse(url):
    tempUrl = str(url)
    if tempUrl[-1] != "/":
        tempUrl += "/"
    if re.search(r"(\/t\/[^\/]*\/\d+\/)", tempUrl):
        if re.search(r"(t\/[^\/]*\/\d+\/)$", tempUrl):
            tempUrl += "print"
        if re.search(r"(t\/[^\/]*\/\d+\/)(([a-z]+|\d+)\/)$", tempUrl):
            tempUrl = re.sub(
                r"(t\/[^\/]*\/\d+\/)(([a-z]+|\d+)\/)$", r"\1print", tempUrl
            )
    else:
        tempUrl = str(url)
    return tempUrl


def convertLesswrong(url):
    url = url.replace("lesswrong.com", "greaterwrong.com").strip()
    return url


def returnUnchanged(url):
    return url


def open_in_browser(url):
    subprocess.run(["xdg-open", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


conversion_functions = {
    "/watch?": {"function": convertYoutube, "alwaysConvert": True},
    "docs.": {"function": convertGitbook, "alwaysConvert": True},
    "twitter.com": {"function": returnUnchanged, "alwaysConvert": False},
    "warpcast.com": {"function": returnUnchanged, "alwaysConvert": False},
    "docs.google.com/document/": {
        "function": convertGDocs,
        "alwaysConvert": False,
    },
    "streameth.org": {"function": convertStreameth, "alwaysConvert": False},
    "https://t.me/c/": {"function": convertTelegram, "alwaysConvert": False},
    ".mp4": {"function": convertMp4, "alwaysConvert": False},
    "discord.com": {"function": convertDiscord, "alwaysConvert": True},
    "rumble.com": {"function": returnUnchanged, "alwaysConvert": True},
    "gitbook": {"function": convertGitbook, "alwaysConvert": True},
    "m.wikipedia.org": {"function": convertWikipedia, "alwaysConvert": True},
    "reddit.com": {"function": convertReddit, "alwaysConvert": True},
    "medium.com": {"function": convertMedium, "alwaysConvert": True},
    "podcasts.apple.com": {"function": convertPodcast, "alwaysConvert": True},
    "/t/": {"function": convertDiscourse, "alwaysConvert": True},
    "lesswrong.com": {"function": convertLesswrong, "alwaysConvert": True},
    "soundcloud.com": {"function": convertSoundcloud, "alwaysConvert": True},
    "/home/pimania/ebooks/": {"function": convertGitbook, "alwaysConvert": True},
}


# @pysnooper.snoop()
def process_url(originalUrl, openInBrowser, openingToRead):
    try:
        url = str(originalUrl)
        for key, value in conversion_functions.items():
            if url and key in url:
                func = value["function"]
                alwaysConvert = value["alwaysConvert"]
                if alwaysConvert or openingToRead:
                    # print("converting url", url, "with function", func.__name__)
                    url = func(url)
    except Exception as e:
        print(e)
        traceback.print_exc()
        subprocess.run(
            ["notify-send", "URL Processing Error", f"Error: {url}" + str(e)]
        )
        open_in_browser(originalUrl)
        return None
    else:
        if openInBrowser:
            if url:
                return url
            else:
                return originalUrl
        else:
            return url


@pysnooper.snoop()
def main(text, openInBrowser, openingToRead):
    textFromClipboard = not bool(text)
    selected_text = get_selected_text() if textFromClipboard else text
    if selected_text is None:
        return []

    urls = find_urls_in_text(selected_text)
    if len(urls) > 1:
        openingToRead = True  # the fact that multiple are being opened is an indication that the intent may be to open them in @voice
    processed_urls = []

    threads = []
    for url in urls:
        thread = threading.Thread(
            target=lambda u: processed_urls.append(
                process_url(u, openInBrowser, openingToRead)
            ),
            args=(url,),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    processed_urls = [url for url in processed_urls if url]

    if openInBrowser:
        for url in processed_urls:
            open_in_browser(url)

    return processed_urls


if __name__ == "__main__":
    main(None, openInBrowser=True, openingToRead=False)
