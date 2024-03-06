import yt_dlp
from pydub import AudioSegment
from openai import OpenAI
import random
import utilities
import os
from dotenv import load_dotenv
from math import ceil

load_dotenv()


def download_youtube_video_as_mp3(url, max_size_mb):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    randomNumber = str(random.randint(1000000000, 9999999999))

    # Configure yt-dlp options
    ydl_opts = {
        "format": "bestaudio/best",
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
        info_dict = ydl.extract_info(url, download=True)
        title = info_dict["title"]
        youtube_id = info_dict["id"]

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

    return file_paths, title


def main(video_url):
    youtubeId = video_url.split("v=")[-1].split("&")[0]
    gistUrl = utilities.getGistUrl(youtubeId)
    if gistUrl:
        return gistUrl
    audio_chunks, title = download_youtube_video_as_mp3(video_url, 0.8)
    client = OpenAI()
    markdown_transcript = f"[Original Video]({video_url})\n\n"
    for i, chunk_filename in enumerate(audio_chunks):
        audio_file = open(chunk_filename, "rb")
        prompt = markdown_transcript[-224:] if i > 0 else "This is a technical video."
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            prompt=prompt,
        )
        grouped_segments = []
        i = 0
        currentGroup = []
        for segment in transcript.segments:
            currentGroup.append(segment)
            i += 1
            if i % 7 == 0:
                startTime = currentGroup[0]["start"]
                text = " ".join([segment["text"] for segment in currentGroup])
                grouped_segments.append(
                    {
                        "start": startTime,
                        "text": text,
                    }
                )
                currentGroup = []
        # vtt, srt or verbose_json.

        for segment in grouped_segments:
            start_time = int(segment["start"] * 100) / 100
            markdown_transcript += f"[{start_time}]({video_url}&t={int(start_time)}): {segment['text']}\n\n"

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_transcript, "YT: " + title, youtubeId, update=True
    )

    # Delete all the temporary mp3 files
    for file in audio_chunks:
        os.remove(file)

    return gist_url
