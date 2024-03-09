import yt_dlp
import time
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
    utilities.deleteMp3sOlderThan(60 * 60 * 12, output_dir)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

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
        YTduration = info_dict["duration"]
        print("youtube duration", YTduration)

    # Get the downloaded MP3 file path
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")

    # Load the MP3 file using pydub
    audio = AudioSegment.from_mp3(mp3_file)

    # Calculate the number of chunks based on the maximum size
    chunk_size_bytes = max_size_mb * 1024 * 1024
    total_chunks = ceil(len(audio) / chunk_size_bytes)

    # Split the audio into chunks
    cumDurOfChunks = 0
    file_paths = []
    for i in range(total_chunks):
        start_time = i * chunk_size_bytes
        end_time = min((i + 1) * chunk_size_bytes, len(audio))
        chunk = audio[start_time:end_time]
        chunk_file = os.path.join(output_dir, f"{randomNumber}_chunk_{i+1}.mp3")
        cumDurOfChunks += len(chunk) / 1000
        chunk.export(chunk_file, format="mp3")
        file_paths.append(chunk_file)

    os.remove(mp3_file)
    print(
        "origCumDurOfChunks",
        cumDurOfChunks,
        "YTduration",
        YTduration,
    )
    videoScalingFactor = int(YTduration) / float(cumDurOfChunks)
    print("videoScalingFactor", videoScalingFactor)

    return file_paths, title, videoScalingFactor


def main(video_url):
    videoId = video_url.split("v=")[-1]
    video_url = f"https://www.youtube.com/watch?v={videoId}"
    youtubeId = video_url.split("v=")[-1].split("&")[0]
    video_url = "https://www.youtube.com/watch?v=" + youtubeId
    gistUrl = utilities.getGistUrl(youtubeId)
    if gistUrl:
        return gistUrl
    audio_chunks, title, videoScalingFactor = download_youtube_video_as_mp3(
        video_url, 0.8
    )
    client = OpenAI()
    markdown_transcript = f"[Original Video]({video_url})\n\n"
    sumOfPrevChunkDurations = 0
    for i, chunk_filename in enumerate(audio_chunks):
        grouped_segments = []
        i = 0
        currentGroup = []
        print("downloading chunk ", i + 1, "of", len(audio_chunks))
        audio_file = open(chunk_filename, "rb")
        audio_segment = AudioSegment.from_file(chunk_filename, format="mp3")
        chunk_duration = len(audio_segment) / 1000  # Duration in seconds
        prompt = (
            "Title: " + title + " Continuation of video (might begin mid-sentence): "
            if i > 0
            else "Welcome to my technical video. "
        )
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            language="en",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            prompt=prompt,
        )
        for segment in transcript.segments:
            segment["start"] += sumOfPrevChunkDurations
            segment["start"] *= videoScalingFactor
            currentGroup.append(segment)
            i += 1
            if i % 6 == 0:
                startTime = currentGroup[0]["start"]
                text = " ".join([segment["text"] for segment in currentGroup])
                grouped_segments.append(
                    {
                        "start": startTime,
                        "text": text,
                    }
                )
                currentGroup = []
        if currentGroup:
            startTime = currentGroup[0]["start"]
            text = " ".join([segment["text"] for segment in currentGroup])
            grouped_segments.append(
                {
                    "start": startTime,
                    "text": text,
                }
            )
        sumOfPrevChunkDurations += chunk_duration

        for segment in grouped_segments:
            start_time = int(segment["start"])
            markdown_transcript += f"[{start_time}]({video_url}&t={int(start_time)}): {segment['text']}\n\n"

    print("sumOfPrevChunkDurations", sumOfPrevChunkDurations)

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_transcript, "YT: " + title, youtubeId, update=True
    )

    # Delete all the temporary mp3 files
    for file in audio_chunks:
        os.remove(file)

    return gist_url
