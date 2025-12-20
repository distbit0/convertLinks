import time
from pydub import AudioSegment
import random
import os
from dotenv import load_dotenv
import requests
from pathlib import Path

from . import utilities

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def download_mp4_and_convert_to_mp3(url):
    # Set the output directory relative to the script's location
    output_dir = REPO_ROOT / "tmp"
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Download the MP4 file
    response = requests.get(url, allow_redirects=True)
    response.raise_for_status()

    # Save the MP4 file
    mp4_file = output_dir / f"{randomNumber}.mp4"
    with open(mp4_file, "wb") as file:
        file.write(response.content)

    # Convert MP4 to MP3 using pydub
    audio = AudioSegment.from_file(mp4_file, format="mp4")
    mp3_file = output_dir / f"{randomNumber}.mp3"
    audio.export(mp3_file, format="mp3")

    os.remove(mp4_file)
    return str(mp3_file)


def convertMp4(mp4_url, forceRefresh):
    inputSource = "MP4"
    mp4Id = "".join(char for char in mp4_url if char.isalnum())
    domain = mp4_url.split("/")[2:3][0]
    fileName = mp4Id.split("/")[-1].split(".")[0]
    name = domain + "_" + fileName
    gistUrl = utilities.get_gist_url_for_guid(mp4Id)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file = download_mp4_and_convert_to_mp3(mp4_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(audio_chunks)
    gist_url = utilities.writeGist(
        transcript,
        f"{inputSource}: " + name,
        mp4Id,
        update=True,
        source_url=mp4_url,
    )

    return gist_url
