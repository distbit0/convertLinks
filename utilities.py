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
from concurrent.futures import ThreadPoolExecutor, as_completed


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


def writeGist(text, name, guid=None, gist_id=None, update=True):
    deleteMp3sOlderThan(60 * 60 * 12, getAbsPath("tmp/"))
    if not update:
        gistUrl = getGistUrl(guid)
        if gistUrl:
            return gistUrl
    unixTime = str(int(time.time()))
    randomNumber = str(random.randint(1000000000, 9999999999))
    tmpFile = getAbsPath(f"tmp/{unixTime}.{randomNumber}.txt")
    with open(tmpFile, "w") as f:
        f.write(text)
    gistUrl = "https://gist.github.com/" + gist_id if gist_id else None
    gistUrl = writeContent(gistUrl, guid, name, tmpFile)
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
        "chunk_index": chunk_index
    }

def transcribe_mp3(inputSource, inputUrl, audio_chunks):
    client = OpenAI()
    markdown_transcript = f"[Original]({inputUrl})\n\n"
    
    # Process chunks in parallel
    with ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(
                transcribe_mp3_chunk,
                client,
                chunk_filename,
                i,
                len(audio_chunks)
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
