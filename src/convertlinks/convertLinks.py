import argparse
import re
import subprocess
import threading
import traceback
import os
import pyperclip
from tkinter import Tk, messagebox
import webbrowser

from .convertDiscord import convertDiscord
from .convertDiscourse import convertDiscourse
from .convertGitbook import convertGitbook
from .convertMp3 import convertMp3
from .convertMp4 import convertMp4
from .convertPodcast import convertPodcast
from .convertRumble import convertRumble
from .convertSoundcloud import convertSoundcloud
from .convertStreameth import convertStreameth
from .convertTelegram import convertTelegram
from .convertTwitter import convertTwitter
from .convertYoutube import convertYoutube
from . import utilities


def get_selected_text():
    try:
        selected_text = pyperclip.paste()
        return selected_text
    except Exception as e:
        # Using tkinter for the error message as it's cross-platform
        root = Tk()
        root.withdraw()  # Hide the main window
        messagebox.showerror("Clipboard Error", f"Failed to read clipboard: {str(e)}")
        root.destroy()
        return None


# URL extraction and opening
def find_urls_in_text(text):
    isValidUnixPath = os.path.isdir(text) or os.path.isfile(text)
    if isValidUnixPath:
        return [text]
    url_pattern = re.compile(
        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?:#*[a-zA-Z0-9-_\.]*)?"
    )
    # i previously removed .strip(")") from the below which I for some reason previously thought was necessary but not sure why... it was removing the trailing ) from e.g. wikipedia page urls hence causing issues
    return [url.strip("") for url in url_pattern.findall(text)]


def convertGDocs(url, forceRefresh):
    url_parts = url.split("/")
    if "edit" in url_parts:
        edit_index = url_parts.index("edit")
        modified_url_parts = url_parts[:edit_index]
        modified_url_parts.append("export?format=txt")
        modified_url = "/".join(modified_url_parts)
        return modified_url
    else:
        return url


def convertWikipedia(url, forceRefresh):
    url = url.replace("en.m.wikipedia.org", "en.wikipedia.org").strip()
    return url


def convertReddit(url, forceRefresh):
    url = url.replace("https://www.reddit.com", "https://old.reddit.com").strip()
    return url


def convertMedium(url, forceRefresh):
    if "-" in url:
        if len(url.split("-")[-1]) == 12:
            domain = url.split("https://")[1].split("/")[0]
            url = url.replace(domain, "scribe.rip").strip()
    return url


def convertLesswrong(url, forceRefresh):
    url = url.replace("lesswrong.com", "greaterwrong.com").strip()
    return url


# def convertTelegram(url, forceRefresh):
#     url = url.replace("https://t.me", "https://web.t.me").strip()
#     return url


def returnUnchanged(url, forceRefresh):
    return url


def open_in_browser(url):
    webbrowser.open(url)


conversion_functions = {
    "/watch?": {"function": convertYoutube, "alwaysConvert": False},
    "/live/": {"function": convertYoutube, "alwaysConvert": False},
    "warpcast.com": {"function": returnUnchanged, "alwaysConvert": False},
    ".mp4": {"function": convertMp4, "alwaysConvert": False},
    ".mp3": {"function": convertMp3, "alwaysConvert": False},
    "rumble.com": {"function": convertRumble, "alwaysConvert": False},
    "podcasts.apple.com": {"function": convertPodcast, "alwaysConvert": False},
    "soundcloud.com": {"function": convertSoundcloud, "alwaysConvert": False},
    "streameth.org": {"function": convertStreameth, "alwaysConvert": False},
    "docs.": {"function": convertGitbook, "alwaysConvert": True},
    "/status/": {"function": convertTwitter, "alwaysConvert": True},
    "docs.google.com/document/": {
        "function": convertGDocs,
        "alwaysConvert": False,
    },
    "https://t.me/c/": {"function": convertTelegram, "alwaysConvert": False},
    "discord.com": {"function": convertDiscord, "alwaysConvert": True},
    "gitbook": {"function": convertGitbook, "alwaysConvert": True},
    "m.wikipedia.org": {"function": convertWikipedia, "alwaysConvert": True},
    "reddit.com": {"function": convertReddit, "alwaysConvert": True},
    "medium.com": {"function": convertMedium, "alwaysConvert": True},
    "/t/": {"function": convertDiscourse, "alwaysConvert": True},
    "lesswrong.com": {"function": convertLesswrong, "alwaysConvert": True},
    "https://t.me": {"function": convertTelegram, "alwaysConvert": True},
}


# @pysnooper.snoop()
def process_url(originalUrl, openInBrowser, forceConvertAllUrls, forceNoConvert=False):
    try:
        url = str(originalUrl)
        if not forceNoConvert:
            for key, value in conversion_functions.items():
                if url and key in url:
                    func = value["function"]
                    alwaysConvert = value["alwaysConvert"]
                    forceConvert = "##" in url
                    forceRefresh = "###" in url
                    if alwaysConvert or forceConvertAllUrls or forceConvert:
                        # print("converting url", url, "with function", func.__name__)
                        url = func(url, forceRefresh)
    except Exception as e:
        print(e)
        traceback.print_exc()
        root = Tk()
        root.withdraw()
        messagebox.showerror("URL Processing Error", f"Error: {url}{e}")
        root.destroy()
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


def main(
    text, openInBrowser, forceConvertAllUrls, summarise=False, forceNoConvert=False
):
    utilities.set_default_summarise(summarise)
    textFromClipboard = not bool(text)
    selected_text = get_selected_text() if textFromClipboard else text
    if selected_text is None:
        return []

    urls = find_urls_in_text(selected_text)
    # if len(urls) > 1:
    #     forceConvertAllUrls = True  # the fact that multiple are being opened is an indication that the intent may be to open them in @voice
    processed_urls = []
    print("urls", urls)
    threads = []
    for url in urls:
        thread = threading.Thread(
            target=lambda u: processed_urls.append(
                process_url(u, openInBrowser, forceConvertAllUrls, forceNoConvert)
            ),
            args=(url,),
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    processed_urls = [url for url in processed_urls if url]
    print("processed_urls", processed_urls)
    if openInBrowser:
        for url in processed_urls:
            open_in_browser(url)

    return processed_urls


def cli():
    parser = argparse.ArgumentParser(description="Convert and normalize URLs.")
    parser.add_argument(
        "text",
        nargs="?",
        help="Text or URL(s). If omitted, clipboard contents are used.",
    )
    parser.add_argument(
        "--force-convert-all",
        action="store_true",
        default=True,
        help="Force conversion for all URLs, even if not marked alwaysConvert.",
    )
    parser.add_argument(
        "--summarise",
        action="store_true",
        help="Summarize markdown before writing gists.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open processed URLs in the browser.",
    )
    parser.add_argument(
        "--force-no-convert",
        action="store_true",
        help="Skip conversion for all URLs, even those marked to always convert.",
    )
    args = parser.parse_args()

    main(
        args.text,
        openInBrowser=not args.no_open,
        forceConvertAllUrls=args.force_convert_all,
        summarise=args.summarise,
        forceNoConvert=args.force_no_convert,
    )


if __name__ == "__main__":
    cli()
