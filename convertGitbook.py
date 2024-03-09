import re
import requests
import html2text
import utilities


def find_first_sentence_position(text):
    # Regular expression pattern for a sentence
    pattern = re.compile(
        r"(?m)^(?:[A-Z])(?:[^/*\n]|(?:\n(?!\n)))*(?:[.!?](?=$|\s))"  # First sentence pattern
        # r"(\b[A-Z](?:(?![*.\/])[^.?!])*[.?!])"  # Second sentence pattern
    )

    match = pattern.search(text)
    return match.start() if match else -1


def getLastModifiedStringIndex(text):
    # string to find: Last modified * ago
    pattern = r"Last modified \* ago"
    match = re.search(pattern, text)
    return match.start() if match else -1


def main(url):
    # Generate a unique URL for the Gist
    unique_url = url.lower()
    unique_url = re.sub(r"#.*", "", unique_url)  # Remove #comments from the URL
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)

    gistUrl = utilities.getGistUrl(unique_url)
    if gistUrl:
        return gistUrl
    response = requests.get(url)
    if not response.ok:
        return False
    html_content = response.text

    # Convert HTML to Markdown using html2text
    markdown_content = html2text.html2text(html_content)
    print(markdown_content + "\n\n\n\n\n\n\n\n\n\n\n\n\n\n\n")
    firstSentenceIndex = find_first_sentence_position(markdown_content)
    if firstSentenceIndex > 0:
        markdown_content = markdown_content[firstSentenceIndex:]

    lastModifiedIndex = getLastModifiedStringIndex(markdown_content)
    if lastModifiedIndex > 0:
        markdown_content = markdown_content[:lastModifiedIndex]

    # Extract the title from the Markdown content
    title = ""
    lines = markdown_content.split("\n")
    for line in lines:
        if line.startswith("#"):
            title = " ".join(line.split(" ")[1:])
            break

    # Add the original URL as a Markdown link at the top of the content
    markdown_content = f"[Link to Original]({url})\n\n{markdown_content}"

    # Save the Markdown content to a Gist
    gist_url = utilities.writeGist(
        markdown_content, "GITB: " + title, unique_url, update=True
    )

    return gist_url
