import PyPDF2
import json
import os
import logging
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting
import google.auth

# Configure logging (optional but good practice)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# ----------------------------------------------------------------
# STEP 1: LOAD TOC (already in JSON format)
# ----------------------------------------------------------------
# You might load this from a separate .json file in a real application
toc_json_str = """
{
    "00": {
        "start": 3,
        "end": 7,
        "title": "ALGEMEENHEDEN.",
        "sections": {
            "00.01": {
                "start": 3,
                "end": 3,
                "title": "MONSTERS, STALEN, MODELLEN."
            },
            "00.02": {
                "start": 3,
                "end": 4,
                "title": "UITVOERING EN OPMETEN."
            }
        }
    },
    "09": {
        "start": 7,
        "end": 8,
        "title": "VEILIGHEID",
        "sections": {
            "09.10": {
                "start": 7,
                "end": 7,
                "title": "VEILIGHEIDSPLAN ONTWERP"
            }
        }
    }
}
"""

toc = json.loads(toc_json_str)

# ----------------------------------------------------------------
# STEP 2: LOAD THE PDF (REMOVED FROM TOP LEVEL)
# ----------------------------------------------------------------
# The following lines caused errors during import in app.py and are not needed
# for get_toc_page_ranges_from_json, which only uses the `toc` variable.
# PDF_PATH = "your_lastenboek.pdf" 
# if not os.path.exists(PDF_PATH):
#     raise FileNotFoundError(f"PDF file not found at path: {PDF_PATH}. Please update the PDF_PATH variable.")
# reader = PyPDF2.PdfReader(open(PDF_PATH, 'rb'))
# num_pages = len(reader.pages)

# ----------------------------------------------------------------
# STEP 3: RECURSIVELY PARSE TOC AND EXTRACT TEXT CHUNKS
# ----------------------------------------------------------------

# Note: extract_section_text is not used in the page range extraction,
# but kept here for potential future use or if refactoring for text extraction later.
def extract_section_text(pdf_reader, num_pages, start_page: int, end_page: int) -> str:
    """Extracts text from the PDF for pages [start_page..end_page]."""
    # ... (Implementation remains the same, but ensure pdf_reader and num_pages are passed)
    text_content = []
    actual_start = max(0, start_page)
    actual_end = min(num_pages - 1, end_page)
    for p in range(actual_start, actual_end + 1):
        try:
            page = pdf_reader.pages[p]
            page_text = page.extract_text() or ""
            text_content.append(page_text)
        except IndexError:
            logger.warning(f"Page index {p} out of range (Total pages: {num_pages}). Skipping.")
        except Exception as e:
            logger.warning(f"Could not extract text from page {p}. Error: {e}. Skipping.")
    return "\n".join(text_content)

def _traverse_toc_for_ranges(node: dict, code: str, page_ranges: dict):
    """
    Internal recursive helper to extract page ranges from the TOC structure.
    Populates the page_ranges dictionary.
    """
    start = node.get("start")
    end = node.get("end")
    title = node.get("title", "Untitled Section")

    # Store page range if valid and code exists
    if code and isinstance(start, int) and isinstance(end, int) and start >= 0 and end >= start:
        page_ranges[code] = {
            "title": title,
            "start": start,
            "end": end
        }
    elif code:
        logger.warning(f"Invalid or missing page range for code {code} ('{title}'). Start: {start}, End: {end}. Skipping range storage.")

    # Traverse subsections if they exist
    sub_sections = node.get("sections", {})
    if isinstance(sub_sections, dict):
        for subcode, subnode in sub_sections.items():
            if isinstance(subnode, dict):
                _traverse_toc_for_ranges(subnode, code=subcode, page_ranges=page_ranges)
            else:
                logger.warning(f"Expected dictionary for subsection {subcode}, but got {type(subnode)}. Skipping subsection.")

def get_toc_page_ranges_from_json(toc_data: dict) -> dict:
    """
    Processes a loaded TOC dictionary (from JSON) and extracts a flat dictionary
    mapping specific item codes to their titles and page ranges.

    Args:
        toc_data: The dictionary loaded from the TOC JSON.

    Returns:
        A dictionary mapping item codes (e.g., "00.01", "11.03.01") to
        a dictionary containing at least "title" and potentially "start", "end", 
        and "lastenboek_summary". Start/end might be missing if invalid.
    """
    page_ranges = {}
    
    # Detect if this is a standard TOC or vision TOC format
    is_vision_format = False
    for code, node in toc_data.items():
        if isinstance(node, dict) and ("start_page" in node or "end_page" in node): # More lenient detection
            is_vision_format = True
            logger.info(f"Detected potential vision TOC format key in item '{code}': start_page={node.get('start_page')}, end_page={node.get('end_page')}")
            break # Assume vision if keys are present
            
    if is_vision_format:
        logger.info("Processing using vision TOC format logic (start_page/end_page keys expected)")
        
        def _try_convert_page(page_val, page_name, code):
            """Helper to check, convert, and log page number processing."""
            if page_val is None:
                logger.debug(f"Node '{code}': {page_name} is None.")
                return None
            if isinstance(page_val, int):
                logger.debug(f"Node '{code}': {page_name} is already int: {page_val}")
                return page_val
            if isinstance(page_val, str):
                logger.debug(f"Node '{code}': {page_name} is string '{page_val}'. Attempting conversion.")
                try:
                    converted = int(page_val)
                    logger.info(f"Node '{code}': Successfully converted string {page_name} '{page_val}' to int: {converted}")
                    return converted
                except ValueError:
                    logger.warning(f"Node '{code}': Failed to convert string {page_name} '{page_val}' to int.")
                    return None
            # Handle other unexpected types like float etc.
            logger.warning(f"Node '{code}': Unexpected type for {page_name}: {type(page_val)}, value: {page_val}. Treating as invalid.")
            return None

        def extract_vision_toc_ranges(code, node, page_ranges, parent_code=None):
            if not isinstance(node, dict):
                logger.warning(f"Skipping non-dict node for code '{code}' (parent: {parent_code})")
                return

            title = node.get("title", "Untitled Section")
            summary = node.get("summary")
            raw_start_page = node.get("start_page")
            raw_end_page = node.get("end_page")
            
            logger.debug(f"Processing node '{code}' (parent: {parent_code}): title='{title}', raw_start={raw_start_page} (type: {type(raw_start_page)}), raw_end={raw_end_page} (type: {type(raw_end_page)})")

            # Prepare item data, always include title and summary if present
            item_data = {"title": title}
            if summary and isinstance(summary, str) and summary.strip():
                item_data["lastenboek_summary"] = summary.strip()

            # Try processing/converting page numbers
            processed_start = _try_convert_page(raw_start_page, "start_page", code)
            processed_end = _try_convert_page(raw_end_page, "end_page", code)

            page_range_found_directly = False
            if processed_start is not None and processed_end is not None:
                # Basic sanity check: end >= start
                if processed_end >= processed_start:
                    item_data["start"] = processed_start
                    item_data["end"] = processed_end
                    page_ranges[code] = item_data
                    page_range_found_directly = True
                    logger.info(f"✅ Stored valid page range for '{code}': {processed_start}-{processed_end}")
                else:
                    logger.warning(f"⚠️ Invalid range logic for '{code}': end_page ({processed_end}) < start_page ({processed_start}). Skipping direct assignment.")
            else:
                 logger.debug(f"Node '{code}': Direct page range is invalid or incomplete (start: {processed_start}, end: {processed_end}). Will check parent.")

            # If no direct valid range, try inheriting from parent
            if not page_range_found_directly:
                if parent_code and parent_code in page_ranges:
                    parent_data = page_ranges[parent_code]
                    # Check if parent HAS valid start/end keys before inheriting
                    parent_start = parent_data.get("start")
                    parent_end = parent_data.get("end")
                    if parent_start is not None and parent_end is not None and isinstance(parent_start, int) and isinstance(parent_end, int):
                        item_data["start"] = parent_start
                        item_data["end"] = parent_end
                        page_ranges[code] = item_data # Store item with inherited range
                        logger.info(f"➡️ Inherited page range for '{code}' from parent '{parent_code}': {parent_start}-{parent_end}")
                    else:
                        logger.warning(f"⚠️ Parent '{parent_code}' found for '{code}', but parent lacks valid start/end pages. Cannot inherit range.")
                        page_ranges[code] = item_data # Store item without page range
                else:
                    # No valid direct range and no valid parent range found
                    logger.warning(f"⚠️ No valid page range found directly or via parent for '{code}'. Storing item without start/end.")
                    page_ranges[code] = item_data # Store item without page range

            # Process sections recursively, passing the current code as the parent code
            sections = node.get("sections", {})
            if isinstance(sections, dict):
                for subcode, subnode in sections.items():
                    # Make sure subcode is prefixed correctly if needed (though vision usually has full codes)
                    # full_subcode = f"{code}.{subcode}" if not subcode.startswith(code) else subcode 
                    extract_vision_toc_ranges(subcode, subnode, page_ranges, parent_code=code) # Pass current code as parent
            elif sections: # Log if sections exist but aren't a dict
                 logger.warning(f"Node '{code}' has a 'sections' key, but it's not a dictionary (type: {type(sections)}). Cannot process subsections.")

        # Process the top-level nodes
        for code, node in toc_data.items():
            extract_vision_toc_ranges(code, node, page_ranges, parent_code=None) # Top level has no parent
            
    else:
        # Standard TOC format - use existing traversal logic
        logger.info("Processing using standard TOC format logic (start/end keys expected)")
        # --- Standard TOC Helper ---
        def _traverse_toc_for_ranges(node: dict, code: str, page_ranges: dict):
            """
            Internal recursive helper for standard TOC format.
            Populates the page_ranges dictionary.
            """
            start = node.get("start")
            end = node.get("end")
            title = node.get("title", "Untitled Section")
            summary = node.get("summary") # Also get summary here

            # Prepare item data
            item_data = {"title": title}
            if summary and isinstance(summary, str) and summary.strip():
                 item_data["lastenboek_summary"] = summary.strip()


            # Store page range if valid and code exists
            if code and isinstance(start, int) and isinstance(end, int) and start >= 0 and end >= start:
                item_data["start"] = start
                item_data["end"] = end
                page_ranges[code] = item_data
                logger.debug(f"✅ Stored valid standard page range for '{code}': {start}-{end}")
            elif code:
                # Store item even without valid range
                page_ranges[code] = item_data 
                logger.warning(f"⚠️ Invalid or missing standard page range for code {code} ('{title}'). Start: {start}, End: {end}. Storing item without range.")

            # Traverse subsections if they exist
            sub_sections = node.get("sections", {})
            if isinstance(sub_sections, dict):
                for subcode, subnode in sub_sections.items():
                    if isinstance(subnode, dict):
                        _traverse_toc_for_ranges(subnode, code=subcode, page_ranges=page_ranges)
                    else:
                        logger.warning(f"Standard TOC: Expected dictionary for subsection {subcode}, but got {type(subnode)}. Skipping subsection.")
        # --- End Standard TOC Helper ---
                        
        for top_level_code, top_level_node in toc_data.items():
            if isinstance(top_level_node, dict):
                _traverse_toc_for_ranges(top_level_node, code=top_level_code, page_ranges=page_ranges)
            else:
                logger.warning(f"Standard TOC: Expected dictionary for top-level code {top_level_code}, but got {type(top_level_node)}. Skipping top-level item.")

    # Final check and summary log
    items_with_range = sum(1 for item in page_ranges.values() if 'start' in item and 'end' in item)
    items_without_range = len(page_ranges) - items_with_range
    logger.info(f"Finished processing TOC data. Extracted {len(page_ranges)} total items.")
    logger.info(f"  Items with valid page ranges: {items_with_range}")
    logger.info(f"  Items without valid page ranges: {items_without_range}")
    # Log first few items as sample
    sample_count = min(5, len(page_ranges))
    if sample_count > 0:
        logger.info(f"Sample of extracted items ({sample_count}/{len(page_ranges)}):")
        sample_items = list(page_ranges.items())[:sample_count]
        for code, info in sample_items:
             range_str = f"{info.get('start', 'N/A')}-{info.get('end', 'N/A')}"
             summary_present = "lastenboek_summary" in info
             logger.info(f"  - '{code}': title='{info.get('title')}', range={range_str}, summary={summary_present}")

    return page_ranges

# ----------------------------------------------------------------
# STEP 4: (REMOVED - Now done in get_toc_page_ranges_from_json)
# ----------------------------------------------------------------

# --- The rest of the file (LLM config, API call, analysis function) remains --- 
# --- but is currently unused by the new function. Can be removed or kept --- 
# --- for future implementation of text/vision analysis.                --- 

# (Keep Vertex AI init and call_llm_api for now, might need later)

# ----------------------------------------------------------------
# STEP 5: CONFIGURE AND SEND CHUNKS TO GEMINI FOR ANALYSIS (USING VERTEX AI)
# ----------------------------------------------------------------

# Vertex AI configuration constants (based on the example)
GENERATION_CONFIG = {
    "max_output_tokens": 8192,
    "temperature": 1,
    "top_p": 0.95,
}

SAFETY_SETTINGS = [
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_NONE # Changed from OFF to BLOCK_NONE
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_NONE
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_NONE
    ),
    SafetySetting(
        category=SafetySetting.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=SafetySetting.HarmBlockThreshold.BLOCK_NONE
    ),
]

# Initialize Vertex AI
# Try to get Project ID from environment, but fall back to gcloud default if not set.
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1") # Default to europe-west1 if not set

if not PROJECT_ID:
    try:
        _, PROJECT_ID = google.auth.default()
        if PROJECT_ID:
            logger.info(f"GOOGLE_CLOUD_PROJECT not set, but successfully discovered project from gcloud: '{PROJECT_ID}'")
        else:
            # This case can happen if ADC is set up but no quota project is configured.
            logger.error("Could not discover Google Cloud Project ID. The project ID is missing from your credentials. Please run 'gcloud auth application-default set-quota-project YOUR_PROJECT_ID'.")
            raise ValueError("Google Cloud Project ID not found in credentials.")
    except google.auth.exceptions.DefaultCredentialsError as e:
        logger.error(f"Google Cloud authentication failed. Could not discover default credentials. Please run 'gcloud auth application-default login' and ensure your environment is configured correctly. Details: {e}")
        raise ValueError("Google Cloud Project ID not found due to authentication failure.")

try:
    vertexai.init(project=PROJECT_ID, location=LOCATION) # Removed credentials=None to allow default discovery
    logger.info(f"Successfully initialized Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {str(e)}")
    raise

# Choose a Gemini model (match the example: 'gemini-1.5-pro-001' or 'gemini-1.5-flash')
# Note: The example uses gemini-1.5-pro-001 for multimodal (TOC), and allows selecting others later.
# We'll use a text model here as we are processing text chunks.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash") # Use 2.5 flash model as default

try:
    # Initialize the specific model
    model = GenerativeModel(
        MODEL_NAME,
        generation_config=GENERATION_CONFIG,
        safety_settings=SAFETY_SETTINGS
        # system_instruction=... # Optional: Add system instruction if needed
    )
    logger.info(f"Successfully initialized Generative Model: {MODEL_NAME}")
except Exception as e:
     logger.error(f"Failed to initialize GenerativeModel {MODEL_NAME}: {str(e)}")
     raise


def call_llm_api(chunk_text: str, task_description: str = "") -> str:
    """
    Calls the configured Vertex AI Generative Model.
    - chunk_text: the text from the section
    - task_description: any instructions for the LLM
    Returns the LLM's response as a string.
    Handles potential API errors gracefully.
    """
    if not chunk_text or not chunk_text.strip():
        return "Skipped: Section content is empty."

    prompt = f"{task_description}\n\nText:\n{chunk_text}"

    try:
        # Vertex AI uses generate_content directly on the model instance
        response = model.generate_content(
            prompt
            # Note: generation_config and safety_settings are set during model initialization
            )

        # Access the text content from the response object
        # Vertex AI response structure might differ, common access is via .text
        if hasattr(response, 'text'):
            return response.text
        # Handle potential blocking or empty parts
        elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
            return f"Blocked due to: {response.prompt_feedback.block_reason}"
        elif not response.candidates or not response.candidates[0].content.parts:
             return "No response generated or content is empty."
        else:
            # Fallback for potentially different structures
            # This might need adjustment based on actual Vertex AI response object inspection
            try:
                return response.candidates[0].content.parts[0].text
            except (AttributeError, IndexError):
                 logger.warning(f"Could not extract text from response structure: {response}")
                 return "Error: Could not parse response text."

    # Handle specific Vertex AI exceptions if needed, otherwise general Exception
    except Exception as e:
        logger.error(f"Error calling Vertex AI API: {e}", exc_info=True) # Log traceback
        return f"Error: Could not get response from LLM. Details: {e}"


# A sample analysis function that sends each chunk to the LLM
# This function might be adapted or called by app.py later
def analyze_sections_with_llm(sections: list):
    results = []
    total_sections = len(sections)
    for i, sec in enumerate(sections):
        code = sec.get("code", "N/A") # Use .get for safety
        title = sec.get("title", "N/A")
        content = sec.get("content", "")

        # Example Instruction: Adapt this to your specific needs
        instruction = f"""Analyze the following section (Code: {code}, Title: {title}).
        Focus on identifying:
        1. Key requirements or specifications mentioned.
        2. Any potential ambiguities, contradictions, or missing information.
        3. References to other codes or standards.
        Present the analysis clearly and concisely."""

        print(f"\n[{i+1}/{total_sections}] Sending code: {code} - {title} to {MODEL_NAME}...")

        # Only call API if content exists
        if content.strip():
            llm_output = call_llm_api(content, task_description=instruction)
        else:
            llm_output = "Skipped: Section content was empty."
            print("Skipping LLM call because section content is empty.")


        # Store the LLM's response
        results.append({
            "code": code,
            "title": title,
            "analysis": llm_output
        })
        # Optional: Add a small delay to respect API rate limits if needed
        # time.sleep(1)

    return results

# --- REMOVED OLD EXECUTION LOGIC --- 
# The following block ran during import and caused errors.
# Analysis orchestration is now handled by app.py.
# print("Starting LLM analysis...")
# llm_results = analyze_sections_with_llm(section_chunks)
# print("LLM analysis finished.")
# 
# # ----------------------------------------------------------------
# # STEP 6: DO SOMETHING WITH THE RESULTS (OLD)
# # ----------------------------------------------------------------
# output_filename = "analysis_results.json"
# try:
#     with open(output_filename, "w", encoding="utf-8") as f:
#         json.dump(llm_results, f, ensure_ascii=False, indent=2)
#     print(f"LLM analysis complete! Results saved to {output_filename}.")
# except IOError as e:
#     print(f"Error writing results to {output_filename}: {e}")
# 
# # Example of how to access a specific result (OLD)
# # if llm_results:
# #    print("\nExample result for the first analyzed section:")
# #    print(json.dumps(llm_results[0], indent=2, ensure_ascii=False))
# --- END REMOVED OLD EXECUTION LOGIC --- 