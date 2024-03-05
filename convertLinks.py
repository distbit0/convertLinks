import re
import subprocess
import json
import threading
from os import path
import sys
import convertDiscord
import traceback


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
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )
    return url_pattern.findall(text)


def open_in_browser(url):
    subprocess.run(["xdg-open", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def convert_youtube(url, openInBrowser):
    return url


def convert_rumble(url, openInBrowser):
    return url


def convert_invidious(url, openInBrowser):
    return url


def convert_docs(url, openInBrowser):
    return url


def convert_discord(url, openInBrowser):
    return convertDiscord.main(url)


def convert_twitter(url, openInBrowser):
    return url


def convert_farcaster(url, openInBrowser):
    return url


conversion_functions = {
    "youtube.com": convert_youtube,
    "rumble.com": convert_rumble,
    "invidio.us": convert_invidious,
    "docs.": convert_docs,
    "discord.com": convert_discord,
    "twitter.com": convert_twitter,
    "farcaster.com": convert_farcaster,
}


def process_url(url, is_main):
    try:
        for key, func in conversion_functions.items():
            if key in url:
                converted_url = func(url, is_main)
                if is_main:
                    open_in_browser(converted_url)
                return converted_url
        if is_main:
            open_in_browser(url)
        return url
    except Exception as e:
        print(e)
        traceback.print_exc()
        subprocess.run(["notify-send", "URL Processing Error", f"Error: {url}"])


def main(text, openInBrowser):
    textFromClipboard = not bool(text)
    selected_text = get_selected_text() if textFromClipboard else text
    print(selected_text)
    if selected_text is None:
        return []
    urls = find_urls_in_text(selected_text)
    processed_urls = []

    if openInBrowser:
        threads = []
        for url in urls:
            thread = threading.Thread(target=lambda: process_url(url, openInBrowser))
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
    else:
        for url in urls:
            processed_url = process_url(url, openInBrowser)
            processed_urls.append(processed_url)
    return processed_urls


if __name__ == "__main__":
    main(None, openInBrowser=True)
