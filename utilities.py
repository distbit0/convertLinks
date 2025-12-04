import sys
from pydub import AudioSegment
from math import ceil
from openai import OpenAI
import time
from os import path
import json
import os
import re
import random
import hashlib
from pathlib import Path
from typing import Callable, List, Mapping, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger


def getAbsPath(relPath):
    basepath = path.dirname(__file__)
    fullPath = path.abspath(path.join(basepath, relPath))
    return fullPath


def getConfig():
    configFileName = getAbsPath("config.json")
    with open(configFileName) as config:
        config = json.loads(config.read())
    return config


sys.path.append(getConfig()["gistWriteDir"])
from writeGist import writeContent, getGistUrl


LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "utilities.log",
    rotation="256 KB",
    retention=5,
    enqueue=True,
)

TMP_DIR = Path(__file__).parent / "tmp"
TMP_DIR.mkdir(exist_ok=True)

MODEL_NAME = "gpt-5.1"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
DEFAULT_SUMMARISE = False


class ForecastError(Exception):
    pass


def set_default_summarise(flag: bool) -> None:
    global DEFAULT_SUMMARISE
    DEFAULT_SUMMARISE = bool(flag)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path_for(text: str) -> Path:
    digest = _hash_text(text)
    return TMP_DIR / f"{digest}.summary.txt"


def _call_with_retry(
    *, client_factory: Callable[[], OpenAI], messages: List[Mapping[str, str]]
) -> str:
    """Minimal retry wrapper for Responses API with web search enabled."""
    last_err: Optional[Exception] = None
    client = client_factory()
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.responses.create(
                model=MODEL_NAME,
                input=messages,
                reasoning={"effort": "medium"},
            )
            content = resp.output_text
            if not content:
                raise ForecastError("Empty response from model.")
            return content
        except Exception as exc:  # noqa: PERF203 (retries are bounded)
            last_err = exc
            logger.warning(
                "GPT call failed (attempt {}/{}): {}", attempt, MAX_RETRIES, exc
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise ForecastError(f"GPT call failed after retries: {last_err}")


def _summarise_markdown(text: str) -> str:
    cache_path = _cache_path_for(text)
    if cache_path.exists():
        return cache_path.read_text()

    messages = [
        {
            "role": "user",
            "content": (
                "Summarize the following markdown into a bullet digest."
                "Avoid embellishment:\n\n"
                "Instructions for summarising conversations:\n\n"
                "Preserve links, interesting technical/detailed discussions, conclusions, problems, solutions, points of disagreement, critiques, novel ideas, insights and explanations. Ignore chit chat/throw away comments, chatter, socialising, noise, random news, advertisements, content-less discussion etc. Do not leave things out just because there might be a lot of messages."
                "Instructions for summarising other text:\n\n"
                "Preserve all arguments, explanations, conclusions, novel ideas, insights, important context, contrarian takes, mechanistic details, rationales, implications. Keep succinct while also easy to follow."
                "\n\nText:\n\n"
                f"{text}"
            ),
        }
    ]

    summary = _call_with_retry(
        client_factory=lambda: OpenAI(api_key=os.getenv("OPENAI_API_KEY")),
        messages=messages,
    ).strip()

    cache_path.write_text(summary)
    return summary


def writeGist(
    text,
    name,
    guid=None,
    gist_id=None,
    update=True,
    summarise=None,
    source_url: str | None = None,
):
    actual_summarise = DEFAULT_SUMMARISE if summarise is None else bool(summarise)
    adjusted_guid = f"{guid}_summary" if actual_summarise and guid else guid

    text_to_write = _summarise_markdown(text) if actual_summarise else text
    if source_url:
        text_to_write = f"[Original]({source_url})\n\n{text_to_write}"

    deleteMp3sOlderThan(60 * 60 * 12, getAbsPath("tmp/"))
    if not update:
        gistUrl = getGistUrl(adjusted_guid)
        if gistUrl:
            return gistUrl
    unixTime = str(int(time.time()))
    randomNumber = str(random.randint(1000000000, 9999999999))
    tmpFile = getAbsPath(f"tmp/{unixTime}.{randomNumber}.txt")
    with open(tmpFile, "w") as f:
        f.write(text_to_write)
    gistUrl = "https://gist.github.com/" + gist_id if gist_id else None
    gistUrl = writeContent(gistUrl, adjusted_guid, name, tmpFile)
    os.remove(tmpFile)
    if "https://gist.github.com/" in gistUrl:
        return gistUrl.strip()
    else:
        return None


def deleteMp3sOlderThan(maxAgeSeconds, output_dir):
    files = os.listdir(output_dir)
    for file in files:
        if file.split(".")[-1] in ["mp3", "webm", "part", "mp4", "txt"]:
            filePath = os.path.join(output_dir, file)
            fileName = filePath.split("/")[-1].split(".")[0]
            if fileName.count("_") == 3:
                creationTime = int(fileName.split("_")[0])
            else:
                creationTime = os.path.getctime(filePath)
            if time.time() - creationTime > maxAgeSeconds:
                print("deleting file", filePath)
                os.remove(filePath)


def chunk_mp3(mp3_file):
    max_size_mb = 0.8
    randomNumber = mp3_file.split("/")[-1].split(".")[0]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "tmp")
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

    return file_paths


### might be worthwhile to modify this so it includes timestamps in the output even if they are not clickable
def transcribe_mp3_chunk(client, chunk_filename, chunk_index, total_chunks):
    print(f"transcribing chunk {chunk_index + 1} of {total_chunks}")
    with open(chunk_filename, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            language="en",
            response_format="text",
            prompt=(
                "Continuation of audio (might begin mid-sentence): "
                if chunk_index > 0
                else "Welcome to this technical episode. "
            ),
        )
    return {
        "filename": chunk_filename,
        "transcript": transcript,
        "chunk_index": chunk_index,
    }


def transcribe_mp3(inputSource, inputUrl, audio_chunks):
    client = OpenAI()
    markdown_transcript = ""
    print("transcribing mp3")
    # Process chunks in parallel
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                transcribe_mp3_chunk, client, chunk_filename, i, len(audio_chunks)
            )
            for i, chunk_filename in enumerate(audio_chunks)
        ]

        # Collect results in order
        results = []
        for future in as_completed(futures):
            results.append(future.result())

        # Sort results by chunk index to maintain original order
        results.sort(key=lambda x: x["chunk_index"])

        # Process results in order
        for result in results:
            markdown_transcript += result["transcript"] + "\n\n"

    markdown_transcript = re.sub(
        r"((?:\[^.!?\]+\[.!?\]){6})", r"\1\n\n", markdown_transcript
    )  # split on every 6th sentence

    # Delete all the temporary mp3 files
    for file in audio_chunks:
        os.remove(file)

    return markdown_transcript
