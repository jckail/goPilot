import sys
import os
import hashlib
import re
import tempfile
from urllib.parse import urlsplit
import requests
from bs4 import BeautifulSoup


def fetch_html(url):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        return response.text
    except requests.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}"
    except Exception as err:
        return f"Other error occurred: {err}"


def extract_text_with_formatting(element):
    """Recursively extract text from the HTML element, maintaining basic formatting."""
    text_parts = []
    for sub_element in element.descendants:
        if isinstance(sub_element, str):
            text_parts.append(sub_element.strip())
        elif sub_element.name in ["p", "div", "br"] and text_parts:
            # Add a newline for block elements (only if there is text already)
            text_parts.append("\n")
    return " ".join(text_parts).strip()


def process_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove the index and "Jump to ..." sections
    for section in soup.find_all("section", class_="Documentation-index"):
        section.decompose()

    for jump_to_nav in soup.find_all(
        lambda tag: tag.name == "nav" and "Jump to ..." in tag.text
    ):
        jump_to_nav.decompose()

    # Add new lines around "Documentation-declaration" divs
    for div in soup.find_all("div", class_="Documentation-declaration"):
        div.insert_before("\n")
        div.insert_after("\n")

    # Process the text for 'func' lines
    modified_html_text = extract_text_with_formatting(soup.body)
    lines = modified_html_text.split("\n")
    processed_lines = []

    for line in lines:
        processed_line = line.replace(" ¶", "").strip()
        if processed_line.startswith("func"):
            processed_lines.append("\n" + processed_line)
        else:
            processed_lines.append(processed_line)

    return "\n".join(processed_lines)


def save_text_to_file(text, filename):
    """Publish complete UTF-8 context atomically, retaining old bytes on failure."""
    descriptor, staging = tempfile.mkstemp(
        prefix=".html-context-", suffix=".tmp", dir=os.path.dirname(filename) or "."
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            descriptor = None  # The file object now owns the descriptor.
            file.write(text)
        os.replace(staging, filename)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(staging)
        except FileNotFoundError:
            pass


def generate_filename_from_url(url):
    """Return a bounded portable stem, preserving exact URL identity in its digest."""
    parts = urlsplit(url)
    readable = (parts.hostname or "web") + parts.path
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", readable).strip("-_")[:80] or "web"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return f"web-{slug}-{digest}"


def fetchWebData(url,path):
    html_content = fetch_html(url)
    if html_content.startswith("HTTP error occurred:") or html_content.startswith(
        "Other error occurred:"
    ):
        print(" ".join(html_content.split())[:500], file=sys.stderr)
        return False

    processed_text = process_html(html_content)
    # Use the URL to generate the output filename
    parsed_name = generate_filename_from_url(url)
    output_directory = os.path.join(path, "additionalcontext")
    output_filename = os.path.join(output_directory, f"{parsed_name}_context.txt")
    os.makedirs(output_directory, exist_ok=True)
    save_text_to_file(processed_text, output_filename)
    print(f"Processed text saved to {output_filename}")
    return True


# Replace the URL with the actual URL from which you want to fetch and process the HTML content
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python htmlParser.py <URL> <helper-directory>", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    goHelperDirectory = sys.argv[2]
    
    try:
        if fetchWebData(url, goHelperDirectory) is False:
            sys.exit(1)
    except Exception as error:
        diagnostic = " ".join(str(error).split())[:500]
        print(f"HTML context failed: {diagnostic}", file=sys.stderr)
        sys.exit(1)
