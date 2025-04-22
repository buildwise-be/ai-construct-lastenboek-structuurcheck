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
# Model for initial TOC extraction (Chapters, Sections, Pages)
TOC_EXTRACTION_MODEL_NAME = os.getenv("GEMINI_TOC_EXTRACTION_MODEL", "gemini-1.5-pro-002") # Default to 1.5 Pro 002
# Model for summarizing sections (using vision capabilities)
VISION_MODEL_NAME = os.getenv("GEMINI_VISION_MODEL", "gemini-2.0-flash-001") # Default to 2.0 Flash 001


# TOC Extraction Model Config (May need different tuning than vision)
TOC_EXTRACTION_GENERATION_CONFIG = GenerationConfig(
    max_output_tokens=8192,
    temperature=0.1, # Even lower temp for structured extraction?
    top_p=0.95,
)

# Vision Model Config (Align with toc_summarizer.py examples)
VISION_GENERATION_CONFIG = GenerationConfig(
    max_output_tokens=8192, # Allow large output for complex TOCs
    temperature=0.2,      # Lower temperature for more deterministic TOC structure
    top_p=0.95,
)
# Define safety settings (Apply same settings to both for now)
COMMON_SAFETY_SETTINGS = [
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

# Global variables for initialized models
toc_extraction_model = None
vision_model = None

# --- Initialization ---
def initialize_vertex_ai():
    """Initializes the Vertex AI client and models for TOC extraction and vision."""
    global vision_model, toc_extraction_model
    if vision_model and toc_extraction_model:
        logger.debug("Vertex AI models already initialized.")
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

        # Initialize TOC Extraction Model
        if not toc_extraction_model:
            logger.info(f"Loading TOC extraction model: {TOC_EXTRACTION_MODEL_NAME}")
            toc_extraction_model = GenerativeModel(
                TOC_EXTRACTION_MODEL_NAME,
                # System instruction is passed within generate_content
            )
            logger.info("TOC extraction model loaded successfully.")
        else:
            logger.debug("TOC extraction model already initialized.")

        # Initialize Vision Model
        if not vision_model:
            logger.info(f"Loading vision model: {VISION_MODEL_NAME}")
            vision_model = GenerativeModel(
                VISION_MODEL_NAME,
                # System instruction passed within generate_content
            )
            logger.info("Vision model loaded successfully.")
        else:
             logger.debug("Vision model already initialized.")

        return True

    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI models: {e}", exc_info=True)
        vision_model = None
        toc_extraction_model = None
        return False

# --- Helper Functions ---
# System instruction - Modified for batch-focused extraction
system_instruction_text = """You are an expert system analyzing technical PDF documents, specifically Belgian/Flemish construction specifications ("lastenboek" / "bestek"). Focus ONLY on the visual content within the current page range provided.

Your Task:
Identify all headings (chapters, sections, subsections, etc.) that VISUALLY BEGIN within the current page range.

Heading Formats to look for:
- Main chapters: "XX." (e.g., "00.", "01.")
- Sections: "XX.YY." (e.g., "01.10.")
- Subsections: "XX.YY.ZZ." (e.g., "01.10.01.")
- Further levels: "XX.YY.ZZ.AA." etc.

For EACH heading identified starting within this page range:
1.  **Hierarchical Code:** Determine the exact code (e.g., "00", "01.10", "01.10.01"). Remove any trailing dots.
2.  **Title:** Extract the full title exactly as it appears following the code.
3.  **Start Page:** Determine the **GLOBAL PDF page number** (1-based index) where this heading VISUALLY APPEARS.

Crucial Instructions:
-   **Page Numbers:** Use ONLY GLOBAL PDF page numbers (1-based index).
-   **Scope:** Only report headings that START on a page within the current range.
-   **Completeness:** Be thorough in identifying all heading formats starting in these pages.
-   **NO Hierarchy/End Pages:** Do NOT attempt to build the hierarchy or determine end pages in this step. Just list the headings you find starting here.

Output Format:
Produce a **single, valid Python list literal** containing dictionaries, enclosed in ```python ... ```. Each dictionary represents one heading found starting in this range.

Example Output:
```python
[
    {
        "code": "01.10",
        "title": "Definities",
        "start_page": 5
    },
    {
        "code": "01.20",
        "title": "Toepasselijke normen",
        "start_page": 8
    },
    {
        "code": "01.20.01",
        "title": "Algemene normen",
        "start_page": 9
    }
    # ... other headings starting in this page range
]
```
Ensure the output contains ONLY the Python list within the ```python ... ``` block. Be meticulous about syntax.
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

def post_process_llm_response_to_list(response_text: str) -> list | None:
    """
    Extracts a Python list literal from the LLM's response text,
    attempting to handle common variations like ```python ... ``` blocks.
    EXPECTS A LIST, NOT A DICTIONARY.
    """
    list_str = None
    try:
        # Regex to find ```python [ ... ] ``` or just [ ... ] as fallback
        match_python = re.search(r"```python\s*(\[.*?\])\s*```", response_text, re.DOTALL)
        match_raw = re.search(r"^\s*(\[.*?\])\s*$", response_text, re.DOTALL | re.MULTILINE)

        if match_python:
            list_str = match_python.group(1)
            logger.debug("Found list within ```python block.")
        elif match_raw:
            list_str = match_raw.group(1)
            logger.debug("Found raw list structure.")
        else:
            logger.warning("Could not find Python list structure (```python ... ``` or raw [...]) in LLM response.")
            logger.debug(f"LLM Response Start: {response_text[:500]}...")
            return None

        logger.debug(f"Extracted potential list string (length {len(list_str)}). First 500 chars: {list_str[:500]}...")

        # Basic Python literal to JSON conversion (for list contents)
        list_str = list_str.replace(': None', ': null')
        list_str = list_str.replace(': True', ': true')
        list_str = list_str.replace(': False', ': false')

        try:
            # Try direct JSON parsing (JSON arrays are valid lists)
            parsed_list = json.loads(list_str)
        except json.JSONDecodeError:
            logger.warning("Direct JSON parsing failed. Trying ast.literal_eval as fallback.")
            import ast
            try:
                parsed_list = ast.literal_eval(list_str)
                # Check if the result is a list of dictionaries
                if not isinstance(parsed_list, list) or not all(isinstance(item, dict) for item in parsed_list):
                     logger.warning("ast.literal_eval result doesn't look like the expected list of dicts structure.")
                     return None
            except (ValueError, SyntaxError, MemoryError, TypeError) as ast_e:
                logger.error(f"ast.literal_eval failed: {ast_e}")
                logger.error(f"Problematic string (first 500 chars): {list_str[:500]}...")
                # logger.error(f"Full problematic string for ast.literal_eval:\n{list_str}") # Avoid logging potentially huge strings
                return None

        if isinstance(parsed_list, list):
            logger.info(f"Successfully extracted and parsed list from LLM response ({len(parsed_list)} items).")
            return parsed_list
        else:
            logger.warning(f"Parsed result is not a list: {type(parsed_list)}")
            return None

    except Exception as e:
        logger.error(f"Error post-processing LLM response to list: {e}", exc_info=True)
        if list_str:
            logger.error(f"String being processed (first 500 chars): {list_str[:500]}...")
        # logger.error(f"Original LLM response text leading to post-processing error:\n{response_text}") # Avoid logging huge response
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
                # Using VISION settings specifically for the vision model
                response = vision_model.generate_content(
                    content_parts,
                    generation_config=VISION_GENERATION_CONFIG, # Use VISION_CONFIG
                    safety_settings=COMMON_SAFETY_SETTINGS,     # Use common safety settings
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

# --- TOC Assembly Function (NEW) ---
def assemble_full_toc(extracted_items: list, total_pages: int) -> dict:
    """Assembles the final hierarchical TOC from the flat list of extracted items."""
    if not extracted_items:
        return {}

    # 1. Deduplicate based on code and start_page
    unique_items = []
    seen = set()
    for item in extracted_items:
        # Basic validation of item structure
        if not isinstance(item, dict) or 'code' not in item or 'start_page' not in item or 'title' not in item:
            logger.warning(f"Skipping invalid item during deduplication: {item}")
            continue
        # Normalize code slightly (remove potential whitespace)
        code = str(item['code']).strip()
        start_page = item['start_page']
        # Ensure start_page is a valid integer
        if not isinstance(start_page, int) or start_page < 1:
             logger.warning(f"Skipping item with invalid start_page: {item}")
             continue

        identifier = (code, start_page)
        if identifier not in seen:
            # Store with potentially cleaned code
            item['code'] = code 
            unique_items.append(item)
            seen.add(identifier)
        else:
             logger.debug(f"Duplicate item found and removed: {item}")

    logger.info(f"Reduced {len(extracted_items)} items to {len(unique_items)} unique items after deduplication.")

    # 2. Sort globally by start_page, then by code length (shallower first), then code itself
    def sort_key(item):
        code = item['code']
        return (item['start_page'], len(code.split('.')), code)

    unique_items.sort(key=sort_key)
    logger.debug("Sorted unique items by start_page and code.")

    # 3. Calculate end_page
    num_items = len(unique_items)
    for i, current_item in enumerate(unique_items):
        if 'end_page' not in current_item: # Calculate only if not somehow present
            if i < num_items - 1:
                next_item = unique_items[i+1]
                # End page is the page before the next item starts
                # Ensure end_page is not before start_page
                calculated_end = next_item['start_page'] - 1
                current_item['end_page'] = max(current_item['start_page'], calculated_end)
            else:
                # Last item goes to the end of the document
                current_item['end_page'] = total_pages
    logger.debug("Calculated end_pages for all items.")

    # 4. Reconstruct hierarchy
    toc_hierarchy = {}
    item_map = {item['code']: item for item in unique_items} # Map for easy lookup

    for item in sorted(unique_items, key=lambda x: (len(x['code'].split('.')), x['code'])): # Process top-level first
        code = item['code']
        parts = code.split('.')
        # Ensure sections dictionary exists
        if 'sections' not in item:
            item['sections'] = {}

        if len(parts) == 1:
            # Top-level chapter
            if code not in toc_hierarchy:
                toc_hierarchy[code] = item
        else:
            # Find parent
            parent_code = '.'.join(parts[:-1])
            if parent_code in item_map:
                parent_item = item_map[parent_code]
                # Ensure parent has a sections dict
                if 'sections' not in parent_item or not isinstance(parent_item['sections'], dict):
                     parent_item['sections'] = {}
                # Add current item to parent's sections
                if parts[-1] not in parent_item['sections']:
                     parent_item['sections'][parts[-1]] = item # Use the last part as the key in sections
                     # Alternative: use full code? Stick to original structure: parent['sections'][full_child_code] = item
                     # Let's stick to the original structure where keys are full codes
                     parent_item['sections'][code] = item
                else:
                     logger.warning(f"Attempted to add duplicate code {code} under parent {parent_code}")
            else:
                logger.warning(f"Could not find parent ({parent_code}) for item {code}. Orphaned item.")
                # Optionally add orphans to a separate list or top level?

    logger.info("Reconstructed TOC hierarchy.")
    return toc_hierarchy

# --- Function for saving results (modified slightly if needed) ---
def save_results_with_index(chapters_dict, input_filename, output_base_filename="vision_toc_focused"):
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

# --- Validation Function (Potentially needs adaptation later) ---
def validate_assembled_toc(chapters_dict, total_pages):
    """Validates page numbers and basic structure in the assembled TOC dictionary."""
    # This function might need more robust checks now, e.g., parent/child consistency
    # For now, keep the basic page validation from validate_chapters
    validated = {}
    reasonable_max = total_pages

    for chapter_id, chapter_data in chapters_dict.items():
        if not chapter_data or not isinstance(chapter_data, dict):
            logger.warning(f"Skipping invalid chapter entry during validation: {chapter_id}")
            continue
        
        # Check top-level chapter pages (start/end should now exist)
        if ('start_page' not in chapter_data or 'end_page' not in chapter_data or
            not isinstance(chapter_data['start_page'], int) or not isinstance(chapter_data['end_page'], int) or
            chapter_data['start_page'] < 1 or chapter_data['end_page'] > reasonable_max or
            chapter_data['start_page'] > chapter_data['end_page']):
            logger.warning(f"Chapter {chapter_id} has invalid final page numbers: {chapter_data.get('start_page', 'missing')}-{chapter_data.get('end_page', 'missing')}. Max pages: {reasonable_max}")
            continue

        # Recursively validate sections
        if 'sections' in chapter_data and isinstance(chapter_data['sections'], dict):
            chapter_data['sections'] = _validate_assembled_sections_recursive(chapter_data['sections'], reasonable_max, chapter_id)

        validated[chapter_id] = chapter_data
    
    logger.info("Validation of assembled TOC page numbers complete.")
    return validated

def _validate_assembled_sections_recursive(sections_dict, max_pages, parent_id):
    """Helper function to recursively validate section page numbers in assembled TOC."""
    valid_sections = {}
    for section_id, section_data in sections_dict.items(): # Iterate through the values (which are the items)
        if not section_data or not isinstance(section_data, dict):
            logger.warning(f"Skipping invalid section entry during validation under {parent_id}: {section_id}")
            continue
        
        actual_code = section_data.get('code', section_id) # Get the real code from the item

        if ('start_page' not in section_data or 'end_page' not in section_data or
            not isinstance(section_data['start_page'], int) or not isinstance(section_data['end_page'], int) or
            section_data['start_page'] < 1 or section_data['end_page'] > max_pages or
            section_data['start_page'] > section_data['end_page']):
            logger.warning(f"Section {actual_code} (under {parent_id}) has invalid final page numbers: {section_data.get('start_page', 'missing')}-{section_data.get('end_page', 'missing')}. Max pages: {max_pages}")
            continue

        # Recursively validate nested sections
        if 'sections' in section_data and isinstance(section_data['sections'], dict):
            section_data['sections'] = _validate_assembled_sections_recursive(section_data['sections'], max_pages, actual_code)

        valid_sections[section_id] = section_data # Keep original key structure
    return valid_sections

# --- Main Execution Logic ---
def process_pdf_batches(pdf_path: str, pdf_part: Part, total_pages: int):
    """Processes the PDF in batches to generate a flat list of TOC items using Vertex AI."""
    global toc_extraction_model
    if not toc_extraction_model:
        logger.error("TOC Extraction model not initialized. Cannot process.")
        return None

    # Change from dict to list to collect items from all batches
    all_extracted_items = [] 
    processed_batches = 0

    # --- Batching Logic ---
    page_batch_size = 20
    if total_pages > 300:
        page_batch_size = 15
    elif total_pages > 500:
        page_batch_size = 10

    overlap = 5
    page_batches = []
    current_page = 1
    while current_page <= total_pages:
        start_page = current_page
        end_page = min(start_page + page_batch_size - 1, total_pages)
        page_batches.append((start_page, end_page))
        # Move to the next page after the overlap
        current_page = start_page + page_batch_size - overlap
        if current_page <= start_page: # Prevent infinite loop if batch_size <= overlap
            current_page = start_page + 1 
            
    # Ensure the last batch covers the end page
    if page_batches and page_batches[-1][1] < total_pages:
         last_start, _ = page_batches[-1]
         page_batches[-1] = (last_start, total_pages)
         
    logger.info(f"Created {len(page_batches)} page batches (size ~{page_batch_size}, overlap {overlap}).")
    # --- Loop Through Batches ---
    max_retries_per_batch = 2
    
    for i, (start_page, end_page) in enumerate(page_batches):
        processed_batches += 1
        logger.info(f"Processing Batch {processed_batches}/{len(page_batches)}: Pages {start_page}-{end_page}")
        batch_success = False
        for attempt in range(max_retries_per_batch + 1):
            try:
                # Define content for the LLM call using the new system instruction
                content_parts = [
                    system_instruction_text, 
                    pdf_part
                ]
                
                logger.debug(f"Sending request to TOC extraction model for batch {processed_batches} (Attempt {attempt+1})...")
                # Use the TOC_EXTRACTION_MODEL and its specific config
                response = toc_extraction_model.generate_content(
                    content_parts,
                    generation_config=TOC_EXTRACTION_GENERATION_CONFIG, # Use TOC_EXTRACTION_CONFIG
                    safety_settings=COMMON_SAFETY_SETTINGS,             # Use common safety settings
                    stream=False
                )
                logger.debug(f"Received response from TOC extraction model for batch {processed_batches}.")

                # Check for safety blocks
                if response.prompt_feedback and response.prompt_feedback.block_reason:
                     block_reason = response.prompt_feedback.block_reason
                     logger.warning(f"LLM call blocked for batch {processed_batches} (Attempt {attempt+1}): {block_reason}")
                     break # Exit retry loop for this batch if blocked
                
                # Post-process the response (expecting a LIST now)
                extracted_list = post_process_llm_response_to_list(response.text)

                if extracted_list is not None: # Can be an empty list [] which is valid
                    logger.info(f"Batch {processed_batches}: Successfully extracted {len(extracted_list)} items.")
                    # Filter items to ensure start_page is within the current batch range
                    filtered_items = [
                        item for item in extracted_list 
                        if isinstance(item.get('start_page'), int) and 
                           start_page <= item['start_page'] <= end_page
                    ]
                    if len(filtered_items) < len(extracted_list):
                        logger.info(f"Filtered out {len(extracted_list) - len(filtered_items)} items whose start_page was outside batch range {start_page}-{end_page}.")
                    
                    all_extracted_items.extend(filtered_items)
                    batch_success = True
                    break # Success for this batch
                else:
                    logger.warning(f"Batch {processed_batches}: Failed to extract list from LLM response (Attempt {attempt+1}).")
                    # Continue to retry if attempts remain

            except Exception as e:
                logger.error(f"Error processing batch {processed_batches} (Pages {start_page}-{end_page}), Attempt {attempt+1}: {e}", exc_info=True)
            
            # Retry logic
            if not batch_success and attempt < max_retries_per_batch:
                logger.info(f"Retrying batch {processed_batches} after delay...")
                time.sleep(5 * (attempt + 1)) # Longer backoff for core extraction
        
        if not batch_success:
             logger.error(f"Failed to process batch {processed_batches} (Pages {start_page}-{end_page}) after {max_retries_per_batch + 1} attempts. Skipping batch.")
             # Consider whether to halt entirely or continue with potentially missing data

    logger.info(f"Finished processing all batches. Total items extracted (before assembly): {len(all_extracted_items)}")
    return all_extracted_items

# --- Main Function (Modified) ---
def main(pdf_path: str):
    """Main function to orchestrate TOC generation."""
    if not initialize_vertex_ai():
        sys.exit(1) # Exit if initialization fails

    # Get total page count using fitz
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close() # Close the document
        if total_pages == 0:
             logger.error(f"PDF file '{pdf_path}' has 0 pages.")
             sys.exit(1)
        logger.info(f"PDF '{pdf_path}' has {total_pages} pages.")
    except Exception as e:
        logger.error(f"Failed to open PDF or get page count: {e}")
        sys.exit(1)

    # Prepare PDF Part for Vertex AI by loading local bytes
    pdf_bytes = None
    try:
        logger.info(f"Loading PDF file locally: {pdf_path}")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        if not pdf_bytes:
             raise ValueError("Failed to read PDF bytes or file is empty.")

        pdf_part = Part.from_data(
            mime_type="application/pdf",
            data=pdf_bytes # Pass the raw bytes
        )
        logger.info("PDF Part prepared from local file bytes for Vertex AI.")

    except FileNotFoundError:
        logger.error(f"PDF file not found at path: {pdf_path}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to read PDF file or create Part from data: {e}", exc_info=True)
        sys.exit(1)

    # --- Run Batch Processing ---
    logger.info("Starting PDF batch processing for TOC item extraction...")
    start_time = time.time()
    # ** Pass pdf_path for potential text extraction and pdf_part for vision model **
    # Note: process_pdf_batches might need adjustment if it cannot handle raw bytes efficiently
    extracted_items_flat_list = process_pdf_batches(pdf_path, pdf_part, total_pages)
    extraction_time = time.time() - start_time
    logger.info(f"Batch processing completed in {extraction_time:.2f} seconds.")

    if extracted_items_flat_list is None:
        logger.error("TOC item extraction failed during batch processing.")
        sys.exit(1)
    if not extracted_items_flat_list:
         logger.warning("No TOC items were extracted from the PDF after batch processing.")
         final_toc = {} # Empty TOC
    else:
        # --- Assemble Full TOC --- 
        logger.info(f"Assembling final TOC hierarchy from {len(extracted_items_flat_list)} extracted items...")
        start_time = time.time()
        # ** Call the assembly function **
        assembled_toc = assemble_full_toc(extracted_items_flat_list, total_pages)
        assembly_time = time.time() - start_time
        logger.info(f"TOC assembly completed in {assembly_time:.2f} seconds.")

        # --- Validate Assembled TOC --- 
        logger.info("Validating assembled TOC...")
        # ** Call the correct validation function **
        final_toc = validate_assembled_toc(assembled_toc, total_pages)
        logger.info("TOC validation complete.")

    # --- Add Summaries (Optional Step) ---
    should_summarize = True # Set to False to skip summarization for now
    if should_summarize and final_toc:
        logger.info("Starting recursive summary generation for TOC nodes...")
        start_time = time.time()
        # ** Pass the same pdf_part (containing bytes) to summarization **
        # Note: add_vision_summaries_recursive might also need adjustment
        for chapter_code, chapter_node in final_toc.items():
            add_vision_summaries_recursive(chapter_node, pdf_part, node_code=chapter_code)
        summarization_time = time.time() - start_time
        logger.info(f"Summary generation finished in {summarization_time:.2f} seconds.")
    elif not final_toc:
         logger.info("Skipping summary generation as the assembled TOC is empty.")
    else:
         logger.info("Skipping summary generation as per configuration.")

    # --- Save Final Results --- 
    # ** Save the final_toc **
    save_results_with_index(final_toc, pdf_path)

# --- Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a hierarchical TOC with summaries from a PDF using Vertex AI Vision Model.")
    # Make pdf_path an optional positional argument with a default value
    parser.add_argument("pdf_path", type=str, nargs='?', default="CoordinatedArchitectlastenboek.pdf", 
                        help="Path to the input PDF file (defaults to CoordinatedArchitectlastenboek.pdf in the current directory).")
    # Add other arguments as needed (e.g., --no-summaries, --output-name)
    args = parser.parse_args()

    # Basic check for PDF existence (using the resolved path)
    pdf_to_check = args.pdf_path
    if not os.path.isfile(pdf_to_check):
        logger.error(f"Input PDF file not found: {pdf_to_check}")
        # Check if it's the default that's missing
        if pdf_to_check == "CoordinatedArchitectlastenboek.pdf":
             logger.error("Default PDF 'CoordinatedArchitectlastenboek.pdf' not found in the current directory.")
             logger.error("Please provide the path to your PDF or place the default file here.")
        sys.exit(1)
        
    # Ensure the PDF is accessible, potentially upload to GCS first
    # (Add GCS upload logic here if needed, using GOOGLE_CLOUD_BUCKET_NAME)
    # Example: ensure_pdf_on_gcs(args.pdf_path, os.getenv('GOOGLE_CLOUD_BUCKET_NAME'))

    main(args.pdf_path)
