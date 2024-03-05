import sys
from os import path
import json


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
from writeGist import writeContent


def writeGist(text, name, guid=None, gist_id=None):
    tmpFile = getAbsPath("tmp.txt")
    with open(tmpFile, "w") as f:
        f.write(text)
    gistUrl = "https://gist.github.com/" + gist_id if gist_id else None
    gistUrl = writeContent(gistUrl, guid, name, tmpFile)
    if "https://gist.github.com/" in gistUrl:
        return gistUrl.strip()
    else:
        return None
