#!/usr/bin/env python
"""
Module to generate a hierarchical Table of Contents (TOC) from a PDF using an LLM,
extract text for each section, and generate AI summaries for each section.

Combines LLM-based TOC generation (adapted from examples/main_script.py)
with text summarization.
"""

import os
import sys
import json
import argparse
import logging
from dotenv import load_dotenv
import fitz  # PyMuPDF
import re
import time
import base64 # Although imported, base64 is not explicitly used in the final logic

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, SafetySetting, Part

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Define model names via environment variables with defaults
VISION_MODEL_NAME = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-001")
SUMMARIZER_MODEL_NAME = os.getenv("GEMINI_SUMMARIZER_MODEL", "gemini-2.0-flash-001") # Using flash for potentially faster/cheaper summaries

# Summarizer Config (Consider making this configurable if needed)
SUMMARIZER_GENERATION_CONFIG = {
    "max_output_tokens": 400, # Increased slightly for potentially more detailed summaries
    "temperature": 0.6, # Slightly lower temp for more focused summaries
    "top_p": 0.95,
}
SUMMARIZER_SAFETY_SETTINGS = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    # Add other categories as needed, copying the pattern
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
]

# Vision Model Config (Using default generation config, adjust if needed)
VISION_GENERATION_CONFIG = {
    "max_output_tokens": 8192, # Allow large output for complex TOCs
    "temperature": 0.2,      # Lower temperature for more deterministic TOC structure
    "top_p": 0.95,
}
# Using same safety settings for Vision model, adjust if specific needs differ
VISION_SAFETY_SETTINGS = SUMMARIZER_SAFETY_SETTINGS

# Global variables for initialized models
vision_model = None
summarizer_model = None

# --- Initialization ---
def initialize_llm_models():
    """Initializes both the Vision and Summarizer Vertex AI models."""
    global vision_model, summarizer_model
    if vision_model and summarizer_model:
        logger.debug("Models already initialized.")
        return True

    try:
        load_dotenv() # Load environment variables from .env file
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1") # Default location

        if not project_id:
            logger.error("GOOGLE_CLOUD_PROJECT environment variable not set.")
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set.")

        logger.info(f"Initializing Vertex AI (Project: {project_id}, Location: {location})")
        aiplatform.init(project=project_id, location=location)

        # Initialize Vision Model (used for TOC generation)
        if not vision_model:
            logger.info(f"Loading vision model: {VISION_MODEL_NAME}")
            vision_model = GenerativeModel(
                VISION_MODEL_NAME,
                generation_config=VISION_GENERATION_CONFIG,
                safety_settings=VISION_SAFETY_SETTINGS
            )
            logger.info("Vision model loaded successfully.")

        # Initialize Summarizer Model
        if not summarizer_model:
             logger.info(f"Loading summarizer model: {SUMMARIZER_MODEL_NAME}")
             summarizer_model = GenerativeModel(
                 SUMMARIZER_MODEL_NAME,
                 generation_config=SUMMARIZER_GENERATION_CONFIG,
                 safety_settings=SUMMARIZER_SAFETY_SETTINGS
             )
             logger.info("Summarizer model loaded successfully.")

        return True # Indicate success

    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI models: {e}", exc_info=True)
        vision_model = None
        summarizer_model = None
        return False # Indicate failure

# --- Helper Functions ---
def extract_text_for_section(doc: fitz.Document, start_page: int | None, end_page: int | None) -> str:
    """Extracts plain text from a given page range (1-based index)."""
    text = ""
    # Validate page numbers
    if start_page is None or end_page is None:
        logger.warning("Missing start or end page for text extraction.")
        return ""
    try:
        start_page = int(start_page)
        end_page = int(end_page)
    except (ValueError, TypeError):
         logger.warning(f"Invalid non-integer page numbers: start={start_page}, end={end_page}")
         return ""

    # Convert to 0-based index, ensuring bounds
    start_page_zero_based = max(0, start_page - 1)
    end_page_zero_based = min(doc.page_count - 1, end_page - 1)

    if start_page_zero_based < 0 or end_page_zero_based >= doc.page_count or start_page_zero_based > end_page_zero_based:
        logger.warning(f"Invalid page range for text extraction: {start_page}-{end_page} (Document has {doc.page_count} pages). Corrected range: {start_page_zero_based+1}-{end_page_zero_based+1}")
        # If corrected start is still invalid, return empty
        if start_page_zero_based > end_page_zero_based or start_page_zero_based < 0:
             return ""

    try:
        for page_num in range(start_page_zero_based, end_page_zero_based + 1):
            page = doc.load_page(page_num)
            page_text = page.get_text("text")
            if page_text: # Append only if text exists
                text += page_text + "\\n" # Add newline between pages
        return text.strip()
    except Exception as e:
        logger.error(f"Error extracting text from pages {start_page}-{end_page} (indices {start_page_zero_based}-{end_page_zero_based}): {e}", exc_info=True)
        return "Error extracting text."

def post_process_llm_response_to_dict(response_text: str) -> dict | None:
    """
    Extracts a Python dictionary literal from the LLM's response text,
    attempting to handle common variations like ```python ... ``` blocks.
    """
    dict_str = None
    try:
        # Regex to find ```python { ... } ``` or just { ... } as fallback
        # Make the dictionary capture non-greedy and handle potential leading/trailing whitespace
        match_python = re.search(r"```python\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        match_raw = re.search(r"^\s*(\{.*?\})\s*$", response_text, re.DOTALL | re.MULTILINE)

        if match_python:
            dict_str = match_python.group(1)
            logger.debug("Found dictionary within ```python block.")
        elif match_raw:
            dict_str = match_raw.group(1)
            logger.debug("Found raw dictionary structure.")
        else:
            logger.warning("Could not find Python dictionary structure (```python ... ``` or raw {...}) in LLM response.")
            # Log the beginning of the response for debugging
            logger.debug(f"LLM Response Start: {response_text[:500]}...")
            return None

        logger.debug(f"Extracted potential dictionary string (length {len(dict_str)}). First 500 chars: {dict_str[:500]}...")

        # Attempt to parse the string as JSON after basic Python literal conversion
        # This is fragile; a more robust solution might involve ast.literal_eval
        # Be cautious with replacements, especially quotes inside strings
        dict_str = dict_str.replace(': None', ': null')
        dict_str = dict_str.replace(': True', ': true')
        dict_str = dict_str.replace(': False', ': false')
        # Attempting to replace single quotes used for keys/strings requires care
        # to avoid messing up quotes *within* strings. Let's try parsing first.

        try:
            # First try direct JSON parsing
            parsed_dict = json.loads(dict_str)
        except json.JSONDecodeError:
            logger.warning("Direct JSON parsing failed. Trying ast.literal_eval as fallback.")
            # If JSON fails, try Python's literal evaluation (safer than eval)
            import ast
            try:
                parsed_dict = ast.literal_eval(dict_str)
                # Quick check if it looks like the expected TOC structure
                if not isinstance(parsed_dict, dict) or not all(isinstance(v, dict) for v in parsed_dict.values()):
                     logger.warning("ast.literal_eval result doesn't look like the expected TOC structure.")
                     return None

            except (ValueError, SyntaxError, MemoryError) as ast_e:
                logger.error(f"ast.literal_eval failed: {ast_e}")
                logger.error(f"Problematic string (first 500 chars): {dict_str[:500]}...")
                # Log the full string if ast fails too, as it might be the root cause
                logger.error(f"Full problematic string for ast.literal_eval:\n{dict_str}")
                return None

        if isinstance(parsed_dict, dict):
            logger.info("Successfully extracted and parsed dictionary from LLM response.")
            return parsed_dict
        else:
            logger.warning(f"Parsed result is not a dictionary: {type(parsed_dict)}")
            return None

    except Exception as e:
        # Catch other potential errors during processing
        logger.error(f"Error post-processing LLM response: {e}", exc_info=True)
        if dict_str:
            logger.error(f"String being processed (first 500 chars): {dict_str[:500]}...")
        # Also log the original full response text if available and post-processing failed
        logger.error(f"Original LLM response text leading to post-processing error:\n{response_text}")
        return None


# --- LLM Summarization Function ---
def summarize_text_chunk(text_chunk: str) -> str:
    """Sends a text chunk to the Summarizer LLM and returns a summary."""
    global summarizer_model
    if not summarizer_model:
        logger.error("Summarizer model is not initialized. Cannot generate summary.")
        return "Error: Summarizer model not initialized."

    # Basic validation of input text
    if not text_chunk or text_chunk == "Error extracting text.":
        return "Summary not available due to missing or invalid text."
    if len(text_chunk) < 30: # Increase min length slightly
        return "Section text too short to summarize meaningfully."

    # Limit input text size to avoid exceeding model limits (adjust as needed)
    # Check model's token limit if necessary. This is a rough character limit.
    MAX_CHUNK_CHARS = 30000
    if len(text_chunk) > MAX_CHUNK_CHARS:
        logger.warning(f"Text chunk exceeds {MAX_CHUNK_CHARS} chars, truncating for summarization.")
        text_chunk = text_chunk[:MAX_CHUNK_CHARS]

    logger.debug(f"Summarizing text chunk (length: {len(text_chunk)} chars)...")

    # Refined Prompt for better focus
    prompt = f"""You are an expert technical writer analyzing Belgian/Flemish construction specifications ('lastenboek' or 'bestek').
Analyze the following text extracted from one specific section.
Provide a concise summary (target 3-5 key points or sentences) focusing *only* on the **actions, methods, materials, or quality requirements** described for executing the work in this section.

Instructions for the summary:
- Focus on *how* the work must be done.
- Highlight specific instructions, prescribed methods, essential materials, quality standards, or mandatory procedures.
- Be direct and action-oriented.
- Use bullet points if appropriate for clarity.
- Do NOT include introductory phrases like "This section discusses..." or "The text covers...".
- Do NOT summarize the *topic* itself (e.g., avoid "This section is about concrete."). Instead, state *what* must be done with the concrete (e.g., "- Concrete must reach strength class C25/30.").
- If the text is too short or lacks actionable details, state "No specific execution details found."

Text from Section:
```
{text_chunk}
```

Execution Details Summary:"""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = summarizer_model.generate_content(prompt)

            # Check for blocked content first
            if response.prompt_feedback and response.prompt_feedback.block_reason:
                 block_reason = response.prompt_feedback.block_reason
                 logger.warning(f"LLM summarization call blocked (Attempt {attempt+1}): {block_reason}")
                 # Provide a more informative error message
                 return f"Summary blocked by safety filter ({block_reason})."

            # Check for valid content parts
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                summary = response.candidates[0].content.parts[0].text.strip()
                # Basic check if summary is meaningful
                if summary and len(summary) > 10: # Avoid empty or trivial summaries
                    logger.debug(f"  Summary generated (attempt {attempt+1}). Length: {len(summary)}")
                    return summary
                else:
                    logger.warning(f"LLM generated empty or trivial summary (Attempt {attempt+1}). Response: {summary}")
                    # Return a specific message instead of the trivial summary
                    return "Summary generation resulted in empty or trivial content."

            # If neither blocked nor valid content, log unexpected response
            logger.warning(f"LLM summary response structure unexpected or empty (Attempt {attempt+1}). Response: {response}")
            # Fallthrough to retry

        except Exception as e:
            logger.error(f"Error calling Vertex AI API for summary (Attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1.5 ** attempt) # Exponential backoff
            else:
                logger.error("Max retries reached for summarization.")
                return "Error: Failed to generate summary after multiple attempts."

    # If loop completes without returning, it means all retries failed without specific errors caught above
    return "Error: Failed to generate summary after retries."

# --- LLM-Based TOC Generation Function ---
def generate_llm_toc(pdf_path: str) -> dict | None:
    """Generates a hierarchical TOC using the LLM Vision model."""
    global vision_model
    if not vision_model:
        logger.error("Vision model is not initialized. Cannot generate TOC.")
        return None

    logger.info(f"Starting LLM-based TOC generation for: {pdf_path}")
    pdf_doc_check = None # For initial page count check
    try:
        # Use fitz to open and get page count, ensure it's closed promptly
        pdf_doc_check = fitz.open(pdf_path)
        total_pages = pdf_doc_check.page_count
        pdf_doc_check.close() # Close doc after getting page count
        logger.info(f"PDF initial check successful ({total_pages} pages).")

        # Read bytes separately for sending to LLM
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        logger.info(f"PDF bytes read ({len(pdf_bytes)} bytes). Sending to vision model...")

        # Refined and detailed prompt for the vision model
        # Ensure JSON examples are valid JSON within the Python string context
        toc_prompt = f"""Analyze the provided PDF document ({total_pages} pages), which contains technical specifications, likely for construction (Dutch/Flemish language). The document might be a combination of multiple source files.

Identify the hierarchical structure of chapters and sections based on numbered headings. Common formats include:
- Chapter: `XX.` (e.g., "00.", "01.")
- Section: `XX.YY.` (e.g., "01.10.")
- Subsection: `XX.YY.ZZ.` (e.g., "01.10.01.")
- Further levels: `XX.YY.ZZ.AA.` etc.

Your Task: Extract a complete Table of Contents (TOC) including ALL levels of chapters and sections/subsections.

For EACH identified entry (chapter, section, subsection, etc.):
1.  **Hierarchical Code:** Determine the exact code (e.g., "00", "01.10", "01.10.01"). Remove trailing dots.
2.  **Title:** Extract the full title exactly as it appears following the code.
3.  **Start Page:** Determine the **GLOBAL PDF page number** (1-based index) where the content for this specific section *begins*. This is the page where the heading appears or the content immediately following it starts.
4.  **End Page:** Determine the **GLOBAL PDF page number** (1-based index) which is the last page containing content *belonging exclusively to this section*. This page is usually immediately before the *next* heading of the same or higher level starts. For the very last section of the document, the end page is the total number of pages in the PDF.

Crucial Instructions:
-   **Page Numbers:** Use ONLY the GLOBAL PDF page numbers (1 to {total_pages}). IGNORE any page numbers printed *within* the document's headers/footers or its internal, often inaccurate, TOC.
-   **Accuracy:** Base page ranges on the actual start and end of content for each section within the PDF body.
-   **Completeness:** Be extremely thorough. Missing *any* chapter or section, especially nested ones, is a critical failure. Capture all levels.
-   **Structure:** Ensure the start page of a parent chapter/section matches the start page of its *first* child subsection if applicable. The end page of a parent should match the end page of its *last* child subsection.

Output Format:
Produce a **single, valid Python dictionary literal** enclosed in ```python ... ```. The keys of the dictionary should be the top-level chapter codes (as strings, e.g., "00", "01"). Each value must be a dictionary containing:
    - "title" (string): The full title.
    - "start_page" (integer): The 1-based starting page number.
    - "end_page" (integer): The 1-based ending page number.
    - "sections" (dictionary, optional): A nested dictionary for subsections, following the exact same structure recursively. The keys for the nested "sections" dictionary are the full subsection codes (e.g., "01.10", "01.10.01").

Example Snippet of the Expected Output Structure:
```python
{{
    "00": {{
        "title": "ALGEMENE BEPALINGEN",
        "start_page": 5,
        "end_page": 12,
        "sections": {{
            "00.10": {{
                "title": "Definities",
                "start_page": 5,
                "end_page": 7,
                "sections": {{}} # Empty if no further subsections
            }},
            "00.20": {{
                "title": "Toepasselijke normen",
                "start_page": 8,
                "end_page": 12,
                "sections": {{
                     "00.20.01": {{
                         "title": "Algemene normen",
                         "start_page": 9,
                         "end_page": 10,
                         "sections": {{}}
                     }},
                     "00.20.02": {{
                         "title": "Specifieke normen",
                         "start_page": 11,
                         "end_page": 12,
                         "sections": {{}}
                     }}
                }}
            }}
        }}
    }},
    "01": {{
        "title": "GRONDWERKEN",
        "start_page": 13,
        "end_page": 25,
        "sections": {{
            # ... more sections like 01.10, 01.20 etc.
        }}
    }}
    # ... other top-level chapters
}}
```

Ensure the output contains ONLY the Python dictionary within the ```python ... ``` block. Be meticulous about correct nesting, keys, types (strings for codes/titles, integers for pages), and valid Python syntax. Check page ranges carefully.
"""

        # Prepare the content parts for the API call
        content_parts = [
            toc_prompt,
            Part.from_data(data=pdf_bytes, mime_type="application/pdf")
        ]

        # Send prompt and PDF to the vision model
        # Use streaming=False for simpler response handling unless the response is huge
        response = vision_model.generate_content(content_parts, stream=False)

        logger.info("Received TOC response from vision model.")

        # Process the response to get the dictionary
        # Accessing response for non-streaming:
        if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            response_text = response.text # Use response.text for easier access
            toc_dict = post_process_llm_response_to_dict(response_text)
            if toc_dict:
                logger.info(f"Successfully generated and parsed hierarchical TOC with {len(toc_dict)} top-level chapters.")
                # Add a basic validation check
                if not all(isinstance(v, dict) and 'title' in v and 'start_page' in v and 'end_page' in v for v in toc_dict.values()):
                    logger.warning("Parsed TOC dictionary structure seems invalid. Check LLM output.")
                    # Potentially log the problematic dict structure here
                    # logger.debug(f"Problematic TOC structure: {json.dumps(toc_dict, indent=2)}")
                    # Decide whether to return None or the potentially flawed dict
                    # return None
                return toc_dict
            else:
                logger.error("Failed to extract a valid dictionary from the vision model response text.")
                logger.debug(f"LLM Response Text: {response_text[:1000]}...") # Log beginning of text
                return None
        elif response.prompt_feedback and response.prompt_feedback.block_reason:
            block_reason = response.prompt_feedback.block_reason
            logger.error(f"Vision model call blocked for TOC generation: {block_reason}")
            return None
        else:
             logger.error("Vision model response was empty, invalid, or did not contain expected content parts.")
             logger.debug(f"Raw response object: {response}") # Log raw response if possible
             return None

    except fitz.FitzError as fitz_e:
        logger.error(f"PyMuPDF (fitz) error processing {pdf_path}: {fitz_e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error during LLM-based TOC generation: {e}", exc_info=True)
        return None
    finally:
        # Ensure closure of the initial check document if it was opened
        if pdf_doc_check and not pdf_doc_check.is_closed:
             pdf_doc_check.close()

# --- Recursive Summarization Function ---
def add_summaries_recursive(toc_node: dict, pdf_doc: fitz.Document, node_code: str = "ROOT"):
    """Recursively traverses the TOC dictionary and adds summaries."""
    if not isinstance(toc_node, dict):
        logger.warning(f"Encountered non-dictionary node while expecting dict for code {node_code}.")
        return # Skip non-dictionary nodes

    node_title = toc_node.get("title", f"Unknown Section {node_code}")
    start_page = toc_node.get("start_page")
    end_page = toc_node.get("end_page")

    logger.debug(f"Processing node: {node_code} - '{node_title}' (Pages {start_page}-{end_page})")

    summary = "Summary generation skipped (validation failed)." # Default
    node_text = "" # Initialize node_text

    # Validate pages before extraction
    valid_pages = False
    if start_page is not None and end_page is not None:
        try:
            start_page = int(start_page)
            end_page = int(end_page)
            if 1 <= start_page <= end_page <= pdf_doc.page_count:
                valid_pages = True
            else:
                 logger.warning(f"Node {node_code} ('{node_title}') has invalid page range: {start_page}-{end_page}. Document pages: {pdf_doc.page_count}. Skipping text extraction.")
        except (ValueError, TypeError):
            logger.warning(f"Node {node_code} ('{node_title}') has non-integer page numbers: start={start_page}, end={end_page}. Skipping text extraction.")
    else:
        logger.warning(f"Node {node_code} ('{node_title}') missing start/end page. Cannot extract text or summarize.")

    # Extract text and summarize only if pages are valid
    if valid_pages:
        node_text = extract_text_for_section(pdf_doc, start_page, end_page)
        # Check if extraction was successful before summarizing
        if node_text != "Error extracting text.":
             summary = summarize_text_chunk(node_text)
        else:
             summary = "Summary unavailable (error during text extraction)."
    else:
        # If pages were invalid from the start
        summary = "Summary unavailable (invalid or missing page range)."

    # Add summary and extracted text (optional, can be large) to the node
    toc_node['summary'] = summary
    # Decide if you want to store the full text - potentially very large!
    # toc_node['extracted_text'] = node_text # Uncomment carefully

    # Recursively process child sections
    if "sections" in toc_node and isinstance(toc_node["sections"], dict):
        child_sections = toc_node["sections"]
        if child_sections: # Check if dictionary is not empty
             logger.debug(f"  Processing {len(child_sections)} subsections for {node_code} ('{node_title}')")
             for section_code, section_node in child_sections.items():
                 # Pass the correct code for the child node
                 add_summaries_recursive(section_node, pdf_doc, node_code=section_code)
        else:
             logger.debug(f"  Node {node_code} ('{node_title}') has an empty 'sections' dictionary.")
    else:
        # Log if 'sections' key exists but isn't a dict, or doesn't exist
        if "sections" in toc_node:
             logger.debug(f"  Node {node_code} ('{node_title}') 'sections' key is not a dictionary (type: {type(toc_node.get('sections'))}).")
        else:
             logger.debug(f"  Node {node_code} ('{node_title}') has no 'sections' key.")


# --- Main Processing Function ---
def generate_augmented_toc(pdf_path: str) -> dict | None:
    """
    Main function to generate hierarchical TOC via LLM and augment it with summaries.
    Returns the augmented TOC dictionary or None if failed.
    """
    pdf_doc = None # Initialize pdf_doc for finally block
    augmented_toc = None # Initialize result
    try:
        # 1. Initialize LLM Models
        logger.info("Step 1: Initializing LLM models...")
        if not initialize_llm_models():
            logger.error("LLM initialization failed. Exiting.")
            return None # Exit if models can't be initialized
        logger.info("LLM models initialized successfully.")

        # 2. Generate Base Hierarchical TOC using Vision LLM
        logger.info("Step 2: Generating base hierarchical TOC...")
        hierarchical_toc = generate_llm_toc(pdf_path)
        if not hierarchical_toc or not isinstance(hierarchical_toc, dict):
            logger.error("Failed to generate or parse the base hierarchical TOC from LLM. Exiting.")
            return None
        logger.info("Base hierarchical TOC generated successfully.")
        # Keep a copy before modification if needed for comparison later
        augmented_toc = hierarchical_toc # Start augmentation on the generated TOC

        # 3. Augment with Summaries
        logger.info("Step 3: Augmenting TOC with summaries...")
        logger.info(f"Opening PDF '{pdf_path}' with fitz for text extraction...")
        pdf_doc = fitz.open(pdf_path)
        logger.info(f"PDF opened ({pdf_doc.page_count} pages). Starting recursive summarization...")

        # Process each top-level chapter in the TOC
        # Make sure to iterate over items() for key-value pairs
        for chapter_code, chapter_node in augmented_toc.items():
             if isinstance(chapter_node, dict): # Ensure we're processing a dictionary
                 logger.info(f"Augmenting Chapter: {chapter_code} - {chapter_node.get('title', 'Unknown Title')}")
                 add_summaries_recursive(chapter_node, pdf_doc, node_code=chapter_code)
             else:
                 logger.warning(f"Skipping invalid top-level entry for code '{chapter_code}'. Expected dict, got {type(chapter_node)}.")

        logger.info("Finished augmenting TOC with summaries.")
        return augmented_toc # Return the modified dictionary

    except fitz.FitzError as fitz_e:
         logger.error(f"PyMuPDF (fitz) error during summary augmentation: {fitz_e}", exc_info=True)
         return augmented_toc # Return whatever was processed so far, potentially partially summarized
    except Exception as e:
        logger.error(f"An unexpected error occurred during the main augmentation process: {e}", exc_info=True)
        # Decide whether to return None or partially processed TOC
        return augmented_toc # Return potentially partially summarized TOC on general errors too
    finally:
        # Ensure the fitz document is closed even if errors occur
        if pdf_doc and not pdf_doc.is_closed:
            pdf_doc.close()
            logger.debug("Closed fitz PDF document.")
        else:
            logger.debug("Fitz PDF document was not opened or already closed.")

# --- Main Execution Block ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a summarized hierarchical Table of Contents (TOC) from a PDF using LLMs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help
    )
    parser.add_argument("pdf_file", help="Path to the input PDF file.")
    parser.add_argument("-o", "--output", default="output/augmented_hierarchical_toc.json",
                        help="Path to the output JSON file (will be placed in 'output' subdir and indexed if exists).")
    parser.add_argument("--log", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Set the logging level.")

    args = parser.parse_args()

    # Set logging level based on command line argument
    logging.getLogger().setLevel(args.log.upper())
    logger.info(f"Logging level set to {args.log.upper()}")


    logger.info(f"Input PDF: {args.pdf_file}")
    logger.info(f"Output JSON: {args.output}")

    if not os.path.exists(args.pdf_file):
        logger.error(f"Input PDF file not found: {args.pdf_file}")
        sys.exit(1)
    if not args.pdf_file.lower().endswith('.pdf'):
        logger.warning(f"Input file '{args.pdf_file}' does not have a .pdf extension.")
        # Decide if you want to exit or proceed:
        # sys.exit(1)

    start_time = time.time()
    logger.info("Starting TOC Summarizer process...")

    # Generate the augmented TOC
    results = generate_augmented_toc(args.pdf_file)

    # Save results to JSON
    if results and isinstance(results, dict): # Check if results is a dictionary
        try:
            output_path = args.output
            output_dir = os.path.dirname(output_path)
            base_name, ext = os.path.splitext(os.path.basename(output_path))

            # Create output directory if it doesn't exist
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
                logger.info(f"Created output directory: {output_dir}")

            # Find the next available indexed filename
            index = 0
            final_output_path = os.path.join(output_dir, f"{base_name}{ext}")
            while os.path.exists(final_output_path):
                index += 1
                final_output_path = os.path.join(output_dir, f"{base_name}_{index}{ext}")

            logger.info(f"Determined final output path: {final_output_path}")

            with open(final_output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"Successfully saved augmented TOC to: {final_output_path}")
        except IOError as e:
            logger.error(f"Error writing output JSON file '{final_output_path}': {e}") # Use final path in error
            sys.exit(1)
        except Exception as e: # Catch other potential errors during save
            logger.error(f"Unexpected error saving results: {e}", exc_info=True)
            sys.exit(1)
    elif results is None:
        logger.error("Failed to generate augmented TOC. No output file created.")
        sys.exit(1)
    else:
         logger.error(f"Generated result was not a dictionary (type: {type(results)}). Cannot save. Check logs for errors.")
         sys.exit(1)


    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"TOC Summarizer script finished in {duration:.2f} seconds.") 