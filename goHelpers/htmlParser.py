import sys
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
    with open(filename, "w") as file:
        file.write(text)


def generate_filename_from_url(url):
    # Split the URL to get the part after '.com'
    parts = url.split(".com")
    if len(parts) > 1:
        # Replace '/' with '_' and remove leading '/'
        parsed_name = parts[1].replace("/", "_").lstrip("_")
        return parsed_name
    parts = url.split(".dev")
    parsed_name = parts[1].replace("/", "_").lstrip("_")
    return parsed_name


def fetchWebData(url,path):
    html_content = fetch_html(url)
    if html_content.startswith("HTTP error occurred:") or html_content.startswith(
        "Other error occurred:"
    ):
        print(html_content)
        return

    processed_text = process_html(html_content)
    # Use the URL to generate the output filename
    parsed_name = generate_filename_from_url(url)
    output_filename =path+"additionalcontext/"+f"{parsed_name}_context.txt"
    save_text_to_file(processed_text, output_filename)
    print(f"Processed text saved to {output_filename}")


# Replace the URL with the actual URL from which you want to fetch and process the HTML content
if __name__ == "__main__":
    if len(sys.argv) != 3:
        logger.error("Usage: python getter.py <directory>")
        sys.exit(1)

    url = sys.argv[1]
    outputdirectory = sys.argv[2]
    
    main(url,outputdirectory)
