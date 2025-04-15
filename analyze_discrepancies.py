import argparse
import json
import logging
import os
from pathlib import Path
import time

from google.cloud import aiplatform
from google.cloud.aiplatform.gapic.schema import predict
from vertexai.generative_models import GenerativeModel, Part

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def analyze_item_with_gemini(
    model: GenerativeModel,
    item: dict,
    project_id: str,
    location: str
) -> str:
    """
    Sends item details to Gemini for discrepancy analysis.

    Args:
        model: Initialized Vertex AI GenerativeModel.
        item: A dictionary representing one item from the analysis results.
        project_id: Google Cloud project ID.
        location: Google Cloud location (e.g., 'us-central1').

    Returns:
        The analysis result string from Gemini, or an error message.
    """
    # --- Construct the prompt ---
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
            logger.debug(f"Sending prompt to Gemini for item {item.get('item_code')}:\n{prompt}")
            response = model.generate_content(prompt)
            logger.debug(f"Received response from Gemini for item {item.get('item_code')}")
            # Accessing the text safely
            if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                 analysis_text = response.candidates[0].content.parts[0].text
                 # Basic safety check for potentially harmful content flags (optional)
                 # if response.candidates[0].finish_reason != 'STOP':
                 #     logger.warning(f"Gemini response for item {item.get('item_code')} finished with reason: {response.candidates[0].finish_reason}")
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
    return "Error: Analysis failed after retries." # Should not be reached if loop completes


def main():
    parser = argparse.ArgumentParser(description="Analyze discrepancies between Meetstaat and Lastenboek using Gemini.")
    parser.add_argument("input_json", type=str, help="Path to the input analysis_results.json file.")
    parser.add_argument("--project-id", required=True, type=str, help="Google Cloud Project ID.")
    parser.add_argument("--location", default="us-central1", type=str, help="Google Cloud location (e.g., us-central1).")
    parser.add_argument("--model-name", default="gemini-1.5-flash-001", type=str, help="Gemini model name (e.g., gemini-1.5-flash-001).")
    parser.add_argument("--output-json", type=str, help="Path for the output JSON file with analysis results. Defaults to adding '_analyzed' before .json.")
    args = parser.parse_args()

    input_path = Path(args.input_json)
    if not input_path.is_file():
        logger.error(f"Input file not found: {input_path}")
        return

    if not args.output_json:
        output_path = input_path.with_stem(f"{input_path.stem}_analyzed")
    else:
        output_path = Path(args.output_json)

    # Load the input JSON data
    logger.info(f"Loading data from: {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {input_path}: {e}")
        return
    except Exception as e:
        logger.error(f"Error reading file {input_path}: {e}")
        return

    # Initialize Vertex AI
    logger.info(f"Initializing Vertex AI for project '{args.project_id}' in location '{args.location}'")
    try:
        aiplatform.init(project=args.project_id, location=args.location)
        model = GenerativeModel(args.model_name)
        logger.info(f"Using Gemini model: {args.model_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI or load model: {e}")
        logger.error("Ensure the Vertex AI API is enabled and your credentials are set up correctly.")
        return

    # Process items
    results_with_analysis = []
    total_items = len(analysis_data)
    items_to_analyze_count = sum(1 for item in analysis_data if item.get("source") == "both")
    logger.info(f"Found {total_items} total items. Analyzing {items_to_analyze_count} items present in both sources.")

    processed_count = 0
    for i, item in enumerate(analysis_data):
        if item.get("source") == "both":
            processed_count += 1
            logger.info(f"Analyzing item {processed_count}/{items_to_analyze_count} (Code: {item.get('item_code', 'N/A')})...")
            analysis_result = analyze_item_with_gemini(model, item, args.project_id, args.location)
            item["llm_discrepancy_analysis"] = analysis_result # Add analysis result
        else:
            # Keep items not analyzed, but mark analysis as N/A
            item["llm_discrepancy_analysis"] = "N/A (Source not 'both')"

        results_with_analysis.append(item) # Add item (analyzed or not) to the final list

    # Save the results
    logger.info(f"Saving analysis results to: {output_path}")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results_with_analysis, f, indent=2, ensure_ascii=False)
        logger.info("Analysis complete.")
    except Exception as e:
        logger.error(f"Error writing output file {output_path}: {e}")

if __name__ == "__main__":
    main() 