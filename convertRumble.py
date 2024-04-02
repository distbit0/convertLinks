import yt_dlp
import pysnooper
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


def download_rumble_video_as_mp3(url, max_size_mb):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    utilities.deleteMp3sOlderThan(60 * 60 * 12, output_dir)
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

    # Load the MP3 file using pydub
    audio = AudioSegment.from_mp3(mp3_file)

    # Calculate the number of chunks based on the maximum size
    chunk_size_bytes = max_size_mb * 1024 * 1024
    total_chunks = ceil(len(audio) / chunk_size_bytes)

    # Split the audio into chunks
    file_paths = []
    for i in range(total_chunks):
        start_time = i * chunk_size_bytes
        end_time = min((i + 1) * chunk_size_bytes, len(audio))
        chunk = audio[start_time:end_time]
        chunk_file = os.path.join(output_dir, f"{randomNumber}_chunk_{i+1}.mp3")
        chunk.export(chunk_file, format="mp3")
        file_paths.append(chunk_file)

    os.remove(mp3_file)
    return file_paths, title


@pysnooper.snoop()
def convertRumble(video_url):
    videoId = video_url.split("/")[-1]
    gistUrl = utilities.getGistUrl(videoId)
    if gistUrl:
        return gistUrl

    audio_chunks, title = download_rumble_video_as_mp3(video_url, 0.8)

    client = OpenAI()
    markdown_transcript = f"[Original Rumble Video]({video_url})\n\n"
    for i, chunk_filename in enumerate(audio_chunks):
        print("transcribing chunk", i + 1, "of", len(audio_chunks))
        with open(chunk_filename, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                language="en",
                response_format="text",
                prompt=(
                    "Title: "
                    + title
                    + " Continuation of audio (might begin mid-sentence): "
                    if i > 0
                    else "Welcome to this Rumble video content. "
                ),
            )
        markdown_transcript += transcript + "\n\n"

    markdown_transcript = re.sub(
        r"((?:\[^.\!?\]+\[.\!?\]){6})", r"\1\n\n", markdown_transcript
    )

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_transcript, "Rumble: " + title, videoId, update=True
    )

    # Delete all the temporary mp3 files
    for file in audio_chunks:
        os.remove(file)

    return gist_url
