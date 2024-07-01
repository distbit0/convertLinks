import yt_dlp
import time
from pydub import AudioSegment
from openai import OpenAI
import random
import utilities
import os
from dotenv import load_dotenv
from math import ceil
import pysnooper

load_dotenv()


def download_youtube_video_as_mp3(url):
    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    browserName = utilities.getConfig()["browserName"]
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
        "cookiesfrombrowser": [browserName],
    }

    # Download the video using yt-dlp
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        title = info_dict["title"]
        YTduration = info_dict["duration"]
        print("youtube duration", YTduration)
        if YTduration < 60 * 5:
            print("video too short, returning original url")
            return None, None, None
        info_dict = ydl.extract_info(url, download=True)

    # Get the downloaded MP3 file path
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")

    return mp3_file, title


def transcribeYt(inputSource, inputUrl, audio_chunks, title):
    client = OpenAI()
    markdown_transcript = f"[Original {inputSource}]({inputUrl})\n\n"
    sumOfPrevChunkDurations = 0
    for i, chunk_filename in enumerate(audio_chunks):
        grouped_segments = []
        currentGroup = []
        print("transcribing chunk", i + 1, "of", len(audio_chunks))
        audio_file = open(chunk_filename, "rb")
        audio_segment = AudioSegment.from_file(chunk_filename, format="mp3")
        chunk_duration = len(audio_segment) / 1000  # Duration in seconds
        prompt = (
            "Continuation of informative/technical video (might begin mid-sentence): "
            if i > 0
            else "Welcome to this technical episode. "
        )
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            language="en",
            response_format="verbose_json",
            timestamp_granularities=["segment"],
            prompt=prompt,
        )
        for j, segment in enumerate(transcript.segments):
            segment["start"] += sumOfPrevChunkDurations
            currentGroup.append(segment)
            if j % 6 == 0:
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
            markdown_transcript += (
                f"[{start_time}]({inputUrl}&t={int(start_time)}): {segment['text']}\n\n"
            )

    print("sumOfPrevChunkDurations", sumOfPrevChunkDurations)

    # Delete all the temporary mp3 files
    for file in audio_chunks:
        os.remove(file)

    return markdown_transcript


# @pysnooper.snoop()
def convertYoutube(video_url, forceRefresh):
    if "streameth" in video_url:
        return
    inputSource = "YT video"
    videoId = video_url.split("v=")[-1].split("&")[0]
    video_url = f"https://www.youtube.com/watch?v={videoId}"
    gistUrl = utilities.getGistUrl(videoId)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file, title = download_youtube_video_as_mp3(video_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    transcript = transcribeYt(inputSource, video_url, audio_chunks, title)
    gist_url = utilities.writeGist(
        transcript, f"{inputSource}: " + title, videoId, update=True
    )

    return gist_url
