from os import path
import json
import pyperclip
import subprocess
import re
import json
import requests
from dotenv import load_dotenv
import os
import utilities

load_dotenv()


def extract_and_validate_numbers_from_url(url):
    # Split the URL by slash to break it into parts
    parts = url.split("/")
    # Use a list comprehension to filter parts that can be converted to integers
    numeric_parts = [part for part in parts if part.isdigit()]

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
    first = True
    while True:
        params = {"limit": 100, "around": last_message_id}
        response = requests.get(
            f"{base_url}/{channel_id}/messages", headers=headers, params=params
        )
        messages = response.json()
        messages.reverse()
        if first:
            indexOfFirstMessage = messages.index(
                [message for message in messages if message["id"] == last_message_id][0]
            )
            messages = messages[indexOfFirstMessage:]

        modifiedMessages = []
        for message in messages:
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

        all_messages.extend(
            [message for message in messages if message not in all_messages]
        )
        last_message_id = current_last_message["id"]
        last_timestamp = current_last_timestamp

        # Update params for the next iteration to fetch messages before the current last message
        params["before"] = last_message_id
        print(
            "\n".join(
                [
                    str(message["id"]) + ": " + message["timestamp"]
                    for message in messages
                ]
            )
        )
        first = False

    return all_messages


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

    html = f'<p><a href="{originalUrl}">Link to Original Message</a></p>'

    for message in messagesList:
        # Skip empty messages
        if not message["content"]:
            continue

        username = message["author"]["username"]
        content = message["content"].replace("\n", "<br>")
        messageLink = "/".join(originalUrl.split("/")[:-1] + [str(message["id"])])
        html += f'<p><a href="{messageLink}">{username}</a>: {content}</p>'

    return html, firstMsg[:50]


def main(url):
    if extract_and_validate_numbers_from_url(url):
        channel_id, initial_message_id = extract_and_validate_numbers_from_url(url)
    else:
        return url
    all_messages = fetch_messages(channel_id, initial_message_id)
    html, firstMsg = createHtmlFromJSON(all_messages, url)
    urlToOpen = utilities.writeGist(html, "DISC: " + firstMsg, initial_message_id)
    return urlToOpen
