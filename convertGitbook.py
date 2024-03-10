import re
import requests
import html2text
import utilities
from bs4 import BeautifulSoup
import pysnooper
import sys

sys.path.append("/home/pimania/dev/articleSearchAndSync/src")
from utils import getUrlOfArticle


def convert_markdown_images_to_absolute(markdown_text, base_url):
    # Regular expression to find Markdown images. Groups for alt text and URL.
    regex = r"!\[([^\]]*)\]\((/?[^)]+)\)"

    # Ensure the base_url ends with a '/'
    if not base_url.endswith("/"):
        base_url += "/"

    # Function to convert a single match
    def convert_match(match):
        alt_text = match.group(1)
        url = match.group(2)
        # Check if the URL is already absolute. If not, prepend the base_url.
        if not url.startswith(("http:", "https:")):
            # Adjust for the case where the URL might already start with a '/'
            if url.startswith("/"):
                url = url[1:]
            url = base_url + url
        return f"![{alt_text}]({url})"

    # Replace all matches in the markdown text
    updated_markdown = re.sub(regex, convert_match, markdown_text)

    return updated_markdown


def removeNewLinesFromLinksAndImages(text):
    # Regular expression to match markdown links, capturing text and link separately
    # It's divided into optional image syntax '!', optional text part '[]', and link part '()'
    markdown_link_pattern = r"(!)?\[([^\[\]]*)\]\(((?:[^()\n]|\n(?!\]))*)\)"

    def replace_newlines(match):
        # Replace single newlines within brackets '[]' and parentheses '()'
        text_part = match.group(2).replace("\n", "")
        link_part = match.group(3).replace("\n", "")
        return f'{match.group(1) or ""}[{text_part}]({link_part})'

    # Use re.sub with a function to replace matched parts
    return re.sub(markdown_link_pattern, replace_newlines, text)


def find_first_sentence_position(text):
    # Regular expression pattern for a sentence
    pattern = re.compile(r"(?m)^(?:[A-Z])(?:[^*\n]|(?:\n(?!\n)))*(?:[.!?](?=$|\s))")

    match = pattern.search(text)
    return match.start() if match else -1


def getLastModifiedStringIndex(text):
    # string to find: Last modified * ago
    pattern = r"Last modified .*? ago"
    match = re.search(pattern, text)
    index = match.start() if match else -1
    if index == -1:
        pattern = r"Last updated on"
        match = re.search(pattern, text)
        index = match.start() if match else -1
    if index == -1:
        pattern = r"Last modified on"
        match = re.search(pattern, text)
        index = match.start() if match else -1

    return index


urlPatterns = [
    "\\<\\!\\-\\- Hyperionics-OriginHtml(.*?)-->",
    "\\<\\!\\-\\- Hyperionics-SimpleHtml (.*?)-->",
    "Snapshot-Content-Location: (.*)\n",
]


def main(url):
    if "docs.google.com" in url:
        return url
    # Generate a unique URL for the Gist
    unique_url = url.lower()
    unique_url = re.sub(r"#.*", "", unique_url)  # Remove #comments from the URL
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)

    gistUrl = utilities.getGistUrl(unique_url)
    if gistUrl:
        return gistUrl
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
    # print(markdown_content + "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
    firstSentenceIndex = find_first_sentence_position(markdown_content)
    if firstSentenceIndex > 0:
        markdown_content = markdown_content[firstSentenceIndex:]

    lastModifiedIndex = getLastModifiedStringIndex(markdown_content)
    print(lastModifiedIndex, url)
    if lastModifiedIndex > 0:
        markdown_content = markdown_content[:lastModifiedIndex]

    markdown_content = removeNewLinesFromLinksAndImages(markdown_content)
    domainOfUrl = "/".join(url.split("/")[:3])
    markdown_content = convert_markdown_images_to_absolute(
        markdown_content, domainOfUrl
    )

    # Add the original URL as a Markdown link at the top of the content
    markdown_content = f"[Link to original]({url})\n\n{markdown_content}"

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_content, "GITB: " + title, unique_url, update=True
    )
    return gist_url
