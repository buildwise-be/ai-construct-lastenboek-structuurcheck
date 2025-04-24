import os
import json
import argparse
import logging
import time
import sys
from typing import Dict, List, Any

# --- Add Vertex AI imports ---
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel, Part
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    logging.error("Vertex AI libraries not found. Please install google-cloud-aiplatform.")
    sys.exit(1)
# ---------------------------

# --- Configuration ---
# Get Vertex AI config from environment variables
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
DEFAULT_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-001") # Or another suitable model

GENERATION_CONFIG = {
    "temperature": 0.3, # Lower temperature for more deterministic analysis
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json", # Request JSON directly
}

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def load_toc_data(filepath: str) -> Dict[str, Any] | None:
    """Loads the TOC JSON data from the specified file."""
    logger.info(f"Loading TOC JSON from: {filepath}")
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            toc_data = json.load(f)
        logger.info(f"Successfully loaded TOC JSON data from {filepath}.")
        return toc_data
    except FileNotFoundError:
        logger.error(f"TOC JSON file not found at: {filepath}")
        return None
    except json.JSONDecodeError as json_err:
        logger.error(f"Error decoding TOC JSON file '{filepath}': {json_err}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred loading TOC JSON '{filepath}': {e}")
        return None

def extract_items_for_analysis(toc_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursively extracts items with summaries from the TOC for analysis."""
    items_to_analyze = []
    
    def recurse_toc(data: Dict[str, Any] | List[Any], current_path=""):
        if isinstance(data, dict):
            for key, value in data.items():
                # Construct the item code path (e.g., "01.02.A")
                # This assumes keys directly represent the codes or parts of them
                item_code = f"{current_path}.{key}".strip('.') if current_path else key 
                
                if isinstance(value, dict):
                    # Check if it's an entry with the required fields for analysis
                    is_analyzable_entry = all(k in value for k in ('title', 'summary', 'start', 'end')) and value.get('summary')

                    if is_analyzable_entry:
                        # Extract relevant info for the prompt
                        item_info = {
                            "item_code": item_code,
                            "lastenboek_title": value.get('title', 'N/A'),
                            "lastenboek_summary": value.get('summary', 'N/A'),
                            # Page range might be useful context for the LLM, even if not strictly required
                            "lastenboek_start": value.get('start'),
                            "lastenboek_end": value.get('end'),
                            # Include tasks if available, might help placement check
                            "lastenboek_tasks": value.get('tasks', []) 
                        }
                        items_to_analyze.append(item_info)
                        # Continue recursion for potential sub-items within this entry
                        recurse_toc(value, item_code) 
                    else:
                         # Recurse into sub-dictionaries even if not analyzable themselves
                         recurse_toc(value, item_code)
                elif isinstance(value, list):
                     recurse_toc(value, item_code) # Recurse into lists within dicts

        elif isinstance(data, list):
            for index, item in enumerate(data):
                # Lists usually don't have inherent codes, pass parent path
                recurse_toc(item, current_path)

    recurse_toc(toc_data)
    logger.info(f"Extracted {len(items_to_analyze)} items with summaries for analysis.")
    return items_to_analyze

def analyze_task_placement_batch(batch: List[Dict[str, Any]], model: GenerativeModel) -> Dict[str, Dict[str, Any]]:
    """Sends a batch of items to the LLM for task placement analysis."""
    if not batch:
        return {}

    # --- Construct the prompt ---
    prompt_parts = [
        "You are an expert construction contract analyst reviewing a Lastenboek (Specifications) Table of Contents (TOC).",
        "For EACH item provided below (representing a section in the TOC), perform the following check:",
        
        "\n--- CHECK 1: TASK PLACEMENT CHECK ---",
        "Evaluate if the tasks described in the 'TOC Summary' and 'TOC Tasks' seem contextually appropriate for the section defined by the 'Item Code' and 'TOC Title'.",
        "Look for summaries or tasks described that seem misplaced given the section's title or typical hierarchical placement within construction specifications.",
        "Examples of potential misplacements: painting tasks described under a woodworking code/title (e.g., 34.xx), detailed electrical work summarized under a structural chapter (e.g., 2x.xx), foundation work details appearing in a finishing chapter (e.g., 4x.xx or higher).",
        
        "\nFormat your analysis for EACH item as a JSON object in this exact structure:",
        "{",
        "  \"item_code\": \"the item code\",",
        "  \"checks\": {",
        "    \"task_placement\": {",
        "      \"issue_found\": true/false,",
        "      \"description\": \"Detailed description of the potentially misplaced task(s)/summary content or 'Tasks/Summary seem appropriately placed.'\",",
        "      \"significant\": true/false", # Significance based on how out-of-place it seems
        "    }",
        "  },",
        "  \"summary\": \"Brief overall summary of any placement issues for this item, or 'No placement issues identified.'\",",
        "  \"has_significant_issue\": true/false",
        "}",
        
        "\nGuidelines:",
        "1. Base your judgment *only* on the provided Item Code, TOC Title, TOC Summary, and TOC Tasks.",
        "2. Set 'issue_found' to true if any part of the summary or tasks seems potentially misplaced.",
        "3. Set 'significant' to true ONLY for tasks/summaries that seem clearly and significantly misplaced (e.g., wrong construction phase/discipline).",
        "4. Set 'has_significant_issue' to true if the 'task_placement' check has 'significant' set to true.",
        "5. If 'issue_found' is false, set 'description' to 'Tasks/Summary seem appropriately placed.' and 'significant' to false.",
        "6. For 'summary', briefly describe the main misplaced element and why it seems out of place. If no issues, use 'No placement issues identified.'",
        
        "\n--- ITEMS FOR ANALYSIS ---"
    ]
    
    # Add details for each item in the batch
    for item in batch:
        prompt_parts.append("\n---") # Separator
        prompt_parts.append(f"Item Code: {item.get('item_code', 'N/A')}")
        prompt_parts.append(f"TOC Title: {item.get('lastenboek_title', 'N/A')}")
        prompt_parts.append(f"Page Range: {item.get('lastenboek_start', '?')} - {item.get('lastenboek_end', '?')}") # Context
        prompt_parts.append(f"TOC Summary: {item.get('lastenboek_summary', 'N/A')}")
        tasks = item.get('lastenboek_tasks', [])
        tasks_str = "\n".join([f"- {task}" for task in tasks]) if tasks else "No specific tasks listed."
        prompt_parts.append(f"TOC Tasks:\n{tasks_str}")

    # Final instructions
    prompt_parts.append("\n--- END ITEMS --- ")
    prompt_parts.append("\nReturn your analysis STRICTLY as a JSON array of objects, with one object per item, following the exact structure specified above. Ensure the output is valid JSON.")
    prompt = "\n".join(prompt_parts)

    # Initialize results dict with error placeholders
    batch_results = {item.get("item_code"): {"error": "Analysis not received for this item in batch."} for item in batch}

    # --- Call the LLM ---
    max_retries = 3
    initial_delay = 5 # seconds
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Sending batch prompt to Gemini ({len(batch)} items). First item: {batch[0].get('item_code')}")
            # Explicitly ask for JSON response type
            response = model.generate_content(prompt, generation_config=GENERATION_CONFIG, stream=False)
            logger.debug(f"Received batch response from Gemini. First item: {batch[0].get('item_code')}")

            if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                response_text = response.candidates[0].content.parts[0].text
                # Attempt to parse the response as JSON
                try:
                    # Response should already be JSON due to mime_type, but add failsafe cleaning
                    cleaned_text = response_text.strip()
                    if cleaned_text.startswith("```json"):
                        cleaned_text = cleaned_text[7:-3].strip()
                    elif cleaned_text.startswith("```"):
                         cleaned_text = cleaned_text[3:-3].strip()

                    parsed_results = json.loads(cleaned_text)
                    
                    if isinstance(parsed_results, list):
                        # Update batch_results with successful analyses
                        found_codes = set()
                        for result_item in parsed_results:
                            if isinstance(result_item, dict) and 'item_code' in result_item:
                                code = result_item['item_code']
                                if code in batch_results: # Check if it belongs to this batch
                                     batch_results[code] = result_item # Store the structured result
                                     found_codes.add(code)
                        
                        # Mark items requested but not found in the response as errors
                        for item in batch:
                            code = item.get("item_code")
                            if code not in found_codes:
                                batch_results[code] = {"error": "Item analysis missing in Gemini batch response."}
                                logger.warning(f"Analysis missing for item {code} in batch response.")
                                
                        return batch_results # Success

                    else:
                        logger.error(f"Gemini response was not a JSON list. Content: {response_text[:500]}...")
                        error_msg = {"error": "Gemini response was not a JSON list."}

                except json.JSONDecodeError as json_e:
                    logger.error(f"Failed to decode Gemini JSON response: {json_e}. Response: {response_text[:500]}...")
                    error_msg = {"error": f"Failed to decode Gemini JSON response. {json_e}"}
            else:
                logger.warning(f"Gemini batch response structure unexpected or empty. Response: {response}")
                error_msg = {"error": "Unexpected or empty response from Gemini."}

            # If parsing failed or structure was wrong, fill results with the error
            for item_code in batch_results:
                 batch_results[item_code] = error_msg
            return batch_results # Return errors

        except exceptions.ResourceExhausted as quota_error:
            # Specific handling for Quota errors with exponential backoff
             logger.warning(f"Quota Error encountered (Attempt {attempt + 1}/{max_retries}): {quota_error}")
             if attempt < max_retries - 1:
                 jitter = random.uniform(0, 1) 
                 sleep_time = initial_delay * (2 ** attempt) + jitter
                 logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                 time.sleep(sleep_time)
             else:
                 error_msg = {"error": f"Quota exceeded after {max_retries} attempts. {quota_error}"}
                 logger.error(error_msg["error"])
                 for item_code in batch_results: batch_results[item_code] = error_msg

        except Exception as e:
            logger.error(f"Error calling Gemini API (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                sleep_time = initial_delay * (2 ** attempt) # Exponential backoff for general errors too
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
            else:
                error_msg = {"error": f"Failed to get analysis after {max_retries} attempts. Last error: {e}"}
                logger.error(error_msg["error"])
                # Fill results with the final error
                for item_code in batch_results:
                    batch_results[item_code] = error_msg

    return batch_results # Return results (potentially with errors if all retries failed)


def save_results(results: Dict[str, Any], filepath: str):
    """Saves the analysis results to a JSON file."""
    logger.info(f"Saving analysis results to: {filepath}")
    try:
        output_dir = os.path.dirname(filepath)
        if output_dir:
             os.makedirs(output_dir, exist_ok=True)
             
        # Save as a list of results for easier processing later
        result_list = list(results.values()) 
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_list, f, indent=4, ensure_ascii=False)
        logger.info(f"Successfully saved {len(result_list)} results to {filepath}.")
    except Exception as e:
        logger.error(f"Error saving output JSON file '{filepath}': {e}")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description='Perform Task Placement analysis on a TOC JSON file using Vertex AI.')
    parser.add_argument('--toc_json', type=str, 
                        default=r"C:\\Users\\gr\\Documents\\GitHub\\Meetstaatincorp\\output\\plint_toc_with_summaries_tasks.json",
                        help='Path to the input TOC JSON file (must contain summaries/tasks).')
    parser.add_argument('--pdf_input', type=str, 
                        default=r"C:\\Users\\gr\\Documents\\GitHub\\Meetstaatincorp\\samengevoegdamsterdamlastenboek.pdf",
                        required=False,
                        help='Path to the corresponding PDF file (for context/reference, not processed).')
    parser.add_argument('--output_json', type=str, 
                        default="output/task_placement_results.json",
                        help='Path to save the output analysis results JSON file.')
    parser.add_argument('--model', type=str, default=DEFAULT_MODEL_NAME,
                        help=f'Name of the Vertex AI Gemini model to use (default: {DEFAULT_MODEL_NAME}).')
    parser.add_argument('--batch_size', type=int, default=5,
                        help='Number of items to process in each batch API call (default: 5).')

    args = parser.parse_args()

    # --- Validate Vertex AI Setup ---
    if not VERTEX_AI_AVAILABLE:
        logger.error("Vertex AI libraries not found. Exiting.")
        sys.exit(1)
        
    if not PROJECT_ID:
        logger.error("GOOGLE_CLOUD_PROJECT environment variable not set. Required for Vertex AI. Exiting.")
        sys.exit(1)

    # --- Initialize Vertex AI ---
    try:
        logger.info(f"Initializing Vertex AI for Project: {PROJECT_ID}, Location: {LOCATION}")
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel(args.model)
        logger.info(f"Vertex AI GenerativeModel '{args.model}' initialized.")
    except Exception as e:
        logger.error(f"Error initializing Vertex AI or model '{args.model}': {e}")
        sys.exit(1)

    # --- Load Input TOC ---
    toc_data = load_toc_data(args.toc_json)
    if toc_data is None:
        sys.exit(1) # Exit if TOC loading failed

    # --- Extract Items ---
    items_to_analyze = extract_items_for_analysis(toc_data)
    if not items_to_analyze:
        logger.warning("No items with summaries found in the TOC file. Nothing to analyze.")
        save_results({}, args.output_json) # Save an empty result file
        sys.exit(0)

    # --- Process in Batches ---
    all_results = {}
    batch_size = args.batch_size
    batches = [items_to_analyze[i:i+batch_size] for i in range(0, len(items_to_analyze), batch_size)]
    
    logger.info(f"Processing {len(items_to_analyze)} items in {len(batches)} batches (size={batch_size})...")
    
    total_processed = 0
    total_errors = 0
    
    for i, batch in enumerate(batches):
        logger.info(f"Processing batch {i+1}/{len(batches)}...")
        batch_results = analyze_task_placement_batch(batch, model)
        all_results.update(batch_results)
        
        # Log batch outcome
        errors_in_batch = sum(1 for res in batch_results.values() if isinstance(res, dict) and 'error' in res)
        success_in_batch = len(batch) - errors_in_batch
        total_processed += success_in_batch
        total_errors += errors_in_batch
        logger.info(f"Batch {i+1} finished. Success: {success_in_batch}, Errors: {errors_in_batch}")
        
        # Optional: Add a small delay between batches to avoid hitting rate limits aggressively
        if i < len(batches) - 1:
            time.sleep(1) # 1-second delay

    # --- Save Results ---
    logger.info(f"Analysis complete. Total successfully processed: {total_processed}, Total errors: {total_errors}")
    save_results(all_results, args.output_json)

if __name__ == "__main__":
    main() 