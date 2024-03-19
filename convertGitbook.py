import re
import requests
import html2text
import utilities
from bs4 import BeautifulSoup
import pysnooper
import sys

sys.path.append("/home/pimania/dev/articleSearchAndSync/src")
from utils import getUrlOfArticle


def getUniqueUrl(url):
    unique_url = url.lower()
    unique_url = re.sub(r"#.*", "", unique_url)  # Remove #comments from the URL
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)
    return unique_url


def fixAndMakeLinksAndImagesAbsolute(markdown_text, base_url):
    uniqueUrl = getUniqueUrl(base_url)
    # Regular expression to find Markdown images. Groups for alt text and URL.
    regex = r"!?\[([^\]]*)\]\(([^\)]+)\)"

    # Ensure the base_url ends with a '/'
    if not base_url.endswith("/"):
        base_url += "/"

    # Function to convert a single match
    def convert_match(match):
        exclamation = ""
        if "!" in match.group(0):
            exclamation = "!"
        alt_text = match.group(1)
        url = match.group(2)
        if len(url.split('"')) > 2:
            url = url.split('"')[0].strip()
        alt_text = alt_text.replace("\n", "")
        url = url.replace("\n", "")
        # Check if the URL is already absolute. If not, prepend the base_url.
        if not url.startswith(("http:", "https:")):
            # Adjust for the case where the URL might already start with a '/'
            if url.startswith("/"):
                url = url[1:]
            url = base_url + url
        outputMd = f"{exclamation}[{alt_text}]({url})"
        return outputMd

    # Replace all matches in the markdown text
    updated_markdown = re.sub(regex, convert_match, markdown_text)
    # remove all non-utf8 characters
    updated_markdown = updated_markdown.encode("utf-8", "ignore").decode("utf-8")

    return updated_markdown.strip("\n")


def find_first_sentence_position(originalText):
    # Regular expression pattern for a sentence
    # pattern = re.compile(r"(?m)^(?:[A-Z])(?:[^*\n]|(?:\n(?!\n)))*(?:[.!?](?=$|\s))") ###original, with ^ at start, which broke some sentences that started with a * before the first word. i.e. lists. maybe these could be explicitly handled
    print(originalText)
    ### modify this function so that it returns an index two lines up from where the sentence is, so that it includes headings
    outputIndex = -1
    nextStartIndex = 0
    pattern = re.compile(r"(?m)(?:[A-Z])(?:[^*\n]|(?:\n(?!\n)))*(?:[.!?:](?=$|\s))")
    while True:
        text = originalText[nextStartIndex:]
        match = pattern.search(text)
        if match:
            hasMoreThanNSpaces = text[match.start() : match.end()].count(" ") >= 4
            indexOfMatch = match.start()
            compressedText = "\n".join(
                [
                    line
                    for line in text[match.end() :].split("\n")
                    if line.strip(" #").strip()
                ]
            )
            nextNLines = "\n".join(compressedText.split("\n")[:11])
            isAlsoSentenceInNextNLines = pattern.search(nextNLines)
            # print(nextTenLines + "\n\n\n\n")
            if isAlsoSentenceInNextNLines != None and hasMoreThanNSpaces:
                outputIndex = indexOfMatch + nextStartIndex
                break
            else:
                print(
                    "skipping because: ",
                    isAlsoSentenceInNextNLines,
                    hasMoreThanNSpaces,
                )
                nextStartIndex += match.end()
        else:
            break

    return outputIndex


def getLastModifiedStringIndex(text):
    endStrings = [
        r"\[Previous.*?\[Next",
        r"\[PREVIOUS.*?\[NEXT",
        r"Last updated on",
        r"Last modified on",
        r"Last modified: .*? ago",
        r"Last modified .*? ago",
        r"Last updated",
        r"Last Updated:",
        r"Last update:",
        r"Updated .*? ago",
        r"\[Edit this page",
        r"Edit this page",
        r"Did this page help you",
        r"^Updated\s+\d{2}\s+\w{3}\s+\d{4}$",
    ]
    for string in endStrings:
        match = re.search(string, text, re.DOTALL)
        if match:
            return match.start()
    return -1


urlPatterns = [
    "\\<\\!\\-\\- Hyperionics-OriginHtml(.*?)-->",
    "\\<\\!\\-\\- Hyperionics-SimpleHtml (.*?)-->",
    "Snapshot-Content-Location: (.*)\n",
]


def main(url):
    if "docs.google.com" in url:
        return url
    unique_url = getUniqueUrl(url)
    # gistUrl = utilities.getGistUrl(unique_url)
    # if gistUrl:
    #     return gistUrl
    if "/home/pimania/ebooks" in url:
        html_content = open(url).read()
        url = getUrlOfArticle(url)
    else:
        issue = False
        try:
            response = requests.get(url)
            if not response.ok:
                issue = True
            html_content = response.text
        except Exception as e:
            print("network error", e, url)
            issue = True
        if issue:
            return False

    soup = BeautifulSoup(html_content, "html.parser")
    title_element = soup.find("title")

    title = title_element.get_text() if title_element else unique_url

    # Convert HTML to Markdown using html2text
    markdown_content = html2text.html2text(html_content)
    firstSentenceIndex = find_first_sentence_position(markdown_content)
    if firstSentenceIndex > 0:
        markdown_content = markdown_content[firstSentenceIndex:]
    else:
        print("could not find first sentence")
        return False

    lastModifiedIndex = getLastModifiedStringIndex(markdown_content)
    if lastModifiedIndex > 0:
        markdown_content = markdown_content[:lastModifiedIndex]

    domainOfUrl = "/".join(url.split("/")[:3])
    markdown_content = fixAndMakeLinksAndImagesAbsolute(markdown_content, domainOfUrl)

    # Add the original URL as a Markdown link at the top of the content
    markdown_content = f"[Link to original]({url})\n\n{markdown_content}"

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_content, "GITB: " + title, unique_url, update=True
    )
    return gist_url
