import time
from pydub import AudioSegment
import re
import random
import utilities
import os
from dotenv import load_dotenv
from math import ceil
from openai import OpenAI
from sclib import SoundcloudAPI, Track, Playlist

load_dotenv()


def download_podcast_episode(url):
    api = SoundcloudAPI()
    track = api.resolve(url)
    durationSeconds = track.full_duration / 1000
    if durationSeconds < 600:
        return None, None

    if not isinstance(track, Track):
        return None, None

    # Set the output directory relative to the script's location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Save the episode audio to a file
    mp3_file = os.path.join(output_dir, f"{randomNumber}.mp3")
    with open(mp3_file, "wb+") as file:
        track.write_mp3_to(file)

    return mp3_file, track.title


def convertSoundcloud(episode_url, forceRefresh):
    episodeId = episode_url.split("/")[-1]
    gistUrl = utilities.getGistUrl(episodeId)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file, title = download_podcast_episode(episode_url, 0.8)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    if not audio_chunks:
        return None
    inputSource = "SC"
    transcript = utilities.transcribe_mp3(inputSource, episode_url, audio_chunks)
    gist_url = utilities.writeGist(
        transcript, f"{inputSource}: " + title, episodeId, update=True
    )

    return gist_url
