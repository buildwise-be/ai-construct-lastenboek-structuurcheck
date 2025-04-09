import PyPDF2
import json
import os
import google.generativeai as genai

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
# STEP 2: LOAD THE PDF
# ----------------------------------------------------------------
# IMPORTANT: Replace this with the actual path to your PDF file
PDF_PATH = "your_lastenboek.pdf" # <--- CHANGE THIS
# Ensure the file exists before proceeding
if not os.path.exists(PDF_PATH):
    raise FileNotFoundError(f"PDF file not found at path: {PDF_PATH}. Please update the PDF_PATH variable.")

reader = PyPDF2.PdfReader(open(PDF_PATH, 'rb'))
num_pages = len(reader.pages)

# ----------------------------------------------------------------
# STEP 3: RECURSIVELY PARSE TOC AND EXTRACT TEXT CHUNKS
# ----------------------------------------------------------------
def extract_section_text(start_page: int, end_page: int) -> str:
    """Extracts text from the PDF for pages [start_page..end_page]."""
    # Adjust for 0-based indexing if your TOC uses 1-based page numbers
    # Example: If TOC uses 1-based pages, use range(start_page - 1, end_page)
    # Assuming TOC uses 0-based index for now matching PyPDF2
    text_content = []
    # Ensure start and end pages are within the valid range
    actual_start = max(0, start_page)
    actual_end = min(num_pages -1, end_page) # PyPDF2 pages are 0-indexed

    for p in range(actual_start, actual_end + 1):
        try:
            page = reader.pages[p]
            page_text = page.extract_text() or ""
            text_content.append(page_text)
        except IndexError:
            print(f"Warning: Page index {p} out of range (Total pages: {num_pages}). Skipping.")
        except Exception as e:
            print(f"Warning: Could not extract text from page {p}. Error: {e}. Skipping.")

    return "\n".join(text_content)

def traverse_toc(node: dict, code: str) -> list:
    """
    Recursively traverse the TOC structure to pull text by page range.
    Returns a list of dicts like:
        [{
            'code': '00.01',
            'title': 'MONSTERS, STALEN, MODELLEN.',
            'content': '... extracted PDF text ...'
        }, ...]
    """
    result = []

    # Use .get with default values to handle potentially missing keys
    start = node.get("start")
    end = node.get("end")
    title = node.get("title", "Untitled Section") # Provide a default title

    # Extract text only if start and end pages are valid integers
    if isinstance(start, int) and isinstance(end, int) and start >= 0 and end >= start:
        section_text = extract_section_text(start, end)
        if code:  # Only store if we have a code associated with this level
            result.append({
                "code": code,
                "title": title,
                "content": section_text
            })
    elif code: # If we have a code but no valid pages, log a warning or store empty content
         print(f"Warning: Invalid or missing page range for code {code} ('{title}'). Start: {start}, End: {end}")
         result.append({
                "code": code,
                "title": title,
                "content": "" # Store empty content or handle as needed
            })


    # Traverse subsections if they exist
    sub_sections = node.get("sections", {})
    if isinstance(sub_sections, dict):
        for subcode, subnode in sub_sections.items():
            # Ensure subnode is a dictionary before recursing
            if isinstance(subnode, dict):
                result.extend(traverse_toc(subnode, code=subcode))
            else:
                 print(f"Warning: Expected dictionary for subsection {subcode}, but got {type(subnode)}. Skipping.")

    return result

# ----------------------------------------------------------------
# STEP 4: BUILD A LIST OF SECTION CHUNKS
# ----------------------------------------------------------------
section_chunks = []
for top_level_code, top_level_node in toc.items():
    # Ensure the top-level node is a dictionary
    if isinstance(top_level_node, dict):
        # Pass the top-level code itself when starting traversal for that branch
        section_chunks.extend(traverse_toc(top_level_node, code=top_level_code))
    else:
        print(f"Warning: Expected dictionary for top-level code {top_level_code}, but got {type(top_level_node)}. Skipping.")


# Now section_chunks is a list of {code, title, content}.
# e.g. [
#   {'code': '00', 'title': 'ALGEMEENHEDEN.', 'content': '...'},
#   {'code': '00.01', 'title': 'MONSTERS, STALEN, MODELLEN.', 'content': '...'},
#   ...
# ]
print(f"Extracted {len(section_chunks)} section chunks from the TOC and PDF.")

# ----------------------------------------------------------------
# STEP 5: CONFIGURE AND SEND CHUNKS TO GEMINI FOR ANALYSIS
# ----------------------------------------------------------------

# IMPORTANT: Set your API key as an environment variable
# Example (Bash/Zsh): export GOOGLE_API_KEY="YOUR_API_KEY"
# Example (PowerShell): $env:GOOGLE_API_KEY="YOUR_API_KEY"
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    raise ValueError("Google API Key not found. Please set the GOOGLE_API_KEY environment variable.")

genai.configure(api_key=API_KEY)

# Choose a Gemini model (e.g., 'gemini-1.5-flash' or 'gemini-pro')
MODEL_NAME = "gemini-1.5-flash"
model = genai.GenerativeModel(MODEL_NAME)

def call_llm_api(chunk_text: str, task_description: str = "") -> str:
    """
    Calls the configured Generative AI model.
    - chunk_text: the text from the section
    - task_description: any instructions for the LLM
    Returns the LLM's response as a string.
    Handles potential API errors gracefully.
    """
    if not chunk_text.strip():
        return "Skipped: Section content is empty."

    prompt = f"{task_description}\n\nText:\n{chunk_text}"

    try:
        # Adjust generation config as needed (optional)
        generation_config = genai.types.GenerationConfig(
            # candidate_count=1, # Already defaults to 1
            # stop_sequences=['\n'], # Example stop sequence
            # max_output_tokens=2048, # Example max tokens
            temperature=0.7 # Example temperature
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config,
            # safety_settings=... # Optional: configure safety settings if needed
            )

        # Access the text content correctly based on the library's structure
        # Check if response.parts exists and has content
        if response.parts:
             return response.text # Use the .text accessor
        elif response.prompt_feedback:
             # Handle cases where content might be blocked due to safety settings
             return f"Blocked due to safety reasons: {response.prompt_feedback}"
        else:
            # Handle unexpected empty responses
            return "No response generated."

    except Exception as e:
        # Catch potential API errors (network issues, invalid requests, etc.)
        print(f"Error calling Generative AI API: {e}")
        return f"Error: Could not get response from LLM. Details: {e}"


# A sample analysis function that sends each chunk to the LLM
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

print("Starting LLM analysis...")
llm_results = analyze_sections_with_llm(section_chunks)
print("LLM analysis finished.")

# ----------------------------------------------------------------
# STEP 6: DO SOMETHING WITH THE RESULTS
# ----------------------------------------------------------------
# e.g., print or save to JSON
output_filename = "analysis_results.json"
try:
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(llm_results, f, ensure_ascii=False, indent=2)
    print(f"LLM analysis complete! Results saved to {output_filename}.")
except IOError as e:
    print(f"Error writing results to {output_filename}: {e}")
    # Optionally print results to console if writing fails
    # print("\n--- Analysis Results ---")
    # for res in llm_results:
    #     print(f"Code: {res['code']} - Title: {res['title']}")
    #     print(f"Analysis:\n{res['analysis']}\n{'-'*20}")

# Example of how to access a specific result
# if llm_results:
#    print("
Example result for the first analyzed section:")
#    print(json.dumps(llm_results[0], indent=2, ensure_ascii=False)) 