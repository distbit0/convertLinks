import re
import requests
import html2text
import utils


def main(url):
    response = requests.get(url)
    html_content = response.text

    # Convert HTML to Markdown using html2text
    markdown_content = html2text.html2text(html_content)

    # Generate a unique URL for the Gist
    unique_url = url.lower()
    unique_url = re.sub(r"#.*", "", unique_url)  # Remove #comments from the URL
    unique_url = re.sub(r"[^a-z0-9]", "_", unique_url).strip("_")
    unique_url = re.sub(r"_+", "_", unique_url)

    # Extract the title from the Markdown content
    title = ""
    lines = markdown_content.split("\n")
    for line in lines:
        if line.startswith("#"):
            title = " ".join(line.split(" ")[1:])
            break

    # Save the Markdown content to a Gist
    gist_url = utils.writeGist(markdown_content, "GITB: " + title, unique_url)

    return gist_url
