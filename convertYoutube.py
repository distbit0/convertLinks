from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from loguru import logger
import utilities
from dotenv import load_dotenv
import pysnooper
import json

load_dotenv()


def convertYoutube(video_url, forceRefresh):
    if "streameth" in video_url:
        return
    inputSource = "YT video"
    if "/live/" in video_url:
        videoId = video_url.split("/live/")[-1].split("?")[0]
    else:
        videoId = video_url.split("v=")[-1].split("&")[0]
    video_url = f"https://www.youtube.com/watch?v={videoId}"
    gistUrl = utilities.getGistUrl(videoId)
    if gistUrl and not forceRefresh:
        return gistUrl
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(videoId)
        # Prefer English if available
        transcript = None
        for t in transcript_list:
            if t.language_code.startswith("en"):
                transcript = t.fetch()
                break
        if transcript is None:
            transcript = transcript_list.find_transcript(
                [t.language_code for t in transcript_list]
            ).fetch()
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.error(f"No transcript found for video {videoId}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch transcript for video {videoId}: {e}")
        return None
    markdown_transcript = f"[Original]({video_url})\n\n"
    group = []
    group_word_count = 0
    group_start_time = None
    for entry in transcript:
        words = entry.text.replace("\n", " ").split()
        if group_word_count == 0:
            group_start_time = int(entry.start)
        group.append(entry.text.replace("\n", " "))
        group_word_count += len(words)
        if group_word_count >= 80:
            text = " ".join(group)
            markdown_transcript += (
                f"[{group_start_time}]({video_url}&t={group_start_time}): {text}\n\n"
            )
            group = []
            group_word_count = 0
            group_start_time = None
    if group:
        text = " ".join(group)
        markdown_transcript += (
            f"[{group_start_time}]({video_url}&t={group_start_time}): {text}\n\n"
        )
    title = (
        transcript_list._manually_created_transcripts[0].title
        if transcript_list._manually_created_transcripts
        else inputSource
    )
    gist_url = utilities.writeGist(
        markdown_transcript, f"{inputSource}: " + title, videoId, update=True
    )
    return gist_url


if __name__ == "__main__":
    print(convertYoutube("https://www.youtube.com/watch?v=TbRi2jPZxMs", True))
