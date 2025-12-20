import time
import re
import json
import random
import os
from dotenv import load_dotenv
import requests
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

import utilities

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]


def get_podcast_episode_info(url):
    # Send a GET request to the podcast episode URL
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    # Find the script tag containing the JSON data
    script_pattern = re.compile(
        r'<script type="fastboot/shoebox" id="shoebox-media-api-cache-amp-podcasts">(.*?)</script>',
        re.DOTALL,
    )
    script_match = script_pattern.search(response.text)
    if script_match:
        script_content = script_match.group(1)
        script_content = unescape(script_content)
        json_data = json.loads(script_content, strict=False)

        # Locate the element in the JSON data containing the asset URL
        for key in json_data:
            if "podcast-episode" in key:
                newJson = json.loads(unescape(json_data[key]))
                decoded_url = newJson["d"][0]["attributes"]["assetUrl"]
                title = newJson["d"][0]["attributes"]["name"]
                return decoded_url, title

    script_tags = re.findall(r"<script[^>]*>(.*?)</script>", response.text, re.DOTALL)
    for script in sorted(script_tags, key=len, reverse=True):
        try:
            data = json.loads(script)
        except json.JSONDecodeError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "streamUrl" in item and "title" in item:
                    return item["streamUrl"], item["title"]
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)

    return None, None


def download_podcast_episode(url):
    # Set the output directory relative to the script's location
    output_dir = REPO_ROOT / "tmp"
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Get the episode info
    audio_url, title = get_podcast_episode_info(url)

    if not audio_url:
        raise ValueError(f"Could not find audio URL for {url}")

    # Download the podcast episode
    response = requests.get(
        audio_url,
        allow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0", "Referer": url},
    )
    response.raise_for_status()

    audio_path = Path(urlparse(audio_url).path)
    audio_ext = audio_path.suffix.lower().lstrip(".")
    if audio_ext not in {"mp3", "m4a", "mp4"}:
        raise ValueError(f"Unsupported podcast audio extension: {audio_ext or 'none'}")

    # Save the episode audio to a file
    audio_file = output_dir / f"{randomNumber}.{audio_ext}"
    with open(audio_file, "wb") as file:
        file.write(response.content)

    return str(audio_file), title


def convertPodcast(episode_url, forceRefresh):
    inputSource = "Podcast"
    podcastId = episode_url.split("/")[-1].split("?")[0]
    episodeId = episode_url.split("?i=")[-1].split("#")[0]
    episodeId = podcastId + "_" + episodeId
    gistUrl = utilities.get_gist_url_for_guid(episodeId)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file, title = download_podcast_episode(episode_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(audio_chunks)
    gist_url = utilities.writeGist(
        transcript,
        f"{inputSource}: " + title,
        episodeId,
        update=True,
        source_url=episode_url,
    )
    return gist_url


if __name__ == "__main__":
    convertPodcast(
        "https://podcasts.apple.com/us/podcast/revolutionizing-governance-how-futarchy-is-shaking/id1661582246?i=1000701481178",
        forceRefresh=True,
    )
