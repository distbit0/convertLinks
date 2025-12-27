from pydub import AudioSegment
from math import ceil
from openai import OpenAI
import time
import json
import os
import re
import random
import hashlib
from pathlib import Path
from typing import Callable, List, Mapping, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from loguru import logger

REPO_ROOT = Path(__file__).resolve().parents[1]


def getAbsPath(relPath):
    return str((REPO_ROOT / relPath).resolve())


def getConfig():
    configFileName = REPO_ROOT / "config.json"
    with open(configFileName) as config:
        config = json.loads(config.read())
    return config


def build_guid_from_url(url: str) -> str:
    unique_url = url.lower()
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)
    return unique_url


LOG_DIR = REPO_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.add(
    LOG_DIR / "utilities.log",
    rotation="256 KB",
    retention=5,
    enqueue=False,
)

TMP_DIR = REPO_ROOT / "tmp"
TMP_DIR.mkdir(exist_ok=True)

from write_gist import writeContent, getGistUrl

MODEL_NAME = "gpt-5.1"
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2
DEFAULT_SUMMARISE = False


class ForecastError(Exception):
    pass


def set_default_summarise(flag: bool) -> None:
    global DEFAULT_SUMMARISE
    DEFAULT_SUMMARISE = bool(flag)


def get_gist_url_for_guid(
    guid: str | None, summarise: bool | None = None
) -> str | None:
    if not guid:
        return None
    actual_summarise = DEFAULT_SUMMARISE if summarise is None else bool(summarise)
    adjusted_guid = f"{guid}_summary" if actual_summarise else guid
    return getGistUrl(adjusted_guid)


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

    if not text.strip():
        return ""

    chunk_size = 100_000
    lines = text.splitlines()
    chunks: list[str] = []
    current_lines: list[str] = []
    current_word_count = 0

    for line in lines:
        line_word_count = len(line.split())
        # If a single line exceeds the chunk size, put it in its own chunk to avoid mid-line splits.
        if line_word_count > chunk_size:
            if current_lines:
                chunks.append("\n".join(current_lines).strip())
                current_lines = []
                current_word_count = 0
            chunks.append(line)
            continue

        if current_lines and current_word_count + line_word_count > chunk_size:
            chunks.append("\n".join(current_lines).strip())
            current_lines = []
            current_word_count = 0

        current_lines.append(line)
        current_word_count += line_word_count

    if current_lines:
        chunks.append("\n".join(current_lines).strip())

    total_chunks = len(chunks)

    def summarise_single_chunk(chunk_text: str, index: int) -> str:
        messages = [
            {
                "role": "user",
                "content": (
                    "Summarize the following markdown into a bullet digest."
                    "Translate any foreign language text to English."
                    "Avoid embellishment:\n\n"
                    "Instructions for summarising conversations:\n\n"
                    "Preserve links, interesting technical/detailed discussions, conclusions, problems, solutions, points of disagreement, critiques, novel ideas, insights and explanations. Ignore chit chat/throw away comments, chatter, socialising, noise, random news, advertisements, content-less discussion etc. Do not leave things out just because there might be a lot of messages."
                    "Instructions for summarising other text:\n\n"
                    "Preserve all arguments, explanations, problems, conclusions, novel ideas, insights, points of disagreements, contradictions, important context, contrarian takes, critiques, mechanistic details, rationales, implications. Keep succinct while also easy to follow."
                    f"\n\nChunk {index + 1} of {total_chunks}:\n\n"
                    f"{chunk_text}"
                ),
            }
        ]

        return _call_with_retry(
            client_factory=lambda: OpenAI(api_key=_get_openai_api_key()),
            messages=messages,
        ).strip()

    logger.info(
        "Summarising markdown in {} chunk(s) of up to {} words, split on newline boundaries",
        total_chunks,
        chunk_size,
    )

    with ThreadPoolExecutor() as executor:
        future_to_index = {
            executor.submit(summarise_single_chunk, chunk, idx): idx
            for idx, chunk in enumerate(chunks)
        }

        ordered_summaries: list[str] = ["" for _ in chunks]
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            ordered_summaries[idx] = future.result()

    summary = "\n\n".join(ordered_summaries)

    cache_path.write_text(summary)
    return summary


def _summarise_gist_takeaways(text: str) -> str:
    if not text.strip():
        return ""

    messages = [
        {
            "role": "user",
            "content": (
                "Extract the most interesting/novel/important conclusions, take-aways, implications and findings from the text."
                "Write a very succinct dot-point list. Max 6 bullet points. Max 12 words per bullet."
                "Translate any foreign language text to English."
                "Do not include background, narration, or procedural detail unless it is itself a takeaway."
                # "After the bullets, add a single line with an information-density rating based on"
                # " the percent of the text that is repetition/re-statement/padding/re-iteration"
                # " instead of new ideas, arguments, explanations, problems, conclusions, novel ideas,"
                # " insights, points of disagreements, contradictions, important context, contrarian takes,"
                # " critiques, mechanistic details, rationales, implications."
                # "Use this exact format for the rating line: 'Info density: X/10'."
                # "Choose X from 1-10, where 10 = ~0% repetition/padding, 5 = ~50% repetition/padding,"
                # " and 1 = ~90-100% repetition/padding."
                "After the bullets, add a single line estimating what percentage of the"
                " arguments, problems, conclusions, explanations, novel ideas, points of disagreement,"
                " contrarian takes, critiques, mechanistic details,"
                " rationales, implications from the text could not be included in the bullets. i.e. not including waffling/repetition/re-statement/padding."
                "Use this exact format for the percentage line: 'Missed content: X%'."
                "Then add one line (under 25 words) explaining what the reader misses, which fits the above criteria, in as much detail as possible within the word limit, if the reader only reads the bullets and skips reading the full text. Make sure it is useful/accurate and not overly positive or overly critical, to facilitate an informed decision."
                "Then add one line (under 25 words) that gives the most compelling yet truthful/accurate critique/explanation/devil's-advocate for why it's not worth reading the rest."
                "Return only bullets and the added lines, no heading or preamble."
                "Use '-' as the bullet marker."
                "If the text contains no conclusions, take-aways, or findings, return a single bullet that says:"
                "'- No clear conclusions, take-aways, or findings.'\n\n"
                f"{text}"
            ),
        }
    ]

    logger.info("Generating gist takeaways summary")
    return _call_with_retry(
        client_factory=lambda: OpenAI(api_key=_get_openai_api_key()),
        messages=messages,
    ).strip()


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

    takeaways_summary = _summarise_gist_takeaways(text)
    text_to_write = _summarise_markdown(text) if actual_summarise else text
    if takeaways_summary:
        text_to_write = (
            "## Conclusions / Takeaways\n" f"{takeaways_summary}\n\n{text_to_write}"
        )
    if source_url:
        text_to_write = (
            f"[Original]({source_url})\n\n{text_to_write}\n\n[Original]({source_url})"
        )

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
        if file.split(".")[-1] in ["mp3", "m4a", "webm", "part", "mp4", "txt"]:
            filePath = os.path.join(output_dir, file)
            fileName = filePath.split("/")[-1].split(".")[0]
            if fileName.count("_") == 3:
                creationTime = int(fileName.split("_")[0])
            else:
                creationTime = os.path.getctime(filePath)
            if time.time() - creationTime > maxAgeSeconds:
                logger.info("Deleting file {}", filePath)
                os.remove(filePath)


def chunk_mp3(mp3_file):
    max_size_mb = 0.8
    randomNumber = mp3_file.split("/")[-1].split(".")[0]
    output_dir = REPO_ROOT / "tmp"
    output_dir.mkdir(exist_ok=True)
    audio_ext = os.path.splitext(mp3_file)[1].lower().lstrip(".")
    if audio_ext and audio_ext not in {"mp3", "m4a", "mp4"}:
        raise ValueError(f"Unsupported audio extension: {audio_ext}")
    audio = AudioSegment.from_file(mp3_file, format=audio_ext or None)

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
    logger.info("Transcribing chunk {} of {}", chunk_index + 1, total_chunks)
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


def _get_openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set.")
    return api_key


def transcribe_mp3(audio_chunks):
    client = OpenAI(api_key=_get_openai_api_key())
    markdown_transcript = ""
    logger.info("Transcribing mp3")
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
