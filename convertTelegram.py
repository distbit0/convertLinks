from os import path
import asyncio
import re
import utilities
from telethon import TelegramClient
from telethon.tl.types import MessageEmpty
from dotenv import load_dotenv
import os

load_dotenv()

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME")


def extract_chat_id_and_message_id(url):
    # Extract the chat ID and message ID from the URL
    parts = url.split("/")
    if len(parts) >= 6 and parts[3] == "c":
        chat_id = int(parts[4])
        message_id = int(parts[5])
        return chat_id, message_id
    return None, None


async def fetch_messages(chat_id, initial_message_id, client):
    all_messages = []
    allMessageIds = []
    last_message_id = initial_message_id - 1

    while True:
        print("getting more messages... from message id:", last_message_id)
        messages = await client.get_messages(
            chat_id, min_id=last_message_id, limit=1000
        )
        messages = [message for message in messages if message.id not in allMessageIds]
        messages.sort(key=lambda x: x.id)
        for message in messages:
            print(message.id)
        if not messages:
            print("No messages returned this time")
            break  # Break if no messages are returned
        all_messages.extend(messages)
        allMessageIds.extend([message.id for message in messages])
        last_message_id = messages[-1].id

    return all_messages


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def createHtmlFromMessages(messagesList, originalUrl):
    # Sort messages by timestamp
    messagesList.sort(key=lambda x: x.date)

    # Extract the first message content for the HTML title, removing non-alphabetic characters and limiting to 100 chars
    firstMsg = ""
    i = 0
    while not firstMsg:
        try:
            extractedText = (
                re.sub(r"[^a-zA-Z ]", "", messagesList[i].text) if messagesList else ""
            )
        except:
            pass
        else:
            if extractedText:
                firstMsg = extractedText
        i += 1

    html = f'<p><a href="{originalUrl}">Original</a></p>'

    for message in messagesList:
        # Skip empty messages
        if isinstance(message, MessageEmpty):
            continue

        username = message.sender.username if message.sender else "Unknown"
        content = message.text.replace("\n", "<br>") if message.text else ""
        baseChatUrl = originalUrl.split("?")[0]
        if len(baseChatUrl.split("/")) > 5:
            baseChatUrl = "/".join(baseChatUrl.split("/")[:5])
        messageLink = f"{baseChatUrl}/{message.id}"
        messageLink = messageLink.replace("https://t.me", "https://web.t.me")

        html += f'<p><a href="{messageLink}">{username}</a>: {content}</p>'

    return html, firstMsg[:50]


async def primary(url, client):
    chat_id, message_id = extract_chat_id_and_message_id(url)
    if chat_id and message_id:
        await client.get_dialogs()
        all_messages = await fetch_messages(chat_id, message_id, client)
        html, firstMsg = createHtmlFromMessages(all_messages, url)
        urlToOpen = utilities.writeGist(html, "TG: " + firstMsg, str(message_id))
        return urlToOpen
    else:
        return url


def convertTelegram(url, forceRefresh):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(session_name, api_id, api_hash, loop=loop)
    with client:
        urlToOpen = client.loop.run_until_complete(primary(url, client))
    return urlToOpen


if __name__ == "__main__":
    convertTelegram("https://t.me/c/2675182655/576", False)
