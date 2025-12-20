from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)
from loguru import logger
import utilities
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

load_dotenv()


def getTitle(videoId):

    url = f"https://www.youtube.com/watch?v={videoId}"

    # Extracting HTML Code of the Video Page:
    response = requests.get(url)
    html_content = response.text

    # Processing the HTML Code with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Extracting <title> tag's content
    title_tag = soup.find("meta", property="og:title")
    video_title = title_tag["content"] if title_tag else "Title not found"

    return video_title


def convertYoutube(video_url, forceRefresh):
    if "streameth" in video_url:
        return
    inputSource = "YT video"
    if "/live/" in video_url:
        videoId = video_url.split("/live/")[-1].split("?")[0]
    else:
        videoId = video_url.split("v=")[-1].split("&")[0]
    videoId = videoId.split("#")[0]
    video_url = f"https://www.youtube.com/watch?v={videoId}"
    gistUrl = utilities.get_gist_url_for_guid(videoId)
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
    markdown_transcript = ""
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
    try:
        title = getTitle(videoId)
    except Exception as e:
        logger.error(f"Failed to get title for video {videoId}: {e}")
        title = "Title not found"
    gist_url = utilities.writeGist(
        markdown_transcript,
        f"{inputSource}: " + title,
        videoId,
        update=True,
        source_url=video_url,
    )
    return gist_url


if __name__ == "__main__":
    print(convertYoutube("https://www.youtube.com/watch?v=TbRi2jPZxMs", True))
