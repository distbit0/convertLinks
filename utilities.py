import sys
import time
from os import path
import json
import os
import random


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


def deleteMp3sOlderThan(seconds, output_dir):
    files = os.listdir(output_dir)
    for file in files:
        if file.split(".")[-1] in ["mp3", "webm", "part", "mp4", "txt"]:
            filePath = os.path.join(output_dir, file)
            fileAge = time.time() - int(filePath.split("/")[-1].split(".")[0])
            if fileAge > seconds:
                print("deleting file", filePath)
                os.remove(filePath)
