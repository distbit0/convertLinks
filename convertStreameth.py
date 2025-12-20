import requests
import time
from pydub import AudioSegment
import re
import random
import utilities
import os
from dotenv import load_dotenv
from math import ceil
from openai import OpenAI

load_dotenv()


def getMp4UrlAndName(url):
    # Fetch the text from the URL
    response = requests.get(url)
    text = response.text

    # Find the first substring between '"' and 'download="clip-' using regex
    pattern = r"https:\/\/vod-cdn\.lp-playback\.studio\/raw\/[a-z0-9]+\/catalyst-vod-com\/hls\/[a-z0-9]+\/1080p0\.mp4"
    match = re.search(pattern, text)
    mp4Url = match.group(0) if match else ""
    print("mp4Url", mp4Url)

    # Find the second substring between '<title>' and '| StreamETH</title>'
    start_index = text.find("<title>") + len("<title>")
    end_index = text.find("| StreamETH</title>", start_index)
    name = text[start_index:end_index]

    return mp4Url, name


def download_mp4_and_convert_to_mp3(url):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Download the MP4 file
    response = requests.get(url, allow_redirects=True)
    response.raise_for_status()

    # Save the MP4 file
    mp4_file = os.path.join(output_dir, f"{randomNumber}.mp4")
    with open(mp4_file, "wb") as file:
        file.write(response.content)

    # Convert MP4 to MP3 using pydub
    audio = AudioSegment.from_file(mp4_file, format="mp4")
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")
    audio.export(mp3_file, format="mp3")

    os.remove(mp4_file)

    return mp3_file


def convertStreameth(streamethUrl, forceRefresh):
    inputSource = "StreamEth"
    mp4Url, name = getMp4UrlAndName(streamethUrl)
    id = "".join(char for char in mp4Url if char.isalnum())
    id += "_" + "".join(char for char in name if char.isalnum())
    gistUrl = utilities.getGistUrl(id)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file = download_mp4_and_convert_to_mp3(mp4Url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(audio_chunks)
    gist_url = utilities.writeGist(
        transcript,
        f"{inputSource}: " + name,
        id,
        update=True,
        source_url=streamethUrl,
    )

    return gist_url
