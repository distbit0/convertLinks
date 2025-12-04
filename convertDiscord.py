from os import path
import time

import re
import requests
from dotenv import load_dotenv
import os
import utilities
import json
from dateutil import parser

load_dotenv()


def extract_and_validate_numbers_from_url(url):
    url = url.split("#")[0]
    # Split the URL by slash to break it into parts
    parts = url.split("/")
    # Use a list comprehension to filter parts that can be converted to integers
    numeric_parts = [part for part in parts if part.isdigit() or part == "@me"]

    # Check if there are exactly three numeric parts in the URL
    if len(numeric_parts) == 3:
        # Return the last two numbers if the condition is met
        return numeric_parts[-2:]
    else:
        # Return False if there are not exactly three numbers in the URL
        return False


def fetch_messages(channel_id, initial_message_id):
    base_url = "https://discord.com/api/v9/channels"
    authToken = os.getenv("DISCORD_AUTH_TOKEN")
    headers = {
        "authorization": authToken,
    }
    all_messages = []
    last_message_id = initial_message_id
    last_timestamp = ""

    # Load cached messages and the latest message ID from the cache file if it exists
    cache_file = f"storage/message_cache_{channel_id}.json"
    cache_file = getAbsPath(cache_file)
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache_data = json.load(f)

        cached_messages = cache_data.get("messages", [])

        # Keep only cached messages at or after the requested starting message.
        try:
            initial_id_int = int(initial_message_id)
            filtered_cached_messages = [
                msg
                for msg in cached_messages
                if int(msg.get("id", 0)) >= initial_id_int
            ]
        except ValueError:
            # If IDs are not numeric, fall back to using the provided cache without filtering.
            filtered_cached_messages = cached_messages

        all_messages = filtered_cached_messages

        # Resume fetching from the newest kept message, or the initial ID if none remain.
        if filtered_cached_messages:
            last_message_id = max(
                filtered_cached_messages, key=lambda msg: int(msg.get("id", 0))
            ).get("id", initial_message_id)
        else:
            last_message_id = initial_message_id

    while True:
        time.sleep(1.5)  # avoid rate limit
        params = {"limit": 100, "after": last_message_id}
        print(params)
        response = requests.get(
            f"{base_url}/{channel_id}/messages", headers=headers, params=params
        )
        messages = response.json()
        messages.reverse()

        modifiedMessages = []
        for message in messages:
            print(message["id"])
            if "mentions" in message:
                for mention in message["mentions"]:
                    id = mention["id"]
                    username = mention["username"]
                    message["content"] = message["content"].replace(
                        "<@" + str(id) + ">", "@" + username
                    )
            modifiedMessages.append(message)

        if not messages:
            print("no messages returned this time")
            break  # Break if no messages are returned

        current_last_message = messages[-1]  # Get the last message of the current fetch
        current_last_timestamp = current_last_message["timestamp"]

        if last_timestamp == current_last_timestamp:
            print("already at latest timestamp last request")
            break  # Break if the last message timestamp hasn't changed, indicating no new messages

        all_messages.extend(modifiedMessages)

        last_message_id = current_last_message["id"]
        last_timestamp = current_last_timestamp

        print(
            "\n".join(
                [
                    str(message["id"]) + ": " + message["timestamp"]
                    for message in messages
                ]
            )
        )

    # Save the cached messages and the latest message ID to the cache file
    with open(cache_file, "w") as f:
        json.dump({"messages": all_messages, "latest_message_id": last_message_id}, f)

    # Convert the timestamp string to a Unix timestamp for each message
    for message in all_messages:
        timestamp_str = message["timestamp"]
        timestamp = parser.parse(timestamp_str)
        unix_timestamp = int(timestamp.timestamp())
        message["unix_timestamp"] = unix_timestamp

    # Sort the messages in ascending order based on the Unix timestamp
    sorted_messages = sorted(
        all_messages, key=lambda message: message["unix_timestamp"]
    )

    return sorted_messages


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))

    return fullPath


def createHtmlFromJSON(messagesList, originalUrl):

    # Sort messages by timestamp
    messagesList.sort(key=lambda x: x["timestamp"])

    # Extract the first message content for the HTML title, removing non-alphabetic characters and limiting to 100 chars
    firstMsg = (
        re.sub(r"[^a-zA-Z ]", "", messagesList[0]["content"]) if messagesList else ""
    )

    html = f"[Original]({originalUrl})  \n\n"

    for message in messagesList:
        # Skip empty messages
        if not message["content"]:
            continue

        username = message["author"]["username"]
        content = message["content"].replace("\n", "<br>")
        messageLink = "/".join(originalUrl.split("/")[:-1] + [str(message["id"])])
        html += f'<p><a href="{messageLink}">{username}</a>: {content}</p>'

    return html, firstMsg[:50]


def convertDiscord(url, forceRefresh):
    urlExtract = extract_and_validate_numbers_from_url(url)
    if urlExtract:
        channel_id, initial_message_id = urlExtract
    else:
        print("invalid url")
        return False
    gistUrl = utilities.getGistUrl(initial_message_id)
    print("forceRefresh", forceRefresh)
    if gistUrl and not forceRefresh:
        return gistUrl
    all_messages = fetch_messages(channel_id, initial_message_id)
    html, firstMsg = createHtmlFromJSON(all_messages, url)
    urlToOpen = utilities.writeGist(html, "DISC: " + firstMsg, initial_message_id)
    return urlToOpen
