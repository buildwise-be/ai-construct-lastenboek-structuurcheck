#Actualquery.py - Refactored for Vertex AI

import os
import sys
import json
import argparse
import logging
from dotenv import load_dotenv
import fitz # Using fitz (PyMuPDF) for page count as it's often already needed
import re
import time
import datetime

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, SafetySetting, Part, GenerationConfig

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Define model names via environment variables with defaults
# Note: Using gemini-1.5-pro as the original script did, adjust if needed.
VISION_MODEL_NAME = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-001")

# Vision Model Config (Align with toc_summarizer.py examples)
VISION_GENERATION_CONFIG = GenerationConfig(
    max_output_tokens=8192, # Allow large output for complex TOCs
    temperature=0.2,      # Lower temperature for more deterministic TOC structure
    top_p=0.95,
)
# Define safety settings
VISION_SAFETY_SETTINGS = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
    ),
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

# Global variable for initialized model
vision_model = None

# --- Initialization ---
def initialize_vertex_ai():
    """Initializes the Vertex AI client and model."""
    global vision_model
    if vision_model:
        logger.debug("Vertex AI model already initialized.")
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

        # Initialize Vision Model
        logger.info(f"Loading vision model: {VISION_MODEL_NAME}")
        vision_model = GenerativeModel(
            VISION_MODEL_NAME,
            # System instruction is often passed within the generate_content call for multimodal
            # system_instruction=system_instruction, # Pass later if needed
        )
        logger.info("Vision model loaded successfully.")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI model: {e}", exc_info=True)
        vision_model = None
        return False

# --- Helper Functions ---
# System instruction - kept similar to original, adjusted slightly for clarity
system_instruction_text = """You are an expert system designed to extract a hierarchical Table of Contents (TOC) from technical PDF documents, specifically Belgian/Flemish construction specifications ("lastenboek" / "bestek"). These PDFs are often concatenations of multiple source documents, potentially with inconsistent internal pagination.

Your primary goal is to identify chapters and nested sections based on their numbered headings and determine their accurate page ranges within the GLOBAL PDF page numbering (1-based index).

Heading Formats:
- Main chapters: "XX." (e.g., "00.", "01.")
- Sections: "XX.YY." (e.g., "01.10.")
- Subsections: "XX.YY.ZZ." (e.g., "01.10.01.")
- Further levels: "XX.YY.ZZ.AA." etc.

Task: Extract a complete TOC including ALL levels.

For EACH identified entry (chapter, section, subsection, etc.):
1.  **Hierarchical Code:** Determine the exact code (e.g., "00", "01.10", "01.10.01"). Remove any trailing dots.
2.  **Title:** Extract the full title exactly as it appears following the code.
3.  **Start Page:** Determine the **GLOBAL PDF page number** (1-based index) where the content for this specific section *begins*.
4.  **End Page:** Determine the **GLOBAL PDF page number** (1-based index) which is the last page containing content *belonging exclusively to this section*. This page is usually immediately before the *next* heading of the same or higher level starts. For the very last section of the document, the end page is the total number of pages in the PDF.

Crucial Instructions:
-   **Page Numbers:** Use ONLY GLOBAL PDF page numbers. IGNORE any page numbers printed *within* the document or in its internal TOC (which is unreliable).
-   **Accuracy:** Base page ranges on the actual start and end of content flow in the PDF body.
-   **Completeness:** Be extremely thorough. Missing *any* level is a critical failure.
-   **Structure:** Ensure parent start/end pages align with their first/last children.

Output Format:
Produce a **single, valid Python dictionary literal** enclosed in ```python ... ```. Use the following nested structure, with chapter codes as top-level keys:

```python
{
    "00": {
        "title": "ALGEMENE BEPALINGEN",
        "start_page": 5,
        "end_page": 12,
        "sections": {
            "00.10": {
                "title": "Definities",
                "start_page": 5,
                "end_page": 7,
                "sections": {} # Empty dict if no further subsections
            },
            "00.20": {
                "title": "Toepasselijke normen",
                "start_page": 8,
                "end_page": 12,
                "sections": {
                     "00.20.01": {
                         "title": "Algemene normen",
                         "start_page": 9,
                         "end_page": 10,
                         "sections": {}
                     },
                     "00.20.02": {
                         "title": "Specifieke normen",
                         "start_page": 11,
                         "end_page": 12,
                         "sections": {}
                     }
                }
            }
        }
    },
    "01": { # Next chapter
        # ...
    }
    # ... other chapters
}
```
Ensure the output contains ONLY the Python dictionary within the ```python ... ``` block. Be meticulous about syntax, nesting, types, and page ranges.
"""

# New prompt template for vision-based summarization
vision_summary_prompt_template = """You are an expert technical writer analyzing Belgian/Flemish construction specifications ('lastenboek' or 'bestek').
Focus ONLY on the content within pages {start_page} to {end_page} (inclusive, 1-based index) of the provided PDF document.
Analyze the text and any relevant diagrams/images on these specific pages.
Provide a concise summary (target 3-5 key points or sentences) focusing *only* on the **actions, methods, materials, or quality requirements** described for executing the work in this section.

Instructions for the summary:
- Summarize *how* the work must be done based *only* on pages {start_page}-{end_page}.
- Highlight specific instructions, prescribed methods, essential materials, quality standards, or mandatory procedures mentioned *on these pages*.
- Be direct and action-oriented.
- Use bullet points if appropriate for clarity.
- Do NOT include introductory phrases like "This section discusses..." or "The text covers...".
- Do NOT summarize the *topic* itself (e.g., avoid "This section is about concrete."). Instead, state *what* must be done with the concrete according to these pages (e.g., "- Concrete must reach strength class C25/30.").
- If the specified pages contain insufficient information for an execution summary, state "No specific execution details found on pages {start_page}-{end_page}."
- Output only the summary text.

Execution Details Summary for pages {start_page}-{end_page}:"""

def post_process_llm_response_to_dict(response_text: str) -> dict | None:
    """
    Extracts a Python dictionary literal from the LLM's response text,
    attempting to handle common variations like ```python ... ``` blocks.
    (Adapted from toc_summarizer.py)
    """
    dict_str = None
    try:
        # Regex to find ```python { ... } ``` or just { ... } as fallback
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
            logger.debug(f"LLM Response Start: {response_text[:500]}...")
            return None

        logger.debug(f"Extracted potential dictionary string (length {len(dict_str)}). First 500 chars: {dict_str[:500]}...")

        # Basic Python literal to JSON conversion
        dict_str = dict_str.replace(': None', ': null')
        dict_str = dict_str.replace(': True', ': true')
        dict_str = dict_str.replace(': False', ': false')

        try:
            # Try direct JSON parsing
            parsed_dict = json.loads(dict_str)
        except json.JSONDecodeError:
            logger.warning("Direct JSON parsing failed. Trying ast.literal_eval as fallback.")
            import ast
            try:
                parsed_dict = ast.literal_eval(dict_str)
                if not isinstance(parsed_dict, dict) or not all(isinstance(v, dict) for v in parsed_dict.values()):
                     logger.warning("ast.literal_eval result doesn't look like the expected TOC structure.")
                     return None
            except (ValueError, SyntaxError, MemoryError, TypeError) as ast_e: # Added TypeError
                logger.error(f"ast.literal_eval failed: {ast_e}")
                logger.error(f"Problematic string (first 500 chars): {dict_str[:500]}...")
                logger.error(f"Full problematic string for ast.literal_eval:\n{dict_str}")
                return None

        if isinstance(parsed_dict, dict):
            logger.info("Successfully extracted and parsed dictionary from LLM response.")
            return parsed_dict
        else:
            logger.warning(f"Parsed result is not a dictionary: {type(parsed_dict)}")
            return None

    except Exception as e:
        logger.error(f"Error post-processing LLM response: {e}", exc_info=True)
        if dict_str:
            logger.error(f"String being processed (first 500 chars): {dict_str[:500]}...")
        logger.error(f"Original LLM response text leading to post-processing error:\n{response_text}")
        return None

# --- New Function for Vision-Based Summarization ---
def add_vision_summaries_recursive(toc_node: dict, pdf_part: Part, node_code: str = "ROOT"):
    """Recursively traverses the TOC dictionary and adds summaries using the vision model."""
    global vision_model
    if not vision_model:
        logger.error(f"Summarization skipped for {node_code}: Vision model not initialized.")
        toc_node['summary'] = "Error: Vision model not initialized for summary."
        return

    if not isinstance(toc_node, dict):
        logger.warning(f"Skipping summarization for non-dictionary node: {node_code}")
        return # Skip non-dictionary nodes

    node_title = toc_node.get("title", f"Unknown Section {node_code}")
    start_page = toc_node.get("start_page")
    end_page = toc_node.get("end_page")

    logger.debug(f"Attempting summary for node: {node_code} - '{node_title}' (Pages {start_page}-{end_page})")

    summary = "Summary generation skipped (invalid pages)." # Default

    # Validate pages before making API call
    valid_pages = False
    if start_page is not None and end_page is not None and isinstance(start_page, int) and isinstance(end_page, int) and start_page <= end_page and start_page >= 1:
        valid_pages = True
    else:
        logger.warning(f"Node {node_code} ('{node_title}') has invalid or missing page range: {start_page}-{end_page}. Skipping summary generation.")

    if valid_pages:
        # Format the summary prompt for the specific page range
        summary_prompt = vision_summary_prompt_template.format(start_page=start_page, end_page=end_page)
        content_parts = [summary_prompt, pdf_part]

        max_retries = 2
        summary = f"Error: Failed to generate summary for pages {start_page}-{end_page} after retries." # Default error

        for attempt in range(max_retries + 1):
            try:
                # Use appropriate config/safety for summarization - maybe slightly different?
                # For now, reusing VISION settings, but could define separate SUMMARIZER ones.
                response = vision_model.generate_content(
                    content_parts,
                    generation_config=VISION_GENERATION_CONFIG, # Consider a SUMMARIZER_CONFIG if needed
                    safety_settings=VISION_SAFETY_SETTINGS,    # Consider SUMMARIZER_SAFETY if needed
                    stream=False
                )

                # Check for safety blocks
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     logger.warning(f"LLM summarization call blocked for {node_code} (Pages {start_page}-{end_page}, Attempt {attempt+1}): {block_reason}")
                     summary = f"Summary blocked by safety filter ({block_reason}) for pages {start_page}-{end_page}."
                     break # Exit retry loop if blocked

                # Extract summary text
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    extracted_summary = response.text.strip()
                    if extracted_summary and len(extracted_summary) > 10: # Basic check for meaningful summary
                        logger.debug(f"  Summary generated for {node_code} (Pages {start_page}-{end_page}, Attempt {attempt+1}). Length: {len(extracted_summary)}")
                        summary = extracted_summary
                        break # Success
                    else:
                        logger.warning(f"LLM generated empty or trivial summary for {node_code} (Pages {start_page}-{end_page}, Attempt {attempt+1}). Response: {extracted_summary}")
                        summary = f"Summary generation resulted in empty/trivial content for pages {start_page}-{end_page}."
                        # Consider breaking here or letting it retry? Retry might not help if content is sparse. Let's break.
                        break

                else:
                    logger.warning(f"LLM summary response structure unexpected for {node_code} (Pages {start_page}-{end_page}, Attempt {attempt+1}). Response: {response}")
                    # Continue to retry if attempts remain

            except Exception as e:
                logger.error(f"Error calling Vertex AI API for summary of {node_code} (Pages {start_page}-{end_page}, Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying summary for {node_code} after delay...")
                    time.sleep(3 * (attempt + 1)) # Shorter backoff for summary retries?
                else:
                    logger.error(f"Max retries reached for summarizing {node_code} (Pages {start_page}-{end_page}).")
                    # Keep default error message
                    break # Exit retry loop

    # Add the generated summary (or error message) to the node
    toc_node['summary'] = summary

    # Recursively process child sections
    if "sections" in toc_node and isinstance(toc_node["sections"], dict):
        child_sections = toc_node["sections"]
        if child_sections: # Check if dictionary is not empty
             logger.debug(f"  Processing {len(child_sections)} subsections for summary under {node_code} ('{node_title}')")
             for section_code, section_node in child_sections.items():
                 add_vision_summaries_recursive(section_node, pdf_part, node_code=section_code)
        else:
             logger.debug(f"  Node {node_code} ('{node_title}') has an empty 'sections' dictionary.")
    else:
        # Log if 'sections' key exists but isn't a dict, or doesn't exist
        if "sections" in toc_node:
             logger.debug(f"  Node {node_code} ('{node_title}') 'sections' key is not a dictionary (type: {type(toc_node.get('sections'))}). Skipping recursion.")
        else:
             logger.debug(f"  Node {node_code} ('{node_title}') has no 'sections' key. End of branch for summary.")


def save_results_with_index(chapters_dict, input_filename, output_base_filename="vision_toc"):
    """Saves the resulting dictionary to a JSON file in the output folder with indexing."""
    input_base = os.path.splitext(os.path.basename(input_filename))[0]
    today_date = datetime.datetime.now().strftime("%Y%m%d")

    # Use current working directory for output folder
    output_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Determine base filename structure
    base_filename_structure = f"{output_base_filename}_{input_base}_{today_date}"
    
    # Find the next available index number
    index = 1
    output_filename = os.path.join(output_dir, f"{base_filename_structure}_{index}.json")
    while os.path.exists(output_filename):
        index += 1
        output_filename = os.path.join(output_dir, f"{base_filename_structure}_{index}.json")

    logger.info(f"Determined final output path: {output_filename}")

    try:
        with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(chapters_dict, f, indent=4, ensure_ascii=False)
        logger.info(f"Successfully saved vision-based TOC to: {output_filename}")
    except IOError as e:
        logger.error(f"Error writing output JSON file '{output_filename}': {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving results: {e}", exc_info=True)
    

def validate_chapters(chapters_dict, total_pages):
    """Validates page numbers in the extracted TOC dictionary."""
    validated = {}
    # Use total_pages from PDF as the reasonable maximum
    reasonable_max = total_pages

    for chapter_id, chapter_data in chapters_dict.items():
        # Skip empty chapters or non-dictionary entries
        if not chapter_data or not isinstance(chapter_data, dict):
            logger.warning(f"Skipping invalid chapter entry: {chapter_id}")
            continue
            
        # Check top-level chapter pages
        if ('start_page' not in chapter_data or 'end_page' not in chapter_data or
            not isinstance(chapter_data['start_page'], int) or not isinstance(chapter_data['end_page'], int) or
            chapter_data['start_page'] < 1 or chapter_data['end_page'] > reasonable_max or
            chapter_data['start_page'] > chapter_data['end_page']):
            logger.warning(f"Chapter {chapter_id} has invalid page numbers: {chapter_data.get('start_page', 'missing')}-{chapter_data.get('end_page', 'missing')}. Max pages: {reasonable_max}")
            # Optionally skip this chapter or try to fix later
            continue # Skip for now

        # Recursively validate sections
        if 'sections' in chapter_data and isinstance(chapter_data['sections'], dict):
            chapter_data['sections'] = _validate_sections_recursive(chapter_data['sections'], reasonable_max, chapter_id)

        validated[chapter_id] = chapter_data
    
    return validated

def _validate_sections_recursive(sections_dict, max_pages, parent_id):
    """Helper function to recursively validate section page numbers."""
    valid_sections = {}
    for section_id, section_data in sections_dict.items():
        if not section_data or not isinstance(section_data, dict):
            logger.warning(f"Skipping invalid section entry under {parent_id}: {section_id}")
            continue

        if ('start_page' not in section_data or 'end_page' not in section_data or
            not isinstance(section_data['start_page'], int) or not isinstance(section_data['end_page'], int) or
            section_data['start_page'] < 1 or section_data['end_page'] > max_pages or
            section_data['start_page'] > section_data['end_page']):
            logger.warning(f"Section {section_id} (under {parent_id}) has invalid page numbers: {section_data.get('start_page', 'missing')}-{section_data.get('end_page', 'missing')}. Max pages: {max_pages}")
            continue # Skip invalid section

        # Recursively validate nested sections
        if 'sections' in section_data and isinstance(section_data['sections'], dict):
            section_data['sections'] = _validate_sections_recursive(section_data['sections'], max_pages, section_id)

        valid_sections[section_id] = section_data
    return valid_sections

# --- Main Execution Logic ---
def process_pdf_batches(pdf_path: str, pdf_part: Part, total_pages: int):
    """Processes the PDF in batches to generate the TOC using Vertex AI."""
    global vision_model
    if not vision_model:
        logger.error("Vision model not initialized. Cannot process.")
        return None

        all_chapters = {}
    processed_batches = 0

    # --- Batching Logic ---
    page_batch_size = 20  # Default
        if total_pages > 300:
            page_batch_size = 15
        elif total_pages > 500:
            page_batch_size = 10
            
    overlap = 5
        page_batches = []
        for start_page in range(1, total_pages + 1, page_batch_size - overlap):
            end_page = min(start_page + page_batch_size - 1, total_pages)
            if end_page - start_page < 5 and len(page_batches) > 0:
                page_batches[-1] = (page_batches[-1][0], end_page)
                break
            page_batches.append((start_page, end_page))
        
    logger.info(f"Processing PDF in {len(page_batches)} page batches (size ~{page_batch_size}, overlap {overlap})")
        
    # --- Process Batches ---
        for batch_idx, (start_page, end_page) in enumerate(page_batches):
        logger.info(f"Processing page batch {batch_idx+1}/{len(page_batches)}: pages {start_page}-{end_page}")
            
        # Add context notes for first/last batches
            if batch_idx < 3:
            comprehensive_note = "This is one of the first batches; pay extra attention to document structure and early chapters/sections."
            elif batch_idx >= len(page_batches) - 3:
            comprehensive_note = "This is one of the final batches; pay extra attention to closing chapters/sections and ensure correct final page numbers."
            else:
                comprehensive_note = ""
                
        # Construct the prompt for this batch
        # Include the overall system instruction context within the batch prompt if model needs reminding
        page_prompt = f"""{system_instruction_text}

        ---
        Current Task: Analyze ONLY pages {start_page}-{end_page} of the provided PDF document.
            {comprehensive_note}
            
        Identify any chapters or sections (and their nested subsections) that *appear* within this specific page range ({start_page}-{end_page}).

        Specific Instructions for this Batch:
        - Focus ONLY on pages {start_page} through {end_page}.
        - Report page numbers relative to the GLOBAL PDF page count.
        - If a chapter/section starts within this range but continues *beyond* page {end_page}, report its end page as {end_page} for this batch's analysis.
        - If a chapter/section ends within this range but started *before* page {start_page}, report its start page as {start_page} for this batch's analysis.
        - Be thorough, even for brief sections appearing in this range.
        - Output ONLY the findings for pages {start_page}-{end_page} in the specified Python dictionary format ```python {{...}} ```. If no chapters/sections start or end in this range, output an empty dictionary ```python {{}} ```.
        """

        content_parts = [page_prompt, pdf_part]
        max_retries = 2 # Allow one retry per batch
        for attempt in range(max_retries + 1):
            try:
                response = vision_model.generate_content(
                    content_parts,
                    generation_config=VISION_GENERATION_CONFIG,
                    safety_settings=VISION_SAFETY_SETTINGS,
                    stream=False
                )

                # Check for safety blocks first
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     logger.warning(f"LLM call blocked for batch {batch_idx+1} (Attempt {attempt+1}): {block_reason}")
                     page_batch_dict = None # Treat as no data found for this batch
                     break # Exit retry loop for this batch if blocked

                # Check for valid content parts
                if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                    response_text = response.text
                    page_batch_dict = post_process_llm_response_to_dict(response_text)
                    if page_batch_dict is not None: # Includes empty dict {}
                         logger.info(f"Successfully processed batch {batch_idx+1}. Found {len(page_batch_dict)} top-level items in this batch.")
                         processed_batches += 1
                         break # Success, exit retry loop
                        else:
                         logger.warning(f"Failed to parse dictionary from response for batch {batch_idx+1} (Attempt {attempt+1}). Response start: {response.text[:200]}...")
                         page_batch_dict = None # Ensure it's None if parsing failed
                         # Continue to retry if attempts remain

                else:
                    logger.warning(f"LLM response structure unexpected or empty for batch {batch_idx+1} (Attempt {attempt+1}). Response: {response}")
                    page_batch_dict = None # Treat as no data
                    # Continue to retry if attempts remain

            except Exception as e:
                logger.error(f"Error calling Vertex AI API for batch {batch_idx+1} (Attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries:
                    logger.info(f"Retrying batch {batch_idx+1} after delay...")
                    time.sleep(5 * (attempt + 1)) # Exponential backoff
                else:
                    logger.error(f"Max retries reached for batch {batch_idx+1}. Skipping.")
                    page_batch_dict = None # Ensure no data from this failed batch
                    break # Exit retry loop

        # --- Merge Batch Results ---
        if isinstance(page_batch_dict, dict):
                        for chapter_id, chapter_data in page_batch_dict.items():
                if not isinstance(chapter_data, dict) or 'start_page' not in chapter_data or 'end_page' not in chapter_data:
                     logger.warning(f"Skipping invalid chapter data from batch {batch_idx+1}: {chapter_id} -> {chapter_data}")
                     continue

                if chapter_id not in all_chapters:
                    all_chapters[chapter_id] = chapter_data
                            else:
                    # Merge: Keep earliest start, latest end, longest title, merge sections
                    existing = all_chapters[chapter_id]
                    existing['start_page'] = min(existing['start_page'], chapter_data['start_page'])
                    existing['end_page'] = max(existing['end_page'], chapter_data['end_page'])
                    if len(chapter_data.get('title', '')) > len(existing.get('title', '')):
                        existing['title'] = chapter_data['title']

                    if 'sections' in chapter_data and isinstance(chapter_data['sections'], dict):
                        if 'sections' not in existing or not isinstance(existing.get('sections'), dict):
                            existing['sections'] = {} # Initialize if missing or wrong type
                                    
                                    for section_id, section_data in chapter_data['sections'].items():
                             if not isinstance(section_data, dict) or 'start_page' not in section_data or 'end_page' not in section_data:
                                 logger.warning(f"Skipping invalid section data {section_id} under {chapter_id} from batch {batch_idx+1}")
                                 continue

                                        if section_id not in existing['sections']:
                                            existing['sections'][section_id] = section_data
                                        else:
                                 # Merge section: Keep earliest start, latest end, longest title
                                 existing_sec = existing['sections'][section_id]
                                 existing_sec['start_page'] = min(existing_sec['start_page'], section_data['start_page'])
                                 existing_sec['end_page'] = max(existing_sec['end_page'], section_data['end_page'])
                                 if len(section_data.get('title', '')) > len(existing_sec.get('title', '')):
                                     existing_sec['title'] = section_data['title']
                                 # Note: recursive section merging not implemented here, assumes max 2 levels for merge logic

    logger.info(f"Finished processing {processed_batches}/{len(page_batches)} batches successfully.")
    if processed_batches < len(page_batches):
        logger.warning("Some batches may have failed processing.")

    # --- Final Boundary Adjustment ---
    logger.info("Performing final boundary adjustments...")
    # Convert to sorted list for easier adjustment
    # Filter out entries without valid start_page before sorting
    valid_entries = [(k, v) for k, v in all_chapters.items() if isinstance(v, dict) and isinstance(v.get('start_page'), int)]
    if not valid_entries:
        logger.warning("No valid entries found for boundary adjustment.")
        return all_chapters # Return the (likely empty) dict

    sorted_chapters = sorted(valid_entries, key=lambda x: x[1]['start_page'])

    # Phase 1: Adjust sections within each chapter and update chapter end based on last section
    for i in range(len(sorted_chapters)):
        current_id, current_ch = sorted_chapters[i]

        # Adjust sections within the chapter first
        if 'sections' in current_ch and isinstance(current_ch.get('sections'), dict) and current_ch['sections']:
            valid_sections = [(sk, sv) for sk, sv in current_ch['sections'].items() if isinstance(sv, dict) and isinstance(sv.get('start_page'), int)]
            if not valid_sections:
                continue # No valid sections to adjust

            sorted_sections = sorted(valid_sections, key=lambda x: x[1]['start_page'])

            # Adjust end pages for all sections except the last one
                for j in range(len(sorted_sections) - 1):
                    current_sec_id, current_sec = sorted_sections[j]
                next_sec_id, next_sec = sorted_sections[j+1]
                if current_sec['end_page'] < next_sec['start_page'] - 1:
                     logger.debug(f"Adjusting end page for section {current_sec_id}: {current_sec['end_page']} -> {next_sec['start_page'] - 1}")
                     current_sec['end_page'] = next_sec['start_page'] - 1
                elif current_sec['end_page'] >= next_sec['start_page']: # Handle overlap detected by LLM
                     logger.warning(f"Overlap detected between section {current_sec_id} (ends {current_sec['end_page']}) and {next_sec_id} (starts {next_sec['start_page']}). Adjusting {current_sec_id} end.")
                     current_sec['end_page'] = next_sec['start_page'] - 1

            # Get the end page of the (potentially adjusted) last section
            last_sec_id, last_sec = sorted_sections[-1]
            last_section_end_page = last_sec['end_page']

            # Update the chapter's end page to encompass its last section
            # Only update if the last section ends *after* the current chapter end
            if last_section_end_page > current_ch['end_page']:
                logger.debug(f"Updating chapter {current_id} end page based on last section {last_sec_id}: {current_ch['end_page']} -> {last_section_end_page}")
                current_ch['end_page'] = last_section_end_page

            # Update the main dictionary with adjusted section data for this chapter
            # This step might be redundant if sorted_chapters directly references the objects in all_chapters,
            # but explicit update is safer.
            current_ch['sections'] = {item[0]: item[1] for item in sorted_sections}
            all_chapters[current_id] = current_ch # Ensure update in the main dict

    # Phase 2: Adjust chapter boundaries based on the *next* chapter's start page
    # Re-sort based on potentially updated start pages (though unlikely to change)
    sorted_chapters = sorted([(k, v) for k, v in all_chapters.items() if isinstance(v, dict) and isinstance(v.get('start_page'), int)],
                             key=lambda x: x[1]['start_page'])

    for i in range(len(sorted_chapters) - 1):
        current_id, current_ch = sorted_chapters[i]
        next_id, next_ch = sorted_chapters[i+1]

        # Adjust current chapter's end page if there's a gap before the next chapter
        if current_ch['end_page'] < next_ch['start_page'] - 1:
            logger.debug(f"Adjusting end page for chapter {current_id} based on next chapter {next_id}: {current_ch['end_page']} -> {next_ch['start_page'] - 1}")
            current_ch['end_page'] = next_ch['start_page'] - 1
        elif current_ch['end_page'] >= next_ch['start_page']: # Handle overlap
             logger.warning(f"Overlap detected between chapter {current_id} (ends {current_ch['end_page']}) and {next_id} (starts {next_ch['start_page']}). Adjusting {current_id} end.")
             current_ch['end_page'] = next_ch['start_page'] - 1

    # Phase 3: Ensure the very last chapter ends at the document end
    if sorted_chapters:
        last_id, last_ch = sorted_chapters[-1]
        if last_ch['end_page'] < total_pages:
             logger.debug(f"Adjusting end page for very last item {last_id}: {last_ch['end_page']} -> {total_pages}")
             last_ch['end_page'] = total_pages
        # Also ensure the last section within the last chapter ends correctly
        if 'sections' in last_ch and isinstance(last_ch.get('sections'), dict) and last_ch['sections']:
             valid_sections = [(sk, sv) for sk, sv in last_ch['sections'].items() if isinstance(sv, dict) and isinstance(sv.get('start_page'), int)]
             if valid_sections:
                 sorted_sections = sorted(valid_sections, key=lambda x: x[1]['start_page'])
                last_sec_id, last_sec = sorted_sections[-1]
                 if last_sec['end_page'] < last_ch['end_page']:
                     logger.debug(f"Adjusting end page for last section {last_sec_id} in last chapter {last_id}: {last_sec['end_page']} -> {last_ch['end_page']}")
                     last_sec['end_page'] = last_ch['end_page']
                 last_ch['sections'][last_sec_id] = last_sec # Update dict


    # Update the main dictionary with all adjusted data
    final_toc = {item[0]: item[1] for item in sorted_chapters}

    logger.info("Boundary adjustment complete.")
    return final_toc


# --- Main Execution Block ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a hierarchical Table of Contents (TOC) with Vision Summaries from a PDF using the Vertex AI Vision model.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("pdf_file", nargs='?', default="CoordinatedArchitectlastenboek.pdf",
                        help="Path to the input PDF file.")
    parser.add_argument("-o", "--output_base", default="vision_toc_vision_summary",
                        help="Base name for the output JSON file (e.g., 'my_project_toc_summary').")
    parser.add_argument("--log", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        help="Set the logging level.")

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(args.log.upper())
    logger.info(f"Logging level set to {args.log.upper()}")

    logger.info(f"Input PDF: {args.pdf_file}")
    logger.info(f"Output base name: {args.output_base}")

    # --- Pre-checks ---
    if not os.path.exists(args.pdf_file):
        logger.error(f"Input PDF file not found: {args.pdf_file}")
        sys.exit(1)
    if not args.pdf_file.lower().endswith('.pdf'):
        logger.warning(f"Input file '{args.pdf_file}' does not have a .pdf extension.")

    # --- Initialize Vertex AI ---
    if not initialize_vertex_ai():
        logger.error("Failed to initialize Vertex AI. Exiting.")
        sys.exit(1)

    # --- Read PDF and Get Page Count ---
    pdf_bytes = None
    total_pages = 0
    pdf_part = None # Initialize pdf_part
    try:
        logger.info(f"Reading PDF file: {args.pdf_file}")
        with open(args.pdf_file, "rb") as f:
            pdf_bytes = f.read()
        logger.info(f"PDF read successfully ({len(pdf_bytes)} bytes).")

        # Create PDF Part for API calls *once*
        pdf_part = Part.from_data(data=pdf_bytes, mime_type="application/pdf")
        logger.info("PDF Part created for Vertex AI API calls.")

        # Get page count using fitz
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        total_pages = pdf_doc.page_count
        pdf_doc.close()
        logger.info(f"PDF has {total_pages} pages.")
        if total_pages == 0:
             logger.error("PDF file seems to have 0 pages. Cannot process.")
             sys.exit(1)

    except fitz.FitzError as fitz_e:
         logger.error(f"PyMuPDF (fitz) error opening or reading {args.pdf_file}: {fitz_e}", exc_info=True)
         sys.exit(1)
    except IOError as e:
         logger.error(f"Error reading PDF file {args.pdf_file}: {e}", exc_info=True)
         sys.exit(1)
    except Exception as e:
         logger.error(f"Unexpected error during PDF reading: {e}", exc_info=True)
         sys.exit(1)


    # --- Process PDF ---
    start_time = time.time()
    logger.info("Phase 1: Starting Vision TOC generation process...")

    # Generate the TOC using batch processing, passing the pdf_part
    generated_toc = process_pdf_batches(args.pdf_file, pdf_part, total_pages)

    # --- Augment with Summaries ---
    if generated_toc and isinstance(generated_toc, dict) and pdf_part:
        logger.info("Phase 2: Starting Vision Summary generation...")
        # Process each top-level chapter for summaries
        for chapter_code, chapter_node in generated_toc.items():
             if isinstance(chapter_node, dict): # Ensure we're processing a dictionary
                 logger.info(f"Summarizing Chapter: {chapter_code} - {chapter_node.get('title', 'Unknown Title')}")
                 add_vision_summaries_recursive(chapter_node, pdf_part, node_code=chapter_code)
             else:
                 logger.warning(f"Skipping summary for invalid top-level entry: {chapter_code} (type: {type(chapter_node)}).")
        logger.info("Finished generating summaries.")
    elif not pdf_part:
         logger.error("Cannot generate summaries because PDF Part failed to create.")
    # Keep generated_toc even if summarization had issues, but maybe add a note?


    # --- Validate and Save Results ---
    if generated_toc and isinstance(generated_toc, dict):
        logger.info("Validating generated TOC (post-summarization)...")
        # Validation mainly checks page numbers, summaries are just added text
        validated_toc = validate_chapters(generated_toc, total_pages)
        logger.info(f"Validation complete. Found {len(validated_toc)} valid top-level chapters.")

        if validated_toc:
             save_results_with_index(validated_toc, args.pdf_file, args.output_base)
        else:
             logger.error("No valid chapters found after validation. No output file created.")
             sys.exit(1)

    elif generated_toc is None:
        logger.error("Failed to generate TOC. No output file created.")
        sys.exit(1)
    else:
         logger.error(f"Generated result was not a dictionary (type: {type(generated_toc)}). Cannot save. Check logs for errors.")
         sys.exit(1)

    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"Vision TOC Generator script finished in {duration:.2f} seconds.")
