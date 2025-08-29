import os
import sys
import argparse
import datetime
import json
import re
from dotenv import load_dotenv
from llama_parse import LlamaParse

def parse_pdf_with_llamaparse(pdf_path: str):
    """
    Parses a PDF using LlamaParse and saves the structured content.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    # Prioritize environment variable, then fall back to .env file
    load_dotenv() 
    api_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not api_key:
        raise ValueError(
            "LLAMA_CLOUD_API_KEY not found as an environment variable or in .env file."
        )

    # Initialize the parser
    # We will need to determine the best result_type later.
    # For now, let's start with "markdown" as it's structured.
    parser = LlamaParse(
        api_key=api_key,
        result_type="markdown",
        verbose=True,
    )

    print(f"Starting PDF parsing with LlamaParse for: {pdf_path}")
    documents = parser.load_data(pdf_path)
    print("PDF parsing completed.")

    if documents:
        parsed_content = documents[0].text
        # New: Convert markdown to the required JSON structure
        json_output = convert_markdown_to_json(parsed_content)
        save_parsed_output(json_output, pdf_path)
    else:
        print("LlamaParse returned no documents.", file=sys.stderr)


def convert_markdown_to_json(markdown_text: str) -> dict:
    """
    Converts markdown text from LlamaParse into the specific JSON format
    required by the task placement analyzer.
    """
    print("Converting parsed markdown to JSON...")
    chapters = {}
    current_chapter = None
    
    # Regex to identify chapter headings like '## 01.20 ...' or '# 00 ...'
    # This is a basic assumption and may need to be refined.
    chapter_pattern = re.compile(r"^(#{1,3})\s+([0-9\.]+)\s+(.*)")

    for line in markdown_text.split('\n'):
        match = chapter_pattern.match(line)
        if match:
            # New chapter found
            level, chapter_num, title = match.groups()
            current_chapter = chapter_num.strip()
            chapters[current_chapter] = {
                "title": title.strip(),
                "text": "",
                # Placeholder page numbers as LlamaParse markdown doesn't provide them
                "start_page": 1, 
                "end_page": 1,
                "character_count": 0
            }
        elif current_chapter:
            # Append content to the current chapter
            chapters[current_chapter]["text"] += line + "\n"

    # Post-process to clean up text and calculate char counts
    for chapter_num, data in chapters.items():
        data["text"] = data["text"].strip()
        data["character_count"] = len(data["text"])

    print(f"Successfully converted markdown to {len(chapters)} chapters in JSON format.")
    return chapters


def save_parsed_output(content: dict, input_filename: str):
    """
    Saves the parsed output to a JSON file in the ocroutput directory.
    This now saves the JSON file that the main app expects.
    """
    input_base = os.path.splitext(os.path.basename(input_filename))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # The main app expects this specific directory structure and filename
    output_dir = os.path.join(
        "ocroutput", f"pipeline_run_{timestamp}_{input_base}", "final_combined_output"
    )
    os.makedirs(output_dir, exist_ok=True)
    
    # The main app is hardcoded to look for this filename.
    output_filename = os.path.join(output_dir, "chapters_with_text_v3.json")
    
    with open(output_filename, "w", encoding="utf-8") as f:
        # The main app expects a dictionary, not a list of chapters.
        json.dump(content, f, indent=4, ensure_ascii=False)
    
    print(f"Successfully saved structured JSON to: {output_filename}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse a PDF document using LlamaParse."
    )
    parser.add_argument(
        "pdf_path", help="The absolute path to the PDF file to be processed."
    )
    args = parser.parse_args()

    try:
        parse_pdf_with_llamaparse(args.pdf_path)
    except Exception as e:
        print(f"An error occurred during the parsing process: {e}", file=sys.stderr)
        sys.exit(1)
