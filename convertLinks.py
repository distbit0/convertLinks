import re
import subprocess
import json
import threading
from os import path
import convertDiscord
import convertTelegram
import convertYoutube
import convertGitbook
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
    return [url.strip(")") for url in url_pattern.findall(text)]


def open_in_browser(url):
    subprocess.run(["xdg-open", url], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def convert_youtube(url, openingToRead):
    videoId = url.split("v=")[-1]
    videoUrl = f"https://www.youtube.com/watch?v={videoId}"
    print(videoUrl)
    return convertYoutube.main(videoUrl)


def convert_rumble(url, openingToRead):
    if openingToRead:
        return url

    return url


def convert_podcast(url, openingToRead):
    if openingToRead:
        return url
    return url


def convert_twitter(url, openingToRead):
    if not openingToRead:
        return url
    return url


def convert_farcaster(url, openingToRead):
    if not openingToRead:
        return url
    return url


def convert_gitbook(url, openingToRead):
    if "docs.google.com" in url:
        return url
    return convertGitbook.main(url)


def convert_telegram(url, openingToRead):
    if not openingToRead:
        return url
    return url  # convertTelegram.main(url)


def convert_discord(url, openingToRead):
    if not openingToRead:
        return url
    return convertDiscord.main(url)


def convert_gdoc(url, openingToRead):
    if not openingToRead:
        return url

    # Split the URL into parts
    url_parts = url.split("/")

    # Check if the URL contains "/edit"
    if "edit" in url_parts:
        # Find the index of "/edit"
        edit_index = url_parts.index("edit")

        # Slice the URL parts up to "/edit" (exclusive)
        modified_url_parts = url_parts[:edit_index]

        # Append "/export?format=txt" to the modified URL parts
        modified_url_parts.append("export?format=txt")

        # Join the modified URL parts back into a string
        modified_url = "/".join(modified_url_parts)

        return modified_url

    # If "/edit" is not found, return the original URL
    return url


def convert_wikipedia(url, openingToRead):
    url = url.replace("en.m.wikipedia.org", "en.wikipedia.org").strip()
    return url


def convert_reddit(url, openingToRead):
    url = url.replace("reddit.com", "old.reddit.com").strip()
    return url


def convert_medium(url, openingToRead):
    if "-" in url:
        if len(url.split("-")[-1]) == 12:
            url = url.replace("medium.com", "scribe.rip").strip()
    return url


def convert_discourse(url, openingToRead):
    if not url:
        return ""
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


def convert_lesswrong(url, openingToRead):
    url = url.replace("lesswrong.com", "greaterwrong.com").strip()
    return url


conversion_functions = {
    "watch?v=": convert_youtube,
    "rumble.com": convert_rumble,
    "docs.": convert_gitbook,
    "gitbook": convert_gitbook,
    "discord.com": convert_discord,
    "twitter.com": convert_twitter,
    "warpcast.com": convert_farcaster,
    "docs.google.com/document/": convert_gdoc,
    "m.wikipedia.org": convert_wikipedia,
    "reddit.com": convert_reddit,
    "medium.com": convert_medium,
    "https://t.me/c/": convert_telegram,
    "podcasts.apple.com": convert_podcast,
    "": convert_discourse,
    "lesswrong.com": convert_lesswrong,
}


def process_url(originalUrl, openInBrowser, openingToRead):
    try:
        url = str(originalUrl)
        for key, func in conversion_functions.items():
            if key in url:
                url = func(url, openingToRead)
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


def main(text, openInBrowser, openingToRead):
    textFromClipboard = not bool(text)
    selected_text = get_selected_text() if textFromClipboard else text
    if selected_text is None:
        return []

    urls = find_urls_in_text(selected_text)
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
