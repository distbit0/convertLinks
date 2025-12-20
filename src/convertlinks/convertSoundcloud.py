import time
import os
import random
from pathlib import Path

from dotenv import load_dotenv
from sclib import SoundcloudAPI, Track

from . import utilities

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[2]


def download_podcast_episode(url):
    api = SoundcloudAPI()
    track = api.resolve(url)
    durationSeconds = track.full_duration / 1000
    if durationSeconds < 600:
        return None, None

    if not isinstance(track, Track):
        return None, None

    # Set the output directory relative to the script's location
    output_dir = REPO_ROOT / "tmp"
    os.makedirs(output_dir, exist_ok=True)
    currentTime = time.time()
    randomNumber = str(currentTime) + "_" + str(random.randint(1000000000, 9999999999))

    # Save the episode audio to a file
    mp3_file = output_dir / f"{randomNumber}.mp3"
    with open(mp3_file, "wb+") as file:
        track.write_mp3_to(file)

    return str(mp3_file), track.title


def convertSoundcloud(episode_url, forceRefresh):
    episodeId = episode_url.split("/")[-1]
    gistUrl = utilities.get_gist_url_for_guid(episodeId)
    if gistUrl and not forceRefresh:
        return gistUrl
    mp3_file, title = download_podcast_episode(episode_url)
    audio_chunks = utilities.chunk_mp3(mp3_file)
    if not audio_chunks:
        return None
    inputSource = "SC"
    transcript = utilities.transcribe_mp3(audio_chunks)
    gist_url = utilities.writeGist(
        transcript,
        f"{inputSource}: " + title,
        episodeId,
        update=True,
        source_url=episode_url,
    )

    return gist_url
