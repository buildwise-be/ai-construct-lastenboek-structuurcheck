# === Future Development Plan (Vision-Based Approach) ===
# Goal: Compare Meetstaat (Excel) items with Lastenboek (PDF) specifications,
#       handling cases where the PDF might be image-based (scans).
#
# 1.  Parse Meetstaat: Use pandas to extract structured data (item_code -> details) from Excel.
# 2.  Get Lastenboek Page Ranges: Use a Table of Contents (JSON or generated)
#     to find the start/end page numbers corresponding to each item_code.
# 3.  Combine Initial Data: Create a structure linking item_code to Meetstaat details
#     and the corresponding Lastenboek page range (NOT extracted text).
# 4.  Multimodal LLM Comparison (per item):
#     a. For items present in both sources, get the relevant page range from step 3.
#     b. Use PyMuPDF (fitz) to render these specific PDF pages into image data (e.g., PNG).
#     c. Construct a prompt for a multimodal LLM (e.g., Gemini 1.5 Pro/Flash via Vertex AI)
#        including:
#        - Textual Context: item_code, Meetstaat description/details, comparison task.
#        - Image Data: The rendered image(s) of the Lastenboek pages.
#     d. Call the LLM via Vertex AI, sending both text and image(s).
#     e. Store the LLM's text response (comparison result/discrepancies) back into
#        the combined data structure for that item.
# 5.  Return Results: Send the final combined data (including LLM comparison results)
#     back to the frontend as JSON.
#
# Key Changes Required:
# - Refactor llm_toc_analyzer.py: TOC logic remains useful for page numbers, but text
#   extraction and text-based LLM calls will be replaced/supplemented by multimodal calls.
#   Need a function for multimodal comparison (text+image -> text).
# - Update app.py (/analyze): Implement PDF page-to-image rendering (PyMuPDF).
#   Call the multimodal LLM function for comparison. Manage temporary files.
# - requirements.txt: Add PyMuPDF.
# - templates/ui.html: Update JS to display comparison results effectively.
# === End Future Development Plan ===

from flask import Flask, render_template, request, jsonify, session, make_response
from flask_session import Session # <-- Import Flask-Session
import os
import pandas as pd
import tempfile # For handling temporary files
import logging
from werkzeug.utils import secure_filename # For safe filenames
import json # <-- Import json
import re # Import regex for number parsing
import time # For potential backoff in LLM calls
import glob # For globbing files

# Import the refactored function
from llm_toc_analyzer import get_toc_page_ranges_from_json

# --- Add Vertex AI imports --- 
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel, Part
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logging.warning("Vertex AI libraries not found. Discrepancy analysis will be unavailable.")
# ---------------------------

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Abbreviation Mappings ---
ABBREVIATION_MAP = {
    "VH": "Vermoedelijke Hoeveelheid", # Dutch only
    "FH": "Forfaitaire Hoeveelheid",   # Dutch only
    "GP": "Globale Prijs",             # Dutch only
    "OA afbraak": "Categorie: Afbraak"     # Simplified Dutch description for category
    # Add other mappings as needed, HVAC is intentionally excluded
}
# -----------------------------

def normalize_code(code):
    """Removes trailing dots and potential letter suffixes (like .A.) from item codes."""
    if not isinstance(code, str):
        return code # Return as is if not a string
    
    # Remove trailing dots repeatedly
    while code.endswith('.'):
        code = code[:-1]
    
    # Remove trailing letter suffix (e.g., .A, .B)
    if len(code) > 2 and code[-2] == '.' and code[-1].isalpha():
        code = code[:-2]
        
    return code

# Allowed file extensions (for security)
ALLOWED_EXTENSIONS_CSV = {'csv'}
ALLOWED_EXTENSIONS_PDF = {'pdf'}

def allowed_file(filename, allowed_extensions):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Initialize the Flask application
app = Flask(__name__, instance_relative_config=True)

# --- Configure Flask-Session --- 
# Use filesystem session type (requires Flask-Session library)
# Stores session data in a 'flask_session' directory in the instance folder
app.config["SESSION_PERMANENT"] = False # Use session cookies (expire when browser closes)
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, 'flask_session') # Explicitly set path
app.config["SECRET_KEY"] = os.urandom(24) # Secret key is still needed!

# Ensure the instance folder exists
try:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
except OSError:
    pass # Should already exist or be creatable

Session(app) # Initialize the session extension
# --------------------------------

# Create an 'uploads' directory if it doesn't exist
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# SECRET_KEY is now set above during Session config
# app.config['SECRET_KEY'] = os.urandom(24) # Remove or comment out duplicate

# --- Define path to the TOC JSON file --- 
TOC_JSON_PATH = os.path.join(os.path.dirname(__file__), 'step1_toc', 'chapters.json')

# --- Define function to get the most recent vision TOC file ---
def get_latest_vision_toc_path():
    """Returns the path to the most recent vision TOC file in the output directory."""
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    vision_toc_files = glob.glob(os.path.join(output_dir, 'vision_toc_*.json'))
    
    if not vision_toc_files:
        logger.warning("No vision TOC files found in output directory")
        return None
    
    # Sort by modification time (most recent first)
    vision_toc_files.sort(key=os.path.getmtime, reverse=True)
    latest_file = vision_toc_files[0]
    logger.info(f"Selected most recent vision TOC file: {latest_file}")
    return latest_file

# --- Define function to get TOC path based on selected type ---
def get_toc_path_by_type(toc_type):
    """Returns the path to the appropriate TOC file based on the selected type."""
    if toc_type == "vision":
        # Hardcode the path to the existing vision TOC file instead of searching
        vision_toc_path = os.path.join(os.path.dirname(__file__), 'output', 
                                      'uitgebreide toc met taken.json')
        if os.path.exists(vision_toc_path):
            logger.info(f"Using hardcoded vision TOC file: {vision_toc_path}")
            return vision_toc_path
        else:
            logger.warning(f"Hardcoded vision TOC file not found at {vision_toc_path}, falling back to standard TOC")
            return TOC_JSON_PATH
    else:  # Default to standard
        return TOC_JSON_PATH

def parse_meetstaat_csv(csv_path):
    """Parses the Meetstaat CSV file into a dictionary, trying common delimiters."""
    common_configs = [
        {'sep': ';', 'encoding': 'latin1', 'engine': 'python', 'header': None, 'skiprows': 1}, # Try semicolon first
        {'sep': ',', 'encoding': 'latin1', 'engine': 'python', 'header': None, 'skiprows': 1}  # Fallback to comma
    ]
    df = None
    last_error = None

    for config in common_configs:
        try:
            logger.info(f"Attempting to parse CSV with config: {config}")
            df = pd.read_csv(csv_path, dtype={1: str}, **config) # Read column 1 (Item Code) as string
            logger.info(f"Successfully parsed CSV with config: {config}")
            # Add column names manually since header=None
            # Adjust these names based on the actual content/order
            df.columns = ['Col0', 'Item Code', 'Description', 'Col3', 'Unit', 'Type', 'Quantity', 'Col7', 'Notes', 'Col9'] # Example names, adjust count/names!
            logger.info(f"Assigned column names: {list(df.columns)}")
            break # Success, exit the loop
        except FileNotFoundError:
            logger.error(f"Meetstaat CSV file not found at {csv_path}")
            return None # File not found is critical
        except Exception as e:
            logger.warning(f"Failed to parse CSV with config {config}: {e}")
            last_error = e # Store the error and try the next config

    # If df is still None after trying all configs, raise the last error encountered
    if df is None:
        logger.error(f"Failed to parse CSV with all tried configurations. Last error: {last_error}")
        if last_error:
            raise last_error # Re-raise the last specific pandas/python error
        else:
            raise ValueError("Could not read CSV file.")

    # --- Post-parsing processing ---
    # Check if 'Item Code' column (now assigned manually) exists
    if 'Item Code' not in df.columns:
        # This check should ideally not fail now, but kept as safeguard
        raise ValueError("Failed to assign 'Item Code' column after parsing.")

    # Convert NaNs to None for JSON compatibility if needed
    df = df.where(pd.notnull(df), None)

    # Create dictionary: item_code -> {column_name: value, ...}
    # Use the manually assigned 'Item Code' column name
    meetstaat_items = {
        normalize_code(str(row['Item Code'])): row.to_dict()
        for index, row in df.iterrows() 
        if row['Item Code'] is not None and str(row['Item Code']).strip() != '' # Also check for empty strings
    }
    logger.info(f"Parsed {len(meetstaat_items)} items from Meetstaat CSV after normalization.")
    return meetstaat_items

# --- Helper function for number parsing ---
def parse_dutch_number(num_str):
    """Converts Dutch formatted number string (e.g., '123,456') to float."""
    if num_str is None or not isinstance(num_str, str):
        return None
    try:
        # Remove thousands separators (dots) if any - not seen in examples but good practice
        num_str_cleaned = num_str.replace('.', '')
        # Replace comma decimal separator with dot
        num_str_cleaned = num_str_cleaned.replace(',', '.')
        # Handle potential non-numeric chars remaining (like EUR, -, etc.)
        # Keep only digits, decimal point, and potential leading minus sign
        num_str_cleaned = re.sub(r"[^0-9.-]", "", num_str_cleaned)
        if not num_str_cleaned or num_str_cleaned == '.': # Avoid empty strings or just '.'
             return None
        return float(num_str_cleaned)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse '{num_str}' as a number.")
        return None # Return None if parsing fails
# ------------------------------------------

# --- LLM Analysis Functions --- 

# (Keep analyze_item_with_gemini as a fallback or for single-item tests if needed,
#  but the main logic will now use analyze_batch_with_gemini)

def analyze_item_with_gemini(
    model: GenerativeModel,
    item: dict
) -> str:
    """
    Sends item details to Gemini for discrepancy analysis.
    (Assumes model is already initialized)

    Args:
        model: Initialized Vertex AI GenerativeModel.
        item: A dictionary representing one item (flattened structure).

    Returns:
        The analysis result string from Gemini, or an error message.
    """
    # --- Construct the prompt --- 
    # (Using the same prompt as before)
    prompt_parts = [
        "You are an expert construction contract analyst. Your task is to compare the following Meetstaat (Bill of Quantities) details with the corresponding Lastenboek (Specifications) section title and page range.",
        "Identify potential discrepancies, inconsistencies, or ambiguities between them. Focus on mismatches in scope, materials, quantities, units, or descriptions, based *only* on the information provided below.",
        "For example, does the Lastenboek title suggest one type of work while the Meetstaat details imply something significantly different?",
        "\n--- MEETSTAAT DETAILS ---",
        f"Item Code: {item.get('item_code', 'N/A')}",
        f"Description: {item.get('meetstaat_description', 'N/A')}",
        f"Quantity: {item.get('meetstaat_quantity', 'N/A')}",
        f"Unit: {item.get('meetstaat_unit', 'N/A')}",
        f"Type: {item.get('meetstaat_type', 'N/A')}",
        f"Notes: {item.get('meetstaat_notes', 'N/A')}",
        "\n--- LASTENBOEK TOC DETAILS ---",
        f"TOC Title: {item.get('lastenboek_title', 'N/A')}",
        f"Page Range: {item.get('lastenboek_start_page', '?')} - {item.get('lastenboek_end_page', '?')}",
        # IMPORTANT LIMITATION: We don't have the actual text from these pages here.
        # The analysis is based solely on the TOC title vs. Meetstaat details.
        "\n--- ANALYSIS TASK ---",
        "Provide a concise summary of any significant discrepancies found between the Meetstaat details and the Lastenboek TOC title. If no significant issues are apparent based *only* on this limited information, state 'No significant discrepancies found based on provided details.' Do not repeat the input information in your response."
    ]
    prompt = "\n".join(prompt_parts)

    # --- Call the LLM --- 
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"Sending prompt to Gemini for item {item.get('item_code')}")
            # Note: Using generate_content which might block. Consider async if needed for many items.
            response = model.generate_content(prompt)
            logger.debug(f"Received response from Gemini for item {item.get('item_code')}")
            # Accessing the text safely
            if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                 analysis_text = response.candidates[0].content.parts[0].text
                 return analysis_text.strip()
            else:
                 logger.warning(f"Gemini response structure unexpected or empty for item {item.get('item_code')}. Response: {response}")
                 return "Error: Unexpected or empty response from Gemini."

        except Exception as e:
            logger.error(f"Error calling Gemini API for item {item.get('item_code')} (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) # Exponential backoff
            else:
                return f"Error: Failed to get analysis after {max_retries} attempts. Last error: {e}"
    return "Error: Analysis failed after retries." # Should not be reached

def analyze_batch_with_gemini(batch: list[dict]) -> dict[str, dict]:
    """
    Sends a batch of items to Gemini for discrepancy analysis using a single API call.

    Args:
        batch: A list of item dictionaries with Meetstaat and Lastenboek information.

    Returns:
        A dictionary mapping item_code to its analysis result (structured JSON object).
    """
    if not batch:
        return {}

    # Get Vertex AI config from environment variables
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001")  # Using the configured model

    if not project_id:
        logger.error("GOOGLE_CLOUD_PROJECT environment variable not set.")
        return {item.get("item_code", "unknown"): {"error": "Server configuration error: Project ID missing."} for item in batch}

    # Initialize Vertex AI
    try:
        aiplatform.init(project=project_id, location=location)
        model = GenerativeModel(model_name)
        logger.info(f"Vertex AI initialized for project '{project_id}' in '{location}' using model {model_name}.")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {e}")
        return {item.get("item_code", "unknown"): {"error": f"Server configuration error: Could not initialize Vertex AI. {e}"} for item in batch}

    # --- Construct the batch prompt --- 
    prompt_parts = [
        "You are an expert construction contract analyst comparing Meetstaat (Bill of Quantities) details with Lastenboek (Specifications) sections.",
        "For EACH item, perform the following specific checks and provide structured findings:",
        
        "\n--- CHECK 1: CONSISTENCY CHECK ---",
        "Evaluate if quantities and materials in the Meetstaat logically align with the tasks described in the Lastenboek.",
        "Examples of inconsistencies: wrong material type, inappropriate quantities for the described task, mismatched units.",
        "If the Lastenboek describes concrete walls but the Meetstaat shows brick quantities, this is inconsistent.",
        
        "\n--- CHECK 2: LOCATION CHECK ---",
        "Identify if multiple tasks appear to be described in the Lastenboek section but some are missing from this Meetstaat item.",
        "Example: Lastenboek section mentions both 'painting' and 'plastering', but only plastering appears in this Meetstaat item (painting might be missing or in another item).",
        
        "\nFormat your analysis for EACH item as a JSON object in this exact structure:",
        "{",
        "  \"item_code\": \"the item code\",",
        "  \"checks\": {",
        "    \"consistency\": {",
        "      \"issue_found\": true/false,",
        "      \"description\": \"Detailed description of consistency issue or 'No issues found.'\",",
        "      \"significant\": true/false",
        "    },",
        "    \"location\": {",
        "      \"issue_found\": true/false,",
        "      \"description\": \"Detailed description of location/task mismatch issue or 'No issues found.'\",",
        "      \"significant\": true/false",
        "    }",
        "  },",
        "  \"summary\": \"Brief summary of all issues, or 'No significant discrepancies identified.'\",",
        "  \"has_significant_issue\": true/false",
        "}",
        
        "\nGuidelines:",
        "1. Set 'significant' to true ONLY for major discrepancies that likely require attention.",
        "2. Set 'has_significant_issue' to true if ANY check has 'significant' set to true.",
        "3. For each check, if 'issue_found' is false, set 'description' to 'No issues found.' and 'significant' to false.",
        "4. If you cannot definitively assess a check due to limited information, set 'issue_found' to false and mention the limitation in 'description'.",
        "5. For 'summary', briefly list ALL issues found across all checks. If no issues were found, set it to 'No significant discrepancies identified.'",
        
        "\n--- ITEMS FOR ANALYSIS ---"
    ]

    for item in batch:
        prompt_parts.append("\n---") # Separator
        prompt_parts.append(f"Item Code: {item.get('item_code', 'N/A')}")
        prompt_parts.append(f"  Meetstaat Info:")
        
        # Extract and include meetstaat_info
        meetstaat_info = item.get('meetstaat_info', {})
        for key, value in meetstaat_info.items():
            prompt_parts.append(f"    {key}: {value}")
        
        prompt_parts.append(f"  Lastenboek Page Range: {item.get('lastenboek_page_range', 'N/A')}")
        prompt_parts.append(f"  Lastenboek Text: {item.get('lastenboek_text', 'N/A')[:500]}...") # Truncate if too long

    prompt_parts.append("\n--- END ITEMS --- ")
    prompt_parts.append("\nReturn your analysis as a JSON array of objects with the exact structure specified above, one object per item.")
    prompt = "\n".join(prompt_parts)

    # Initialize results dict with error placeholders
    batch_results = {item.get("item_code"): {"error": "Analysis not received for this item in batch."} for item in batch}

    # --- Call the LLM --- 
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"Sending batch prompt to Gemini ({len(batch)} items). First item: {batch[0].get('item_code')}")
            response = model.generate_content(prompt)
            logger.debug(f"Received batch response from Gemini. First item: {batch[0].get('item_code')}")

            if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
                # Attempt to parse the response as JSON
                try:
                    # Clean potential markdown code fences
                    if response_text.strip().startswith("```json"):
                        response_text = response_text.strip()[7:-3].strip()
                    elif response_text.strip().startswith("```"):
                         response_text = response_text.strip()[3:-3].strip()
                        
                    parsed_results = json.loads(response_text)
                    if isinstance(parsed_results, list):
                        # Update batch_results with successful analyses
                        found_codes = set()
                        for result_item in parsed_results:
                            if isinstance(result_item, dict) and 'item_code' in result_item:
                                code = result_item['item_code']
                                if code in batch_results: # Check if it belongs to this batch
                                     # Store the entire structured response with checks
                                     batch_results[code] = result_item
                                     found_codes.add(code)
                        
                        # Mark items requested but not found in the response as errors
                        for item in batch:
                            code = item.get("item_code")
                            if code not in found_codes:
                                batch_results[code] = {"error": "Item analysis missing in Gemini batch response."}
                                logger.warning(f"Analysis missing for item {code} in batch response.")
                                
                        return batch_results # Success
                    else:
                        logger.error(f"Gemini response was not a JSON list for batch starting with {batch[0].get('item_code')}. Content: {response_text[:500]}...")
                        error_msg = {"error": "Gemini response was not a JSON list."}
                except json.JSONDecodeError as json_e:
                    logger.error(f"Failed to decode Gemini JSON response for batch starting with {batch[0].get('item_code')}: {json_e}. Response: {response_text[:500]}...")
                    error_msg = {"error": f"Failed to decode Gemini JSON response. {json_e}"}
            else:
                logger.warning(f"Gemini batch response structure unexpected or empty. Response: {response}")
                error_msg = {"error": "Unexpected or empty response from Gemini."}

            # If parsing failed or structure was wrong, fill results with the error
            for item_code in batch_results:
                 batch_results[item_code] = error_msg # Propagate parsing error to all items in batch
            return batch_results # Return errors

        except Exception as e:
            logger.error(f"Error calling Gemini API for batch (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt) # Exponential backoff
            else:
                error_msg = {"error": f"Failed to get analysis after {max_retries} attempts. Last error: {e}"}
                # Fill results with the final error
                for item_code in batch_results:
                    batch_results[item_code] = error_msg
                return batch_results # Return final errors

    # Fallback - should not be reached if loop completes, but for safety
    for item_code in batch_results:
        batch_results[item_code] = {"error": "Unexpected error in batch analysis."}
    return batch_results
# -----------------------------------------------------

# Route for the main page - serves the HTML UI
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('ui.html')

# Route to handle the analysis request (POST)
@app.route('/analyze', methods=['POST'])
def analyze():
    """Handles the document analysis request."""
    if 'lastenboek' not in request.files:
        return jsonify({'error': 'No Lastenboek (PDF) file part in the request.'}), 400

    lastenboek_file = request.files['lastenboek']
    meetstaat_file = request.files.get('meetstaat') # Meetstaat is optional for now
    
    # Get the selected TOC type (default to standard if not provided)
    toc_type = request.form.get('toc_type', 'standard')
    logger.info(f"Selected TOC type: {toc_type}")

    # --- File Validation ---
    if lastenboek_file.filename == '':
        return jsonify({'error': 'No selected file for Lastenboek (PDF).'}), 400
    if not allowed_file(lastenboek_file.filename, ALLOWED_EXTENSIONS_PDF):
         return jsonify({'error': 'Invalid file type for Lastenboek. Only PDF allowed.'}), 400

    if meetstaat_file and meetstaat_file.filename == '':
         # If meetstaat part exists but no file selected, treat as not uploaded
         meetstaat_file = None
    if meetstaat_file and not allowed_file(meetstaat_file.filename, ALLOWED_EXTENSIONS_CSV):
         return jsonify({'error': 'Invalid file type for Meetstaat. Only CSV allowed.'}), 400

    # --- Save Files Temporarily ---
    # Using tempfile is generally safer for web apps than saving to a fixed 'uploads'
    # but for simplicity here, we save to uploads and will clean up later (ideally)
    lastenboek_filename = secure_filename(lastenboek_file.filename)
    lastenboek_path = os.path.join(app.config['UPLOAD_FOLDER'], lastenboek_filename)
    lastenboek_file.save(lastenboek_path)
    logger.info(f"Saved Lastenboek PDF to: {lastenboek_path}")

    meetstaat_path = None
    meetstaat_filename = None
    if meetstaat_file:
        meetstaat_filename = secure_filename(meetstaat_file.filename)
        meetstaat_path = os.path.join(app.config['UPLOAD_FOLDER'], meetstaat_filename)
        meetstaat_file.save(meetstaat_path)
        logger.info(f"Saved Meetstaat CSV to: {meetstaat_path}")

    # --- Process Files ---
    meetstaat_items = {}
    toc_page_ranges = {}
    error_messages = []
    toc_data = None # Initialize toc_data

    try:
        # --- Load TOC JSON from File based on selected type --- 
        selected_toc_path = get_toc_path_by_type(toc_type)
        logger.info(f"Loading TOC data from: {selected_toc_path}")
        try:
            with open(selected_toc_path, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
            logger.info(f"Successfully loaded TOC JSON data from {selected_toc_path}.")
        except FileNotFoundError:
            logger.error(f"TOC JSON file not found at: {selected_toc_path}")
            error_messages.append(f"Critical error: TOC JSON file not found at {selected_toc_path}")
            # Stop processing if TOC is missing
            return jsonify({'error': f'Server configuration error: TOC file not found.'}), 500
        except json.JSONDecodeError as json_err:
            logger.error(f"Error decoding TOC JSON file: {json_err}")
            error_messages.append(f"Critical error: Invalid format in TOC JSON file.")
            # Stop processing if TOC is invalid
            return jsonify({'error': f'Server configuration error: Invalid TOC file format.'}), 500
        # --- End Load TOC JSON ---

        # Parse Meetstaat CSV (if provided)
        if meetstaat_path:
            meetstaat_items = parse_meetstaat_csv(meetstaat_path)
            if meetstaat_items is None:
                 error_messages.append("Failed to parse Meetstaat CSV.")
                 # Decide if this is critical - for now, continue without it

        # Get Lastenboek TOC page ranges (using data loaded from file)
        if toc_data: # Proceed only if TOC data was loaded successfully
            toc_page_ranges = get_toc_page_ranges_from_json(toc_data)
            if not toc_page_ranges:
                 # This now indicates an issue with the content/structure of the JSON
                 error_messages.append("Failed to extract page ranges from the loaded TOC data. Check JSON structure.")
                 # Decide if this is critical
        else:
            error_messages.append("Skipping Lastenboek page range extraction due to earlier TOC loading error.")

        # --- Combine Data (Flattened Structure) ---
        combined_data = []
        normalized_meetstaat_codes = {normalize_code(k) for k in meetstaat_items.keys()}
        normalized_toc_codes = {normalize_code(k) for k in toc_page_ranges.keys()}
        all_item_codes = normalized_meetstaat_codes | normalized_toc_codes

        for code in sorted(list(all_item_codes)):
            meetstaat_info = meetstaat_items.get(code)
            lastenboek_range_info = toc_page_ranges.get(code)

            # Determine source and apply abbreviation mappings/parsing
            flat_item = {"item_code": code}
            is_meetstaat_present = meetstaat_info is not None
            is_lastenboek_present = lastenboek_range_info is not None

            if is_meetstaat_present and is_lastenboek_present:
                flat_item["source"] = "both"
            elif is_meetstaat_present:
                flat_item["source"] = "meetstaat_only"
            else: # Only in lastenboek
                flat_item["source"] = "lastenboek_only"

            # Add Meetstaat details (if present)
            if meetstaat_info:
                flat_item["meetstaat_description"] = meetstaat_info.get("Description")
                flat_item["meetstaat_quantity"] = parse_dutch_number(meetstaat_info.get("Quantity"))
                flat_item["meetstaat_unit"] = meetstaat_info.get("Unit")
                # Apply mapping to Type and Notes
                raw_type = meetstaat_info.get("Type")
                flat_item["meetstaat_type"] = f"{ABBREVIATION_MAP.get(raw_type, raw_type)} ({raw_type})" if raw_type and raw_type in ABBREVIATION_MAP else raw_type
                raw_notes = meetstaat_info.get("Notes")
                flat_item["meetstaat_notes"] = f"{ABBREVIATION_MAP.get(raw_notes, raw_notes)} ({raw_notes})" if raw_notes and raw_notes in ABBREVIATION_MAP else raw_notes
            else:
                flat_item["meetstaat_description"] = None
                flat_item["meetstaat_quantity"] = None
                flat_item["meetstaat_unit"] = None
                flat_item["meetstaat_type"] = None
                flat_item["meetstaat_notes"] = None

            # Add Lastenboek details (if present)
            if lastenboek_range_info:
                flat_item["lastenboek_title"] = lastenboek_range_info.get("title")
                flat_item["lastenboek_start_page"] = lastenboek_range_info.get("start")
                flat_item["lastenboek_end_page"] = lastenboek_range_info.get("end")
            else:
                flat_item["lastenboek_title"] = None
                flat_item["lastenboek_start_page"] = None
                flat_item["lastenboek_end_page"] = None

            flat_item["llm_analysis"] = None # Placeholder

            combined_data.append(flat_item)
        # --- End Combine Data ---

        # --- Generate Summary (Overall Counts) --- 
        analysis_summary = {
            'count_both': 0,
            'count_meetstaat_only': 0,
            'count_lastenboek_only': 0
        }
        if combined_data:
             for item in combined_data:
                 source = item.get("source")
                 if source == "both":
                     analysis_summary['count_both'] += 1
                 elif source == "meetstaat_only":
                     analysis_summary['count_meetstaat_only'] += 1
                 elif source == "lastenboek_only":
                     analysis_summary['count_lastenboek_only'] += 1
        # --- End Generate Summary --- 

        # --- Added Logging --- 
        logger.info(f"Attempting to save {len(combined_data)} items to session['analysis_results'].")
        if combined_data:
            logger.debug(f"First item sample for session: {combined_data[0]}")
        # --- End Added Logging ---
        
        # --- Store results in session for export AND discrepancy analysis --- 
        # Removed limit: Store the full data again
        # session_limit = 10 
        session['analysis_results'] = combined_data # Store the full combined data
        session['toc_type'] = toc_type  # Store the TOC type used
        session['toc_path'] = os.path.basename(selected_toc_path)  # Store the TOC path used
        # -----------------------------------------------------------------

        # --- Added Logging ---
        if 'analysis_results' in session:
            logger.info(f"Successfully set session['analysis_results'] with {len(session['analysis_results'])} items.")
        else:
            logger.error("Failed to set session['analysis_results']!")
        # --- End Added Logging ---

        logger.info(f"Analysis complete. Returning {len(combined_data)} items for UI display.")
        # Return analysis output for the UI (reconstructs nested structure)
        ui_analysis_output = []
        for item in combined_data:
             readable_meetstaat_info = None
             if item['source'] in ['both', 'meetstaat_only']:
                 readable_meetstaat_info = {
                     'Description': item['meetstaat_description'],
                     'Quantity': item['meetstaat_quantity'], # UI might need formatting?
                     'Unit': item['meetstaat_unit'],
                     'Type': item['meetstaat_type'],
                     'Notes': item['meetstaat_notes']
                 }
             
             readable_lastenboek_info = None
             if item['source'] in ['both', 'lastenboek_only']:
                 readable_lastenboek_info = {
                     'title': item['lastenboek_title'],
                     'start_page': item['lastenboek_start_page'],
                     'end_page': item['lastenboek_end_page']
                 }
             
             # Construct a more UI-friendly output structure
             ui_friendly_item = {
                 'item_code': item['item_code'],
                 'meetstaat_present': item['source'] in ['both', 'meetstaat_only'],
                 'lastenboek_toc_entry_present': item['source'] in ['both', 'lastenboek_only'],
                 'meetstaat_info': readable_meetstaat_info,
                 'lastenboek_page_range': readable_lastenboek_info,
                 'llm_analysis': item.get('llm_analysis') # Placeholder for later use (NULL for first analysis)
             }
             ui_analysis_output.append(ui_friendly_item)

        return jsonify({
            'message': 'Analysis complete!',
            'errors': error_messages,
            'analysis_output': ui_analysis_output,
            'meetstaat_filename': meetstaat_filename or "Not provided",
            'lastenboek_filename': lastenboek_filename,
            'analysis_summary': analysis_summary,
            'toc_type': toc_type,
            'toc_path': os.path.basename(selected_toc_path) # Only send the filename, not the full path
        })

    except Exception as e:
        logger.exception("An error occurred during analysis:") # Log full traceback
        # Ensure temporary files are cleaned up even on error
        # ... (Add cleanup logic here too) ...
        # Retrieve filename if already set
        if 'lastenboek_file' in locals() and not lastenboek_filename:
            lastenboek_filename = secure_filename(lastenboek_file.filename)
        # Return error in the expected structure if possible, or a generic error
        return jsonify({
            'error': f'An unexpected error occurred: {str(e)}',
            'meetstaat_filename': meetstaat_filename if meetstaat_filename else 'Not Provided',
            'lastenboek_filename': lastenboek_filename if 'lastenboek_filename' in locals() else 'Unknown',
            'analysis_summary': {
                'count_both': 0,
                'count_meetstaat_only': 0,
                'count_lastenboek_only': 0
            },
            'analysis_output': [],
            'errors': [f'An unexpected error occurred: {str(e)}'],
            'message': 'Processing failed.'
             }), 500

# --- New Route for Discrepancy Analysis --- 
@app.route('/start_discrepancy_analysis', methods=['POST'])
def start_discrepancy_analysis():
    logger.info("--- Entering /start_discrepancy_analysis ---") # Log entry
    
    # --- Granular Logging --- 
    try:
        session_keys = list(session.keys()) # Get session keys
        logger.debug(f"Session keys at start of request: {session_keys}")
        has_key = 'analysis_results' in session
        is_data_present = bool(session.get('analysis_results')) # Check if data is truthy
        logger.debug(f"Checking session: has_key='{has_key}', is_data_present='{is_data_present}'")
    except Exception as e:
        logger.error(f"Error accessing session at start: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error accessing session data.'}), 500
    # --- End Granular Logging ---
        
    # Check if analysis results exist in session using the CORRECT key
    if not has_key or not is_data_present:
        logger.error("Session check failed: 'analysis_results' key not found or data is empty.")
        return jsonify({'error': 'No analysis results found in session. Please run analysis first.'}), 400
    
    logger.debug("Session check passed. Proceeding...") # Log success of check
    
    # Parse request to get selected items for analysis or analyze all
    try:
        req_data = request.get_json() or {}
        logger.debug(f"Parsed request data: {req_data}")
        selected_codes = req_data.get('selected_codes', [])
        logger.debug(f"Selected codes: {selected_codes}")
    except Exception as e:
        logger.error(f"Error parsing request JSON: {e}", exc_info=True)
        return jsonify({'error': 'Invalid request format.'}), 400
        
    # Use the CORRECT session key
    try:
        all_items_from_session = session['analysis_results'] 
        logger.debug(f"Successfully accessed session['analysis_results'] with {len(all_items_from_session)} items.")
    except Exception as e:
         logger.error(f"Error accessing session['analysis_results'] after check: {e}", exc_info=True)
         return jsonify({'error': 'Internal server error retrieving session data.'}), 500
    
    # --- Added Logging --- 
    logger.debug(f"Retrieved {len(all_items_from_session)} items from session['analysis_results']. First item (sample): {all_items_from_session[0] if all_items_from_session else 'N/A'}")
    # ---------------------
    
    # Log the request details
    logger.info(f"Starting discrepancy analysis for {len(selected_codes) if selected_codes else 'all'} items using data from session['analysis_results'].")
    
    # Prepare items for analysis
    items_to_analyze = []
    
    # Filter for items present in both meetstaat and lastenboek
    # Iterate over the data retrieved from the correct session key
    logger.debug("Filtering items from session for source == 'both'...")
    for item in all_items_from_session: 
        # Check the 'source' field which was determined in the /analyze route
        item_source = item.get('source')
        if item_source != 'both':
            logger.debug(f"  Skipping item {item.get('item_code')} (source: {item_source})")
            continue
            
        # If specific codes requested, check if this item is in the list
        if selected_codes and item.get('item_code') not in selected_codes:
            logger.debug(f"  Skipping item {item.get('item_code')} (not in selected codes)")
            continue
        
        logger.debug(f"  Adding item {item.get('item_code')} to analyze list.")
        # Construct the dictionary needed by analyze_batch_with_gemini
        # IMPORTANT: 'lastenboek_text' is likely MISSING or empty here based on /analyze route logic
        items_to_analyze.append({
            'item_code': item.get('item_code'),
            # Reconstruct meetstaat_info if needed by the LLM prompt 
            # (assuming the flattened structure in session['analysis_results'] is sufficient)
            'meetstaat_info': { 
                'Description': item.get('meetstaat_description'),
                'Quantity': item.get('meetstaat_quantity'),
                'Unit': item.get('meetstaat_unit'),
                'Type': item.get('meetstaat_type'),
                'Notes': item.get('meetstaat_notes')
            },
            # Reconstruct lastenboek_page_range if needed by the LLM prompt
            'lastenboek_page_range': { 
                'title': item.get('lastenboek_title'),
                'start': item.get('lastenboek_start_page'),
                'end': item.get('lastenboek_end_page')
             },
            'lastenboek_text': item.get('lastenboek_text', '') # Likely empty/missing!
        })
    
    # --- Added Logging --- 
    logger.info(f"Prepared {len(items_to_analyze)} items for batch analysis.")
    if len(items_to_analyze) > 0:
        logger.debug(f"First item to analyze (sample): {items_to_analyze[0]}")
    # ---------------------
        
    if not items_to_analyze:
        logger.warning("No items marked as 'both' found in session data for discrepancy analysis.")
        # --- Added Logging --- 
        error_payload = {'error': 'No valid items (found in both sources) available for analysis.'}
        logger.error(f"Returning 400 error with payload: {error_payload}")
        # ---------------------
        return jsonify(error_payload), 400
    
    # Process the items in batches to reduce API calls
    batch_size = 3  # Process 3 items at a time
    all_llm_results = {}
    
    # Split items into batches for processing
    batches = [items_to_analyze[i:i+batch_size] for i in range(0, len(items_to_analyze), batch_size)]
    
    logger.info(f"Processing {len(batches)} batches...") # Log batch count
    for i, batch in enumerate(batches):
        logger.info(f"Processing batch {i+1}/{len(batches)} with {len(batch)} items")
        
        # Send batch to the Gemini model for analysis
        batch_llm_results = analyze_batch_with_gemini(batch)
        logger.debug(f"LLM results for batch {i+1}: {batch_llm_results}") # Log LLM result for batch
        all_llm_results.update(batch_llm_results)
        
        # To avoid rate limiting, sleep briefly between batches
        if i < len(batches) - 1:
            time.sleep(1)
    
    # Store LLM results in session (optional, might not be needed)
    session['discrepancy_analysis_llm_results'] = all_llm_results 
    logger.info(f"Discrepancy analysis completed. LLM provided results for {len(all_llm_results)} items.")
    
    # Integrate LLM results back into a format suitable for the UI
    # The UI expects the original analysis structure plus the LLM results
    # We need to merge all_llm_results into the session['analysis_results'] data
    
    # Create the final list to send to the UI
    final_analysis_output_for_ui = []
    logger.debug("Merging LLM results with original session data for UI...")
    for item_from_session in session['analysis_results']: # Use correct key
        item_code = item_from_session.get('item_code')
        # Create a structure suitable for the UI (similar to how /analyze originally returned it)
        ui_item = {
             'item_code': item_code,
             'meetstaat_present': item_from_session.get('source') in ['both', 'meetstaat_only'],
             'lastenboek_toc_entry_present': item_from_session.get('source') in ['both', 'lastenboek_only'],
             'meetstaat_info': {
                 'Description': item_from_session.get('meetstaat_description'),
                 'Quantity': item_from_session.get('meetstaat_quantity'),
                 'Unit': item_from_session.get('meetstaat_unit'),
                 'Type': item_from_session.get('meetstaat_type'),
                 'Notes': item_from_session.get('meetstaat_notes')
             } if item_from_session.get('source') in ['both', 'meetstaat_only'] else None,
             'lastenboek_page_range': {
                 'title': item_from_session.get('lastenboek_title'),
                 'start': item_from_session.get('lastenboek_start_page'),
                 'end': item_from_session.get('lastenboek_end_page')
             } if item_from_session.get('source') in ['both', 'lastenboek_only'] else None,
             'llm_discrepancy_analysis': None # Default to None
         }
        
        # If this item was analyzed by the LLM, add the result
        if item_code in all_llm_results:
            ui_item['llm_discrepancy_analysis'] = all_llm_results[item_code]
            logger.debug(f"  Merged LLM result for item {item_code}")
        
        final_analysis_output_for_ui.append(ui_item)
        
    
    # Format response for the UI
    response_data = {
        'success': True,
        'item_count': len(all_llm_results), # Count of items actually analyzed by LLM
        'analysis_output': final_analysis_output_for_ui, # Send the merged data structure
        'message': f"Discrepancy analysis completed. Processed {len(all_llm_results)} items with LLM.",
        'toc_type': session.get('toc_type', 'standard'),  # Include the TOC type used in analysis
        'toc_path': session.get('toc_path', os.path.basename(TOC_JSON_PATH))  # Include the TOC path
    }
    
    # --- Store the final merged results in session for export --- 
    session['final_discrepancy_results'] = final_analysis_output_for_ui
    logger.info("Stored final discrepancy results in session['final_discrepancy_results'].")
    # -----------------------------------------------------------

    logger.info("--- Exiting /start_discrepancy_analysis successfully ---")
    return jsonify(response_data), 200
# ------------------------------------------

# Route for exporting JSON (remains the same, uses session data)
@app.route('/export_json')
def export_json():
    """Exports the last analysis results (flattened) stored in session as JSON."""
    # Retrieve the flattened data stored in the session
    analysis_results = session.get('analysis_results', [])
    if not analysis_results:
        return jsonify({"error": "No analysis results found in session. Please run analysis first."}), 404

    # Create a JSON response with headers for download
    response = make_response(jsonify(analysis_results)) # Already flattened
    response.headers["Content-Disposition"] = "attachment; filename=analysis_results.json"
    response.headers["Content-Type"] = "application/json"
    return response
# ------------------------------------

# --- New Route for Exporting Discrepancy Analysis JSON --- 
@app.route('/export_discrepancy_json')
def export_discrepancy_json():
    """Exports the discrepancy analysis results stored in session as JSON."""
    # Retrieve the discrepancy results stored in the session
    discrepancy_results = session.get('final_discrepancy_results', [])
    if not discrepancy_results:
        logger.warning("Attempted to export discrepancy JSON, but no results found in session.")
        return jsonify({"error": "No discrepancy analysis results found in session. Please run discrepancy analysis first."}), 404

    # Create a JSON response with headers for download
    response = make_response(jsonify(discrepancy_results))
    response.headers["Content-Disposition"] = "attachment; filename=discrepancy_analysis_results.json"
    response.headers["Content-Type"] = "application/json"
    logger.info("Exporting discrepancy analysis results as JSON.")
    return response
# ---------------------------------------------------------

# Run the Flask app
if __name__ == '__main__':
    # Use os.getenv('PORT', ...) for deployment flexibility (like Cloud Run)
    # Change the default port to 9000 as requested
    port = int(os.getenv('PORT', 9000))
    # Use host='0.0.0.0' to make it accessible on your network
    # Set debug=False for production environments
    app.run(debug=True, host='0.0.0.0', port=port) 