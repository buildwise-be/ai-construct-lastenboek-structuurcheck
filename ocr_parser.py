import os
import google.generativeai as genai
import time
import re
import datetime
import json
import sys
import argparse
from typing import Dict, List, Any

# Configure the Gemini API key
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable not set.")
genai.configure(api_key=api_key)


def upload_to_gemini(path: str, mime_type: str = None) -> genai.File:
    """Uploads the given file to Gemini."""
    print(f"Uploading file: {path}")
    file = genai.upload_file(path, mime_type=mime_type)
    print(f"Uploaded file '{file.display_name}' as: {file.uri}")
    return file


def wait_for_files_active(files: List[genai.File]):
    """Waits for the given files to be active."""
    print("Waiting for file processing...")
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(10)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")
    print("...all files ready.")


def post_process_results(gemini_response: str) -> Dict[str, Any]:
    """Extracts a Python dictionary from the model's response."""
    # This regex is designed to find a Python code block and extract its content.
    code_block_match = re.search(r"```python\s*(.*?)\s*```", gemini_response, re.DOTALL)
    if not code_block_match:
        return None

    code_block = code_block_match.group(1)
    local_vars = {}
    try:
        exec(code_block, {}, local_vars)
        return local_vars.get("chapters") or local_vars.get("secties")
    except Exception as e:
        print(f"Error executing extracted code: {e}")
        return None


def get_pdf_page_count(pdf_path: str) -> int:
    """Gets the total number of pages in a PDF file."""
    try:
        import PyPDF2

        with open(pdf_path, "rb") as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            return len(pdf_reader.pages)
    except Exception as e:
        print(f"Error reading PDF page count: {e}")
        return 0


def generate_toc_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """Generates a Table of Contents dictionary from a given PDF file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found at: {pdf_path}")

    # Model and generation configuration
    generation_config = {
        "temperature": 0.5,
        "top_p": 0.95,
        "top_k": 40,
        "max_output_tokens": 16384,
        "response_mime_type": "text/plain",
    }
    system_instruction = """
    You are given a technical PDF document. Your task is to identify all chapters and sections,
    using the GLOBAL PDF page numbers. For each entry, record the numbering, title, and the
    precise start and end page numbers. The final output must be a nested Python dictionary.
    """
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        generation_config=generation_config,
        system_instruction=system_instruction,
    )

    # Upload and process the file
    uploaded_file = upload_to_gemini(pdf_path, mime_type="application/pdf")
    wait_for_files_active([uploaded_file])
    total_pages = get_pdf_page_count(pdf_path)
    if total_pages == 0:
        return None

    chat_session = model.start_chat(
        history=[{"role": "user", "parts": [uploaded_file]}]
    )

    # Use a single, comprehensive prompt
    initial_prompt = (
        "Analyze the entire document and identify all main chapters (e.g., 00, 01) and their nested sections "
        "(e.g., 01.10, 01.10.01). For each, determine the accurate start and end page numbers based on the "
        "global PDF page count. The end page is the page right before the next section begins. "
        "Return the result as a single, complete Python dictionary."
    )

    print("Sending initial prompt to Gemini...")
    response = chat_session.send_message(initial_prompt)
    chapters_dict = post_process_results(response.text)

    # A simple validation can be added here if needed

    return chapters_dict


def save_results(chapters_dict: Dict[str, Any], input_filename: str):
    """Saves the generated ToC to a JSON file in the ocroutput directory."""
    input_base = os.path.splitext(os.path.basename(input_filename))[0]
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a structured output directory
    output_dir = os.path.join(
        "ocroutput", f"pipeline_run_{timestamp}_{input_base}", "toc_output"
    )
    os.makedirs(output_dir, exist_ok=True)

    json_filename = os.path.join(output_dir, "chapters.json")
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(chapters_dict, f, indent=4, ensure_ascii=False)

    print(f"Successfully saved ToC to: {json_filename}")
    # You can return the path if the main app needs to know where it was saved
    return json_filename


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a Table of Contents from a PDF using Gemini."
    )
    parser.add_argument(
        "pdf_path", help="The absolute path to the PDF file to be processed."
    )
    args = parser.parse_args()

    try:
        toc = generate_toc_from_pdf(args.pdf_path)
        if toc:
            save_results(toc, args.pdf_path)
    except Exception as e:
        print(f"An error occurred during the process: {e}", file=sys.stderr)
        sys.exit(1)
