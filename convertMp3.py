import time
import re
import random
import utilities
import os
from dotenv import load_dotenv
import requests

load_dotenv()


def download_mp3(url):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Download the MP3 file
    response = requests.get(url, allow_redirects=True)
    response.raise_for_status()

    # Save the MP3 file
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")
    with open(mp3_file, "wb") as file:
        file.write(response.content)

    return mp3_file


def convertMp3(mp3_url, forceRefresh):
    identifier = "".join(char for char in mp3_url if char.isalnum())
    domain = mp3_url.split("/")[2:3][0]
    fileName = identifier.split("/")[-1].split(".")[0]
    name = domain + "_" + fileName
    inputSource = "MP3"

    gistUrl = utilities.getGistUrl(identifier)
    if gistUrl and not forceRefresh:
        return gistUrl

    mp3_file = download_mp3(mp3_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(inputSource, mp3_url, audio_chunks)
    gist_url = utilities.writeGist(
        transcript, f"{inputSource}: " + name, identifier, update=True
    )

    return gist_url
