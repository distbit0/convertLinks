import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

gh_api_key = os.getenv("gh_api_key")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
GUIDS_PATH = DATA_DIR / "guidsToGistIds.json"
HASHES_PATH = DATA_DIR / "textCacheHashes.json"
LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(LOG_DIR / "write_gist.log", rotation="256 KB", retention=5, enqueue=False)


def _read_json_file(path: Path) -> dict:
    if not path.exists():
        path.write_text("{}")
        return {}
    content = path.read_text().strip()
    if not content:
        return {}
    return json.loads(content)


def _write_json_file(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=4))


def _create_gist(
    markdown_text: str, gist_file_name: str, headers: dict
) -> dict | None:
    data = {
        "description": gist_file_name,
        "files": {
            f"{gist_file_name}.md": {"content": markdown_text, "type": "text/plain"}
        },
        "public": False,
    }
    response = requests.post("https://api.github.com/gists", json=data, headers=headers)
    if response.status_code not in [200, 201]:
        logger.error("Error when creating gist: {}", gist_file_name)
        logger.error("Response: {}", response.text)
        logger.error("Payload: {}", json.dumps(data, indent=4))
        return None
    return response.json()


def _update_gist(
    gist_id: str, markdown_text: str, gist_file_name: str, headers: dict
) -> dict | None:
    data = {
        "description": gist_file_name,
        "files": {
            f"{gist_file_name}.md": {"content": markdown_text, "type": "text/plain"}
        },
    }
    endpoint = f"https://api.github.com/gists/{gist_id}"
    response = requests.post(endpoint, json=data, headers=headers)
    if response.status_code not in [200, 201]:
        logger.error("Error when updating gist: {} {}", gist_id, gist_file_name)
        logger.error("Response: {}", response.text)
        logger.error("Payload: {}", json.dumps(data, indent=4))
        return None
    return response.json()


def check_if_updated(content_signature: str, gist_id: str) -> bool:
    hash_dict = {}
    while hash_dict == {}:
        try:
            hash_dict = _read_json_file(HASHES_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", HASHES_PATH, exc)
            time.sleep(1)
    if (gist_id not in hash_dict) or (content_signature != hash_dict[gist_id]):
        hash_dict[gist_id] = content_signature
        _write_json_file(HASHES_PATH, hash_dict)
        return True
    return False


def write_to_gist(
    text: str,
    gist_file_name: str,
    gist_id: str | None = None,
):
    gist_file_name = "".join(c if c.isalnum() else " " for c in gist_file_name)

    logger.info("Writing to gist")

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_api_key}",
    }

    if not gist_id:
        created = _create_gist(text, gist_file_name, headers)
        if created is None:
            return None
        gist_id = created["id"]
        content_signature = hashlib.sha1(text.encode()).hexdigest()
        check_if_updated(content_signature, gist_id)
        return gist_id

    content_signature = hashlib.sha1(text.encode()).hexdigest()
    if not check_if_updated(content_signature, gist_id):
        return gist_id

    update_result = _update_gist(gist_id, text, gist_file_name, headers)
    if update_result is None:
        return None

    check_if_updated(content_signature, gist_id)
    return gist_id


def getGistIdFromGUID(guid: str):
    guid_to_gist_id_dict = {}
    while guid_to_gist_id_dict == {}:
        try:
            guid_to_gist_id_dict = _read_json_file(GUIDS_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", GUIDS_PATH, exc)
            time.sleep(1)
            continue
    gist_id = guid_to_gist_id_dict[guid] if guid in guid_to_gist_id_dict else None
    return gist_id


def setGistIdForGUID(guid: str, gist_id: str):
    guid_to_gist_id_dict = {}
    while guid_to_gist_id_dict == {}:
        try:
            guid_to_gist_id_dict = _read_json_file(GUIDS_PATH)
        except Exception as exc:
            logger.warning("Error reading {}: {}", GUIDS_PATH, exc)
            time.sleep(1)
            continue
    guid_to_gist_id_dict[guid] = gist_id
    _write_json_file(GUIDS_PATH, guid_to_gist_id_dict)


# Adjusted CLI functions with minimal KVP dict and specialized JSON conversion
def getGistUrl(name: str):
    gist_id = getGistIdFromGUID(name)
    if not gist_id:
        return False
    return "https://gist.github.com/" + gist_id


def writeContent(url, guid, name, textFilePath):
    name = "" if not name else name
    text_file_path = Path(textFilePath)
    with text_file_path.open("r") as file:
        markdown_text = file.read()
    if url:
        gist_id = url.split("/")[-1]
        write_to_gist(markdown_text, name, gist_id)
    elif guid:
        gist_id = write_to_gist(
            markdown_text,
            name,
            gist_id=getGistIdFromGUID(guid),
        )
        setGistIdForGUID(guid, gist_id)
    else:
        gist_id = write_to_gist(markdown_text, name)

    return "https://gist.github.com/" + gist_id


def main():
    parser = argparse.ArgumentParser(
        description="A CLI tool for managing GitHub Gists."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    info_parser = subparsers.add_parser("url", help="Get a gist's URL given its GUID")
    info_parser.add_argument("--guid", type=str, help="GUID of the gist.")

    write_parser = subparsers.add_parser(
        "write",
        help="Write or update a gist's content from a text file, given the gist's GUID or URL.",
    )
    write_parser.add_argument("--path", type=str, help="Path to the text file.")
    write_parser.add_argument("--url", type=str, help="URL of the gist.", default=None)
    write_parser.add_argument(
        "--guid", type=str, help="GUID of the gist.", default=None
    )
    write_parser.add_argument("--name", type=str, help="Name of the gist.")

    delete_parser = subparsers.add_parser(
        "delete", help="Delete a gist, given the its GUID or URL."
    )
    delete_parser.add_argument("--url", type=str, help="URL of the gist.", default=None)
    delete_parser.add_argument(
        "--guid", type=str, help="GUID of the gist.", default=None
    )

    args = parser.parse_args()

    result = None
    if args.command == "url":
        result = getGistUrl(args.guid)
    elif args.command == "write":
        result = writeContent(args.url, args.guid, args.name, args.path)

    print(result)


if __name__ == "__main__":
    main()
