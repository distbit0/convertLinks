import re
import requests
import html2text
import utilities


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
        markdown_content, "GITB: " + title, unique_url, update=False
    )

    return gist_url
