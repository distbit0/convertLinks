import yt_dlp

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


def download_rumble_video_as_mp3(url):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Configure yt-dlp options
    ydl_opts = {
        "format": "mp4-480p",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": os.path.join(output_dir, f"{randomNumber}.%(ext)s"),
    }

    # Download the video using yt-dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        title = info_dict["title"]
        info_dict = ydl.extract_info(url, download=True)

    # Get the downloaded MP3 file path
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")
    return mp3_file, title


#@pysnooper.snoop()
def convertRumble(video_url, forceRefresh):
    inputSource = "Rumble"
    videoId = video_url.split("/")[-1]
    gistUrl = utilities.getGistUrl(videoId)
    if gistUrl and not forceRefresh:
        return gistUrl

    mp3_file, title = download_rumble_video_as_mp3(video_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = utilities.transcribe_mp3(inputSource, video_url, audio_chunks)
    gist_url = utilities.writeGist(
        transcript,
        f"{inputSource}: " + title,
        videoId,
        update=True,
        source_url=video_url,
    )

    return gist_url
