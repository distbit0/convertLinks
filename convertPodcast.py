import time
from pydub import AudioSegment
import re
import json
import random
import utilities
import os
from dotenv import load_dotenv
from math import ceil
from openai import OpenAI
import requests
from html import unescape

load_dotenv()


def get_podcast_episode_info(url):
    # Send a GET request to the podcast episode URL
    response = requests.get(url)
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

    return None, None


def download_podcast_episode(url):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Get the episode info
    audio_url, title = get_podcast_episode_info(url)

    # Download the podcast episode
    response = requests.get(audio_url, allow_redirects=True)
    response.raise_for_status()

    # Save the episode audio to a file
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")
    with open(mp3_file, "wb") as file:
        file.write(response.content)

    return mp3_file, title


def convertPodcast(episode_url, forceRefresh):
    inputSource = "Podcast"
    podcastId = episode_url.split("/")[-1].split("?")[0]
    episodeId = episode_url.split("?i=")[-1].split("#")[0]
    episodeId = podcastId + "_" + episodeId
    gistUrl = utilities.getGistUrl(episodeId)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file, title = download_podcast_episode(episode_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(inputSource, episode_url, audio_chunks)
    gist_url = utilities.writeGist(
        transcript, f"{inputSource}: " + title, episodeId, update=True
    )
    return gist_url
