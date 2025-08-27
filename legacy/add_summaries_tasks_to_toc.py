import os
import json
import sys
import argparse
import time
import re
import io
import random # Add random for jitter
from PIL import Image
import fitz  # PyMuPDF
from google.api_core import exceptions as api_core_exceptions # Import specific exceptions
# import google.generativeai as genai # Remove standard genai

# --- Add Vertex AI imports --- 
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel, Part
    VERTEX_AI_AVAILABLE = True
    print("Vertex AI libraries found.")
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("Error: Vertex AI libraries not found. Please install google-cloud-aiplatform.")
    sys.exit(1)
# ---------------------------

# --- Configuration ---
# API Key configuration is no longer needed for Vertex AI (uses ADC)
# DEFAULT_API_KEY = "AIzaSy..." 
# api_key = os.environ.get("GEMINI_API_KEY") or DEFAULT_API_KEY
# if api_key == DEFAULT_API_KEY and "AIzaSy" in api_key: 
#     print("Warning: Using a placeholder API key...")
    
# try:
#     genai.configure(api_key=api_key)
#     print("Gemini API configured.")
# except Exception as e:
#     print(f"Error configuring Gemini API: {e}")
#     sys.exit(1)

# --- Vertex AI Configuration (Add these) ---
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1") # Or your preferred location

if not PROJECT_ID:
     print("Error: GOOGLE_CLOUD_PROJECT environment variable not set. Required for Vertex AI.")
     sys.exit(1)
# ----------------------------------------

# Model Configuration
# DEFAULT_MODEL_NAME = "gemini-1.5-pro-latest" # Keep this, used by argparse default
DEFAULT_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001") # Default to 2.0 flash for Vertex
GENERATION_CONFIG = {
    "temperature": 0.5,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192, # Reverted to standard limit
    "response_mime_type": "text/plain", # Model will be asked to output JSON in the text
}

# --- Default File Paths (Modify if needed) ---
# Define reasonable defaults, perhaps relative to the script directory or a common data folder
DEFAULT_JSON_INPUT_PATH = "path/to/your/default_chapters.json" # CHANGE THIS
DEFAULT_PDF_INPUT_PATH = "path/to/your/default_document.pdf"   # CHANGE THIS

# --- Helper Functions ---

def extract_pages_as_images(pdf_doc, start_page, end_page):
    """Extracts a range of pages from a PDF document as PIL Image objects."""
    images = []
    # fitz uses 0-based index, input pages are 1-based
    start_index = max(0, start_page - 1)
    end_index = min(len(pdf_doc) - 1, end_page - 1)

    if start_index > end_index:
         print(f"Warning: Invalid page range ({start_page}-{end_page}). Start index {start_index} > end index {end_index}. Skipping image extraction.")
         return []

    print(f"  Extracting pages {start_page} to {end_page} (indices {start_index} to {end_index})...", end="")
    try:
        for page_num in range(start_index, end_index + 1):
            page = pdf_doc.load_page(page_num)
            # Increase DPI for better OCR/analysis if needed (default is 72)
            zoom = 2 # 2x zoom -> 144 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes()))
            images.append(img)
        print(f" Extracted {len(images)} images.")
    except Exception as e:
        print(f"\nError extracting page {page_num + 1}: {e}")
        # Decide if you want to return partial list or empty
        return [] # Return empty list on error for safety
    return images

def extract_json_from_response(response_text):
    """Extracts a JSON object from the model's text response, looking for markdown code blocks."""
    # 1. Try finding JSON within ```json ... ``` block
    match = re.search(r'```json\s*({.*?})\s*```', response_text, re.DOTALL | re.IGNORECASE)
    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"  Error decoding JSON from code block: {e}")
            print(f"  Code block content: {json_str}")
            # Fall through to try parsing the whole text

    # 2. If no code block found or parsing failed, try parsing the whole text (less reliable)
    try:
        # Basic cleaning: remove potential markdown backticks if they weren't caught by regex
        cleaned_text = response_text.strip().strip('`')
        # Sometimes the model might just output the JSON without the markdown block
        if cleaned_text.startswith("{") and cleaned_text.endswith("}"):
             return json.loads(cleaned_text)
        else:
             print("  Warning: No JSON code block found and response doesn't look like a raw JSON object.")
             return None # Indicate failure to find JSON

    except json.JSONDecodeError as e:
        print(f"  Error decoding JSON from full response text: {e}")
        print(f"  Full response text: {response_text[:500]}...") # Log snippet
        return None
    except Exception as e:
        print(f"  Unexpected error during JSON extraction: {e}")
        return None

def analyze_content_with_gemini(model: GenerativeModel, images: list, context_info: dict):
    """Analyzes images using the Vertex AI GenerativeModel, expecting a JSON response.
       Processes images spanning a full chapter, but focuses output on a specific section.
    """
    if not VERTEX_AI_AVAILABLE:
         print("  Error: Vertex AI is not available.")
         return {"summary": "Error: Vertex AI libraries not found.", "tasks": []}

    # Extract context details for the prompt
    section_key = context_info.get("section_key", "Unknown Section")
    section_title = context_info.get("section_title", "")
    section_start = context_info.get("section_start", "?") # Start page of the specific section
    section_end = context_info.get("section_end", "?")     # End page of the specific section
    chapter_key = context_info.get("chapter_key", "?")
    chapter_title = context_info.get("chapter_title", "Parent Chapter")
    chapter_start = context_info.get("chapter_start", "?") # Start page of the full chapter context
    chapter_end = context_info.get("chapter_end", "?")     # End page of the full chapter context
    
    item_identifier = f"{section_key} - {section_title}" # For logging/errors
    
    if not images:
        # This check might be redundant if main ensures chapter_images exist, but safe to keep
        print(f"  Skipping analysis for {item_identifier}: No chapter images provided.")
        return {"summary": "Error: No chapter context pages found or extracted.", "tasks": []}

    # Updated logging
    print(f"  Analyzing content relevant to {item_identifier} (pages {section_start}-{section_end}) using chapter context (pages {chapter_start}-{chapter_end}) with Vertex AI ({len(images)} images)...")

    # Construct the prompt - Instruct to focus on the specific section within the chapter context
    focus_instruction = f"The following images contain the full content for **chapter '{chapter_title}'** (pages {chapter_start}-{chapter_end}). Your task is to analyze this full chapter context, but generate a summary and task list **focused ONLY on the specific sub-section {section_key} ('{section_title}')**, which is primarily located on pages {section_start} through {section_end} within these images. Ignore content from other sections when creating the output for {section_key}."

    prompt = f"""
{focus_instruction}

Your goal is to:
1.  Provide a **detailed** summary covering **all main sub-topics, materials, and specifications** discussed **specifically for section {section_key}** based on its content found within pages {section_start}-{section_end} of the provided chapter images. Be comprehensive about *this specific section's* content.
2.  Identify and list **all specific tasks, obligations, requirements, or actions explicitly assigned** to the 'contractor' ('aannemer' in Dutch) or a general executing party **that are mentioned within pages {section_start}-{section_end} and pertain ONLY to section {section_key}**. 
    - Be **exhaustive** and **do not omit any** identified tasks found on these specific pages that are relevant *only* to section {section_key}.
    - Search specifically for keywords like 'must', 'shall', 'provide', 'responsible for', 'ensure', 'moet', 'zal', 'voorzien', 'verantwoordelijk voor', 'zorgen voor', and similar imperative or responsibility-assigning language related *only* to this section's scope ({section_key}).
    - Focus on actionable items the contractor needs to perform, deliver, or adhere to based *only* on the content for section {section_key}.
3.  If absolutely no specific tasks for the contractor relating *only* to section {section_key} are mentioned on pages {section_start}-{section_end}, return an empty list for 'tasks'.

Format your response STRICTLY as a JSON object containing two keys:
- "summary": A string containing the detailed, comprehensive summary *only* for section {section_key}.
- "tasks": A list of strings, where each string is a distinct task or obligation found *only* for section {section_key}. Ensure this list is complete based *only* on pages {section_start}-{section_end}.

Example JSON output (ensure summary is detailed and task list is exhaustive for the *specific section requested*):
```json
{{
  "summary": "This section details the requirements for C25/30 concrete pouring for structural elements. It covers mix design submission protocols, aggregate sourcing from approved quarries (X and Y), minimum curing times based on ambient temperature (Table 12.A), formwork specifications including required release agents, and mandatory slump testing procedures (3 tests per 50m³). It also references related standard NBN EN 206.",
  "tasks": [
    "Contractor must submit mix design C25/30 for approval by the site management at least 14 working days prior to the planned pouring date.",
    "Contractor shall source aggregates exclusively from quarries X or Y as listed in appendix B.",
    "Contractor must ensure curing procedures adhere strictly to Table 12.A, maintaining moisture for the specified duration.",
    "Contractor is responsible for cleaning all formwork surfaces and applying the approved release agent (Type Z) before pouring.",
    "Contractor must perform slump tests according to NBN B15-002, executing 3 tests per 50m³ of concrete poured, and record results.",
    "Contractor must provide temperature logs during the curing period for all structural pours."
  ]
}}
```

If no tasks are found specifically for section {section_key}:
```json
{{
  "summary": "This section provides general project contact information and administrative details.",
  "tasks": []
}}
```

Ensure the output is valid JSON and that the 'tasks' list is fully exhaustive based *only* on the provided page content for section {section_key} (pages {section_start}-{section_end}).
Analyze the provided images now.
"""

    # Prepare request parts (prompt + image Parts for Vertex AI - uses the full chapter images)
    request_parts = [prompt]
    for img in images:
         # Convert PIL Image to bytes
         img_byte_arr = io.BytesIO()
         img.save(img_byte_arr, format='PNG') # Or JPEG
         img_bytes = img_byte_arr.getvalue()
         request_parts.append(Part.from_data(data=img_bytes, mime_type="image/png")) # Or image/jpeg

    # Define initial backoff delay and retry limit
    initial_delay = 5 # seconds
    max_retries = 3 # Max attempts for quota errors
    current_retry = 0

    while current_retry <= max_retries:
        try:
            # Use the passed Vertex AI model object
            response = model.generate_content(request_parts, generation_config=GENERATION_CONFIG, stream=False)
            
            # Handle potential safety blocks or empty responses (Vertex AI structure)
            if not response.candidates:
                 print(f"  Warning: Analysis for {item_identifier} resulted in no candidates (potentially blocked). Response: {response}")
                 return {"summary": "Error: Analysis blocked or yielded no content.", "tasks": []}
            
            # Access text differently in Vertex AI response
            if response.candidates[0].content and response.candidates[0].content.parts:
                 response_text = response.candidates[0].content.parts[0].text
            else:
                 response_text = "" # Handle cases where response might be empty but not blocked
                 print(f"  Warning: Empty content parts in response for {item_identifier}.")

            # Extract JSON from the response (reuse existing helper function)
            parsed_json = extract_json_from_response(response_text)

            if parsed_json and isinstance(parsed_json, dict) and "summary" in parsed_json and "tasks" in parsed_json:
                print(f"  Analysis successful for {item_identifier}.")
                # Basic validation
                if not isinstance(parsed_json["summary"], str):
                     print("  Warning: 'summary' field is not a string. Fixing.")
                     parsed_json["summary"] = str(parsed_json["summary"])
                if not isinstance(parsed_json["tasks"], list):
                     print("  Warning: 'tasks' field is not a list. Fixing.")
                     # Attempt to convert or default to empty list
                     if isinstance(parsed_json["tasks"], str):
                          parsed_json["tasks"] = [parsed_json["tasks"]] # Wrap single string in list
                     else:
                          parsed_json["tasks"] = [] # Default to empty
                else:
                     # Ensure all items in tasks list are strings
                     parsed_json["tasks"] = [str(task) for task in parsed_json["tasks"]]
                return parsed_json
            else:
                print(f"  Warning: Failed to extract valid JSON ('summary', 'tasks') for {item_identifier} from response.")
                # Return default error structure if parsing failed after successful call
                return {"summary": "Error: Failed to parse analysis result from model response.", "tasks": []}

        except api_core_exceptions.ResourceExhausted as quota_error:
            # Specific handling for Quota errors with exponential backoff
            current_retry += 1
            if current_retry <= max_retries:
                 # Calculate sleep time: initial_delay * 2^retry_attempt + random_jitter
                 jitter = random.uniform(0, 1) 
                 sleep_time = initial_delay * (2 ** (current_retry -1)) + jitter
                 print(f"\n  Quota Error encountered for {item_identifier} (Attempt {current_retry}/{max_retries}). Retrying in {sleep_time:.2f} seconds... Error: {quota_error}")
                 time.sleep(sleep_time)
            else:
                 print(f"\n  Quota Error: Failed to analyze {item_identifier} after {max_retries} attempts due to quota limits. Error: {quota_error}")
                 return {"summary": f"Error: Quota exceeded after retries - {quota_error}", "tasks": []}
        
        except Exception as e:
            # Generic handling for other potentially transient errors (maybe 1 retry with fixed delay?)
            # For simplicity, let's keep the same retry count but maybe use fixed delay
            current_retry += 1 # Increment retry count even for generic errors
            if current_retry <= max_retries:
                # Fixed delay for generic errors
                fixed_delay = 5 
                print(f"\n  Error during Vertex AI API call for {item_identifier} (Attempt {current_retry}/{max_retries}): {e}. Retrying in {fixed_delay} seconds...")
                time.sleep(fixed_delay)
            else:
                print(f"\n  Failed to analyze {item_identifier} after {max_retries} attempts. Last Error: {e}")
                return {"summary": f"Error: API call failed after retries - {e}", "tasks": []}

    # Fallback if loop finishes unexpectedly (should be handled by returns within the loop)
    print(f"Error: Loop finished unexpectedly for {item_identifier}.")
    return {"summary": "Error: Analysis failed after retries (unexpected loop exit).", "tasks": []}


def get_min_max_pages(data):
    """Recursively finds the minimum start and maximum end page in a TOC structure."""
    min_page = float('inf')
    max_page = 0
    found_pages = False

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                is_entry = all(k in value for k in ('start', 'end', 'title'))
                if is_entry:
                    try:
                        start = int(value.get('start', 0))
                        end = int(value.get('end', 0))
                        if start > 0 and end >= start:
                            min_page = min(min_page, start)
                            max_page = max(max_page, end)
                            found_pages = True
                    except (ValueError, TypeError):
                        pass # Ignore non-integer or invalid pages

                # Recurse into sub-sections or nested dictionaries
                sub_min, sub_max, sub_found = get_min_max_pages(value) # Check sub-dictionaries
                if sub_found:
                     min_page = min(min_page, sub_min)
                     max_page = max(max_page, sub_max)
                     found_pages = True
            # Could add elif isinstance(value, list) here if lists are possible
    
    elif isinstance(data, list):
         for item in data:
              sub_min, sub_max, sub_found = get_min_max_pages(item)
              if sub_found:
                   min_page = min(min_page, sub_min)
                   max_page = max(max_page, sub_max)
                   found_pages = True

    if not found_pages:
         return None, None, False # Indicate no valid pages found
    return min_page, max_page, True

def collect_all_section_ranges(toc_data):
    """Recursively collects page ranges for ALL sections/entries that have them."""
    sections_with_ranges = []
    
    def find_sections(data):
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict):
                    is_entry = all(k in value for k in ('start', 'end', 'title'))
                    if is_entry:
                        try:
                             start = int(value.get('start', 0))
                             end = int(value.get('end', 0))
                             if start > 0 and end >= start:
                                 # This entry has a valid range, add it
                                 sections_with_ranges.append({
                                     "key": key,
                                     "title": value.get('title', f'Entry {key}'),
                                     "start": start,
                                     "end": end,
                                     "chapter_key": key.split('.')[0] # Store parent chapter key
                                 })
                        except (ValueError, TypeError): 
                             pass # Ignore entries with invalid page numbers

                    # Always recurse deeper into dictionaries
                    find_sections(value)
                    
                elif isinstance(value, list):
                    find_sections(value) # Recurse into lists
                    
        elif isinstance(data, list):
             for item in data:
                  find_sections(item)

    # Start the search from the root
    find_sections(toc_data)
    
    print(f"Collected {len(sections_with_ranges)} sections/entries with valid page ranges.")
    # Sort ranges by key for potentially more logical processing order
    try:
         sections_with_ranges.sort(key=lambda x: tuple(map(int, x['key'].split('.'))))
    except ValueError:
         sections_with_ranges.sort(key=lambda x: x['key']) # Fallback lexical sort
         
    return sections_with_ranges

def process_toc_recursively(data, pdf_doc, model, root_toc_data=None):
    """Recursively traverses the TOC, analyzing each entry with page numbers,
       providing the full parent chapter's pages as context for each call.
    """
    if root_toc_data is None: # Initialize root_toc_data on the first call
         root_toc_data = data
         
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                # Check if it's an entry to analyze (has start, end, title)
                is_entry = all(k in value for k in ('start', 'end', 'title'))
                
                if is_entry:
                    section_title = value.get('title', f'Entry {key}')
                    identifier = f"{key} - {section_title}" 
                    print(f"Processing entry: {identifier}...")
                    try:
                        section_start_page = int(value.get('start', 0))
                        section_end_page = int(value.get('end', 0))

                        if section_start_page > 0 and section_end_page >= section_start_page:
                            # --- Context Logic --- 
                            chapter_key = key.split('.')[0]
                            chapter_data = root_toc_data.get(chapter_key)
                            chapter_title = "Unknown Chapter"
                            chapter_start_page = None
                            chapter_end_page = None
                            chapter_images = []

                            if chapter_data and isinstance(chapter_data, dict):
                                chapter_title = chapter_data.get('title', f'Chapter {chapter_key}')
                                chap_min, chap_max, found = get_min_max_pages(chapter_data)
                                if found:
                                     chapter_start_page = chap_min
                                     chapter_end_page = chap_max
                                     print(f"  Extracting full context for Chapter '{chapter_title}' (pages {chapter_start_page}-{chapter_end_page}) for analyzing {key}...")
                                     chapter_images = extract_pages_as_images(pdf_doc, chapter_start_page, chapter_end_page)
                                else:
                                     print(f"  Warning: Could not determine page range for parent chapter {chapter_key}.")
                            else:
                                 print(f"  Warning: Could not find data for parent chapter {chapter_key}.")
                            # --- End Context Logic ---
                            
                            if chapter_images: # Proceed only if we have chapter context images
                                 # Prepare context info for the prompt
                                 context_info_for_prompt = { 
                                      "section_key": key,
                                      "section_title": section_title,
                                      "section_start": section_start_page,
                                      "section_end": section_end_page,
                                      "chapter_key": chapter_key,
                                      "chapter_title": chapter_title,
                                      "chapter_start": chapter_start_page,
                                      "chapter_end": chapter_end_page
                                 }
                                 # Pass the FULL CHAPTER images and the specific context info
                                 analysis_result = analyze_content_with_gemini(model, chapter_images, context_info_for_prompt)
                                 value['summary'] = analysis_result.get('summary', 'Error: Summary not generated.')
                                 value['tasks'] = analysis_result.get('tasks', [])
                            else:
                                 print(f"  Skipping analysis for {identifier}: Failed to get chapter context images.")
                                 value['summary'] = 'Error: Could not extract chapter context pages for analysis.'
                                 value['tasks'] = []
                            time.sleep(1) # Keep delay between API calls
                        else:
                             print(f"  Skipping analysis for {identifier}: Invalid or missing page numbers ({section_start_page}-{section_end_page}).")
                             value['summary'] = 'Error: Invalid page range.'
                             value['tasks'] = []
                    except ValueError:
                        print(f"  Skipping analysis for {identifier}: Invalid page numbers (not integers).")
                        value['summary'] = 'Error: Non-integer page numbers.'
                        value['tasks'] = []
                    except Exception as e:
                        print(f"  Unexpected error processing entry {key}: {e}")
                        value['summary'] = f'Error: {e}'
                        value['tasks'] = []

                # Always recurse into sub-dictionaries, passing root_toc_data down
                process_toc_recursively(value, pdf_doc, model, root_toc_data)
            
            elif isinstance(value, list):
                 # Also recurse into lists if they contain dicts/other lists
                 process_toc_recursively(value, pdf_doc, model, root_toc_data)

    elif isinstance(data, list):
        for item in data:
            process_toc_recursively(item, pdf_doc, model, root_toc_data)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description='Add summaries and tasks to a TOC JSON file using Vertex AI.')
    parser.add_argument('--json_input', type=str, 
                        default=r"C:\Users\gr\Documents\GitHub\Meetstaatincorp\step1_toc\chapters.json", 
                        help='Path to the input TOC JSON file.')
    parser.add_argument('--pdf_input', type=str, 
                        default=r"C:\Users\gr\Documents\GitHub\Meetstaatincorp\samengevoegdamsterdamlastenboek.pdf", 
                        help='Path to the corresponding PDF file.')
    parser.add_argument('--output', type=str, default='output/toc_with_summaries_tasks.json', 
                        help='Path to save the output JSON file.')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_NAME, 
                        help=f'Name of the Gemini model to use (default: {DEFAULT_MODEL_NAME}).')
    # Add argument for API key if needed, or rely solely on environment variable
    # parser.add_argument('--api_key', type=str, default=None, help='Gemini API Key (overrides environment variable).')

    args = parser.parse_args()

    # --- Determine API Key (Example using arg precedence) ---
    # final_api_key = args.api_key or os.environ.get("GEMINI_API_KEY") or DEFAULT_API_KEY
    # if not final_api_key or ("AIzaSy" in final_api_key and final_api_key == DEFAULT_API_KEY):
    #     print("Error: Gemini API key not configured. Set GEMINI_API_KEY environment variable, use --api_key, or edit DEFAULT_API_KEY.")
    #     sys.exit(1)
    # try:
    #     genai.configure(api_key=final_api_key)
    #     print("Gemini API configured.")
    # except Exception as e:
    #     print(f"Error configuring Gemini API: {e}")
    #     sys.exit(1)
    # --- End API Key Handling ---

    # --- Model Initialization (Change to Vertex AI) ---
    print(f"Using model: {args.model}")
    if not VERTEX_AI_AVAILABLE:
         print("Vertex AI libraries not installed. Cannot proceed.")
         sys.exit(1)
         
    try:
        # Initialize Vertex AI SDK
        print(f"Initializing Vertex AI for Project: {PROJECT_ID}, Location: {LOCATION}")
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
        
        # Create the Vertex AI GenerativeModel instance
        model = GenerativeModel(args.model)
        print(f"Vertex AI GenerativeModel '{args.model}' initialized.")
    except Exception as e:
        print(f"Error initializing Vertex AI or model '{args.model}': {e}")
        sys.exit(1)
    # --- End Model Initialization ---

    # Load input JSON
    print(f"Loading TOC JSON from: {args.json_input}")
    try:
        with open(args.json_input, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        sys.exit(1)

    # Open PDF
    print(f"Opening PDF document: {args.pdf_input}")
    try:
        pdf_doc = fitz.open(args.pdf_input)
        print(f"PDF loaded successfully ({len(pdf_doc)} pages).")
    except Exception as e:
        print(f"Error opening PDF file: {e}")
        sys.exit(1)

    # Process the data
    print("Starting analysis process...")
    # Remove old chunking loop
    # section_results = {} 
    # target_sections = collect_target_section_ranges(toc_data, level=2)
    # for section_range in target_sections: ...
    
    # Call the recursive function to process the entire TOC in-place,
    # passing the loaded toc_data as the root_toc_data for context lookup
    process_toc_recursively(toc_data, pdf_doc, model, root_toc_data=toc_data)

    # Close PDF
    pdf_doc.close()

    # Save the updated JSON
    print(f"\nAnalysis complete. Saving updated TOC JSON to: {args.output}")
    try:
        output_dir = os.path.dirname(args.output)
        if output_dir: # Ensure output directory exists if specified
             os.makedirs(output_dir, exist_ok=True)
             
        # Remove the assignment call - results are added in-place by recursion
        # assign_results_hierarchically(toc_data, section_results, target_level=2) 
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(toc_data, f, indent=4, ensure_ascii=False)
        print("Output JSON saved successfully.")
    except Exception as e:
        print(f"Error saving output JSON file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 