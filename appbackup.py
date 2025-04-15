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

from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
import tempfile # For handling temporary files
import logging
from werkzeug.utils import secure_filename # For safe filenames
import json # <-- Import json

# Import the refactored function
from llm_toc_analyzer import get_toc_page_ranges_from_json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
# Use instance_relative_config=True if you plan to use instance folders later
app = Flask(__name__, instance_relative_config=True)
# Create an 'uploads' directory if it doesn't exist (for temporary storage)
# Consider using Flask's instance folder for better practice: app.instance_path
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Add a secret key for session management if needed later
app.config['SECRET_KEY'] = os.urandom(24)

# --- Define path to the TOC JSON file --- 
TOC_JSON_PATH = os.path.join(os.path.dirname(__file__), 'step1_toc', 'chapters.json')

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
        # --- Load TOC JSON from File --- 
        logger.info(f"Loading TOC data from: {TOC_JSON_PATH}")
        try:
            with open(TOC_JSON_PATH, 'r', encoding='utf-8') as f:
                toc_data = json.load(f)
            logger.info("Successfully loaded TOC JSON data.")
        except FileNotFoundError:
            logger.error(f"TOC JSON file not found at: {TOC_JSON_PATH}")
            error_messages.append(f"Critical error: TOC JSON file not found at {TOC_JSON_PATH}")
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

        # --- Combine Data ---
        combined_data = []
        # Normalize keys from both sources before creating the union set
        normalized_meetstaat_codes = {normalize_code(k) for k in meetstaat_items.keys()}
        normalized_toc_codes = {normalize_code(k) for k in toc_page_ranges.keys()}
        all_item_codes = normalized_meetstaat_codes | normalized_toc_codes

        for code in sorted(list(all_item_codes)):
            # Use the *normalized* code to look up in the original dictionaries
            # Note: This assumes the original dicts still use the un-normalized keys
            # This might be inefficient. A better approach might be to create
            # normalized dictionaries upfront. Let's adjust parse_meetstaat_csv and
            # get_toc_page_ranges_from_json to return normalized keys directly.
            # REVERTING this specific change for now, applying normalization only in parse_meetstaat_csv.

            meetstaat_info = meetstaat_items.get(code) # Assumes meetstaat_items now has normalized keys
            lastenboek_range_info = toc_page_ranges.get(code) # Assumes toc_page_ranges keys are already normalized

            # Ensure meetstaat_info is serializable (convert pandas types if necessary)
            serializable_meetstaat_info = None
            if meetstaat_info:
                serializable_meetstaat_info = {k: v for k, v in meetstaat_info.items() if pd.notna(v)}

            combined_data.append({
                "item_code": code,
                "meetstaat_present": meetstaat_info is not None,
                "lastenboek_toc_entry_present": lastenboek_range_info is not None,
                "meetstaat_info": serializable_meetstaat_info,
                "lastenboek_page_range": lastenboek_range_info,
                "comparison_result": "Comparison not yet implemented." # Placeholder
            })

        logger.info(f"Combined data for {len(combined_data)} unique item codes.")

        # --- Placeholder for Comparison Logic ---
        # Here you would iterate through combined_data
        # If meetstaat_present and lastenboek_toc_entry_present:
        #   - Render PDF pages in lastenboek_page_range to image(s) using PyMuPDF
        #   - Call multimodal LLM with meetstaat_info and image(s)
        #   - Update item['comparison_result']
        # ----------------------------------------

        results = {
            'message': 'Files processed. Combined data generated. Comparison pending.',
            'meetstaat_filename': meetstaat_filename if meetstaat_filename else 'Not provided',
            'lastenboek_filename': lastenboek_filename,
            'errors': error_messages,
            'analysis_output': combined_data # Send the combined list
        }

    except ValueError as ve: # Catch specific errors like missing CSV column
         logger.error(f"Data processing error: {ve}", exc_info=True)
         # Clean up saved files on error
         if lastenboek_path and os.path.exists(lastenboek_path): os.remove(lastenboek_path)
         if meetstaat_path and os.path.exists(meetstaat_path): os.remove(meetstaat_path)
         return jsonify({'error': f'Data processing error: {ve}'}), 500
    except Exception as e:
        logger.error(f"An unexpected error occurred during analysis: {e}", exc_info=True)
        # Clean up saved files on error
        if lastenboek_path and os.path.exists(lastenboek_path): os.remove(lastenboek_path)
        if meetstaat_path and os.path.exists(meetstaat_path): os.remove(meetstaat_path)
        return jsonify({'error': f'An unexpected server error occurred: {e}'}), 500
    finally:
        # --- Clean up uploaded files ---
        # Important in a real app to avoid filling disk space
        try:
            if lastenboek_path and os.path.exists(lastenboek_path):
                os.remove(lastenboek_path)
                logger.info(f"Removed temporary file: {lastenboek_path}")
            if meetstaat_path and os.path.exists(meetstaat_path):
                os.remove(meetstaat_path)
                logger.info(f"Removed temporary file: {meetstaat_path}")
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")

    # Return the results as JSON
    return jsonify(results)

# Run the Flask app
if __name__ == '__main__':
    # Use os.getenv('PORT', 5000) for deployment flexibility (like Cloud Run)
    port = int(os.getenv('PORT', 5000))
    # Use host='0.0.0.0' to make it accessible on your network
    app.run(debug=True, host='0.0.0.0', port=port) 