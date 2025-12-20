import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse
from telethon import TelegramClient
from telethon.tl.types import MessageEmpty
from dotenv import load_dotenv
from loguru import logger
import os
import sys

from . import utilities

load_dotenv()

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")
session_name = os.getenv("TELEGRAM_SESSION_NAME")

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO")
logger.add(LOG_DIR / "telegram.log", rotation="256 KB", retention=5, enqueue=True)


def extract_chat_id_and_message_id(url):
    # Extract the chat ID and message ID from the URL
    parsed_url = urlparse(url)
    path_parts = [part for part in parsed_url.path.split("/") if part]

    try:
        # Private/supergroup links: https://t.me/c/<chat_id>/<message_id>
        if len(path_parts) >= 3 and path_parts[0] == "c":
            chat_id = int(path_parts[1])
            message_id = int(path_parts[2])
            return chat_id, message_id

        # Public channel/group links: https://t.me/<chat_username>/<message_id>
        if len(path_parts) >= 2 and path_parts[1].isdigit():
            chat_id = path_parts[0]
            message_id = int(path_parts[1])
            return chat_id, message_id
    except ValueError:
        # If casting to int fails, treat as invalid
        pass

    return None, None


async def fetch_messages(chat_id, initial_message_id, client, limit=None):
    """Fetch messages starting at the provided message id in chronological order.

    If limit is None, fetch all messages from initial_message_id to the latest.
    """
    messages: list = []

    first_message = await client.get_messages(chat_id, ids=initial_message_id)
    if first_message and not isinstance(first_message, MessageEmpty):
        messages.append(first_message)

    remaining_limit = None if limit is None else max(limit - len(messages), 0)
    fetched = 0

    async for message in client.iter_messages(
        chat_id,
        min_id=initial_message_id,
        reverse=True,
        limit=remaining_limit,
    ):
        if isinstance(message, MessageEmpty):
            continue
        messages.append(message)
        fetched += 1
        if fetched % 500 == 0:
            logger.info("Fetched {} additional messages (last id {})", fetched, message.id)

    logger.info(
        "Fetched {} messages starting from id {} (last id {})",
        len(messages),
        initial_message_id,
        messages[-1].id if messages else initial_message_id,
    )
    return messages


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

    html = ""

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

        html += f'<p><a href="{messageLink}">{username}</a>: {content}</p>'

    return html, firstMsg[:50]


async def primary(url, client):
    chat_id, message_id = extract_chat_id_and_message_id(url)
    if chat_id and message_id:
        await client.get_dialogs()
        all_messages = await fetch_messages(chat_id, message_id, client)
        html, firstMsg = createHtmlFromMessages(all_messages, url)
        urlToOpen = utilities.writeGist(
            html,
            "TG: " + firstMsg,
            str(message_id),
            source_url=url,
        )
        return urlToOpen
    else:
        return url


def convertTelegram(url, forceRefresh):
    logger.info("Converting Telegram URL: {} forceRefresh={}", url, forceRefresh)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = TelegramClient(session_name, api_id, api_hash, loop=loop)
    with client:
        urlToOpen = client.loop.run_until_complete(primary(url, client))
    return urlToOpen


if __name__ == "__main__":
    logger.info(convertTelegram("https://t.me/c/2392373515/27447", False))
