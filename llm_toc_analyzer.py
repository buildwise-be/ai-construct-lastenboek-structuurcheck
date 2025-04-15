import PyPDF2
import json
import os
import logging
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, SafetySetting

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
        {"title": str, "start": int, "end": int}.
    """
    page_ranges = {}
    for top_level_code, top_level_node in toc_data.items():
        if isinstance(top_level_node, dict):
            # Pass the top-level code itself when starting traversal for that branch
            _traverse_toc_for_ranges(top_level_node, code=top_level_code, page_ranges=page_ranges)
        else:
            logger.warning(f"Expected dictionary for top-level code {top_level_code}, but got {type(top_level_node)}. Skipping top-level item.")

    logger.info(f"Extracted {len(page_ranges)} item codes with page ranges from TOC data.")
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
# IMPORTANT: Requires GOOGLE_CLOUD_PROJECT environment variable to be set
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1") # Default to europe-west1 if not set

if not PROJECT_ID:
    raise ValueError("Google Cloud Project ID not found. Please set the GOOGLE_CLOUD_PROJECT environment variable.")

try:
    vertexai.init(project=PROJECT_ID, location=LOCATION)
    logger.info(f"Successfully initialized Vertex AI (Project: {PROJECT_ID}, Location: {LOCATION})")
except Exception as e:
    logger.error(f"Failed to initialize Vertex AI: {str(e)}")
    raise

# Choose a Gemini model (match the example: 'gemini-1.5-pro-001' or 'gemini-1.5-flash')
# Note: The example uses gemini-1.5-pro-001 for multimodal (TOC), and allows selecting others later.
# We'll use a text model here as we are processing text chunks.
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001") # Use 2.0 flash model as default

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