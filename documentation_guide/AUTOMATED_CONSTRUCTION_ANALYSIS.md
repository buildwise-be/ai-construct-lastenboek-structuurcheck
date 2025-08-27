# 1. OVERVIEW & INTRODUCTION

## 1.1 System Purpose & Business Context

Manual verification of construction documents—ensuring the correct placement of tasks within the Specifications (*Lastenboek*)—is a time-consuming and error-prone process. A single project can involve thousands of items, and verifying that every task is described in the logically correct chapter requires meticulous effort. Errors in placement can lead to confusion, missed requirements, and contractual disputes.

The primary purpose of the **Automated Construction Analysis Tool** is to serve as an extensible platform for performing **automated placement and consistency checks**. While its initial scope included comparing the Bill of Quantities (*Meetstaat*) with the *Lastenboek*, the core value was found in analyzing the internal structure and logic of the *Lastenboek* itself. The tool now focuses on this high-value task, freeing up professionals to focus on more complex issues.

### 1.2 Key Capabilities & Features

The system's features are centered on this focused analysis:

1.  **Dynamic Table of Contents (TOC) Generation**: The system intelligently analyzes a *Lastenboek* PDF and automatically generates a structured Table of Contents. This is the foundational step for all subsequent analysis.
2.  **Task Placement Analysis**: This is the core feature. Using the generated TOC, the system analyzes the full text of each chapter to verify that the tasks described within it are contextually appropriate. It flags items that appear misplaced (e.g., finishing work detailed in a structural chapter).
3.  **Extensible Analysis Framework**: The system is built in a modular way, allowing new types of automated checks to be added on top of the core functionality with minimal effort.
4.  **Interactive Web Interface & Data Export**: A user-friendly interface allows for easy operation, review of results, and export to JSON for further use.
5.  **(Legacy) Meetstaat Comparison**: The codebase retains the ability to compare a *Meetstaat* (CSV) for consistency, but this is considered a secondary, optional feature in the current workflow.

### 1.3 Core Process Overview

The system operates through a clear, multi-stage workflow:

1.  **Document Upload**: The user uploads the *Lastenboek* (PDF) via the web interface.
2.  **Dynamic TOC Generation**: The backend `toc_generation_module` processes the PDF, using the Gemini AI model to identify and structure the document's chapters and sections.
3.  **Initial Analysis Display**: The generated TOC is displayed to the user in the interface.
4.  **Enhanced Analysis (User-Triggered)**: The user can then initiate a more detailed analysis, such as the "Placement Check."
5.  **LLM-Powered Analysis**: The backend (`app_enhanced_oldui.py`) sends the relevant chapter data to the Gemini AI model with specific prompts to perform the requested analysis (e.g., checking for misplaced tasks).
6.  **Results Integration**: The AI's findings are integrated with the TOC data and displayed in the results table, highlighting potential issues with clear descriptions.

# 2. TECHNICAL ARCHITECTURE & WORKFLOW

This section provides a detailed, step-by-step breakdown of the system's execution flow, from user input to the final analysis output. It is primarily intended for developers and technical stakeholders.

> **📸 Image showing a high-level system architecture diagram with main components (Frontend, Flask Backend, Vertex AI) and data flow should be placed here**

## 2.1 High-Level Process Overview

The end-to-end process can be summarized in the following stages:

1.  **Frontend Interaction**: The user uploads a *Lastenboek* PDF through the web interface (`oldui.html`).
2.  **Initial Backend Processing**: The Flask application (`app_enhanced_oldui.py`) receives the file.
3.  **Dynamic TOC Generation**: The `toc_generator.py` script is called to analyze the PDF and generate a structured Table of Contents using the Gemini AI model.
4.  **UI Update (TOC Display)**: The generated TOC is sent back to the frontend and displayed to the user.
5.  **Enhanced Analysis Trigger**: The user initiates a "Placement Check" for the generated TOC.
6.  **Rule-Based Content Analysis**: The `enhanced_task_checker.py` script analyzes the full text of each chapter to classify its content type using a rule-based keyword system.
7.  **UI Update (Final Results)**: The final, enriched analysis data is returned to the frontend and displayed in the results table, highlighting content types, issues, and suggestions.

## 2.2 Detailed Step-by-Step Workflow

### 2.2.1 Step 1: Document Upload (Frontend)

The process begins in the user's browser. The main interface is defined in `Templates/oldui.html`. It contains a simple form for uploading the *Lastenboek* PDF.

When the "Analyze Document" button is clicked, a JavaScript event listener gathers the file and initiates a `fetch` request to the backend `/analyze` endpoint.

**📍 Location**: `Templates/oldui.html`

```html
<!-- ... existing code ... -->
<form id="upload-form" class="space-y-4">
    <div>
        <label for="lastenboek-file" class="block text-sm font-medium text-gray-300">Lastenboek (PDF)</label>
        <input type="file" id="lastenboek-file" name="lastenboek" accept=".pdf" class="mt-1 block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-500 file:text-white hover:file:bg-blue-600"/>
    </div>
    <!-- ... existing code ... -->
    <button type="button" id="analyzeButton" class="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 focus:ring-offset-gray-800">Analyze Document</button>
</form>
<!-- ... existing code ... -->
<script>
// ... existing code ...
analyzeButton.addEventListener('click', () => {
    // ... existing code ...
    const formData = new FormData();
    formData.append('lastenboek', lastenboekFile);
    formData.append('toc_type', selectedTocType);
    formData.append('model_name', selectedModel);

    fetch('/analyze', {
        method: 'POST',
        body: formData
    })
    // ... existing code ...
});
</script>
```

### 2.2.2 Step 2: TOC Generation (Backend & AI Core)

The Flask server, running `app_enhanced_oldui.py`, receives the POST request at the `/analyze` route. It saves the uploaded PDF and then calls the core AI function `step1_generate_toc` from the `toc_generation_module`.

**📍 Location**: `app_enhanced_oldui.py`

```python
# ... existing code ...
from toc_generation_module.toc_generator import step1_generate_toc
# ... existing code ...
@app.route('/analyze', methods=['POST'])
def analyze():
    # ... file saving logic ...
    lastenboek_path = os.path.join(app.config['UPLOAD_FOLDER'], lastenboek_filename)
    lastenboek_file.save(lastenboek_path)
    
    app.logger.info("Generating TOC from uploaded PDF...")
    try:
        chapters_data, output_dir = step1_generate_toc(
            pdf_path=lastenboek_path,
            output_base_dir=app.config['UPLOAD_FOLDER'],
            model_name=selected_model
        )
    # ... existing code ...
```

The `step1_generate_toc` function then takes over. It loads the PDF, splits it into manageable, overlapping batches of pages, and sends each batch to the Gemini AI model with a carefully crafted prompt.

**📍 Location**: `toc_generation_module/toc_generator.py`

```python
# ... existing code ...
def step1_generate_toc(pdf_path, output_base_dir=None, called_by_orchestrator=False, model_name=None):
    # ... setup and PDF loading logic ...
    
    page_batch_size = 25
    overlap = 3
    # ... batch creation logic ...

    chat = multimodal_model.start_chat(response_validation=False)

    # ... initial prompt for overall structure ...
    
    for batch_idx, (start_page, end_page) in enumerate(page_batches):
        page_prompt = f'''
Find chapters/sections in pages {start_page}-{end_page}.

Look for:
- Chapters: "XX. TITLE" (e.g., "00. ALGEMENE BEPALINGEN")  
- Sections: "XX.YY TITLE" (e.g., "01.10 SECTIETITEL")

Return as Python dict:
chapters = {{"XX": {{"start": X, "end": Y, "title": "TITLE", "sections": {{"XX.YY": {{"start": X, "end": Y, "title": "TITLE"}}}}}}}}
'''
        batch_response = chat.send_message(page_prompt)
        page_batch_dict = post_process_results(batch_response.text)
        # ... logic to merge results from all batches ...

    return page_batch_results, toc_output_dir
```

The `post_process_results` function (which we recently fixed) is crucial here. It intelligently parses the AI's response to extract the structured chapter data, handling different formats like Python dictionaries or JSON.

### 2.2.3 Step 3: Placement Analysis (Backend & Rule-Based Checker)

After the initial TOC is generated and displayed, the user can click the "Run Placement Check" button. This sends a request to the `/run_placement_check` endpoint.

This route retrieves the path to the generated TOC file (`chapters.json`) and passes it to the `analyze_placement_from_file` function from `enhanced_task_checker.py`.

**📍 Location**: `app_enhanced_oldui.py`

```python
# ... existing code ...
from enhanced_task_checker import analyze_placement_from_file
# ... existing code ...
@app.route('/run_placement_check', methods=['POST'])
def run_placement_check():
    # ... logic to get file path and model ...
    
    # The OCR data path is the chapters.json from the TOC generation step
    ocr_data_path = os.path.join(session['output_dir'], 'chapters.json')

    try:
        placement_results = analyze_placement_from_file(
            ocr_data_path=ocr_data_path,
            model_name=selected_model,
            verbose=True
        )
        session['placement_analysis_results'] = placement_results
        return jsonify({'success': True, 'results': placement_results})
    # ... error handling ...
```

Unlike the TOC generation, the placement analysis in `enhanced_task_checker.py` uses a **rule-based approach** for classification. It does not make another LLM call. It reads the full text of each chapter and uses a predefined set of keywords to classify the content.

**📍 Location**: `enhanced_task_checker.py`

```python
# ... existing code ...
class EnhancedTaskChecker:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        # ...
        self.task_patterns = {
            'finishes': {
                'keywords': [
                    r'paint', r'tile', r'flooring', r'ceiling', r'wall finish',
                    r'verf', r'tegels', r'vloerbedekking', r'afwerking'
                ],
                'level': 3
            },
            # ... other categories like 'hvac', 'electrical', etc. ...
        }

    def _classify_content_type(self, content: str, title: str) -> Tuple[str, float]:
        # ... logic to iterate through task_patterns and find keyword matches ...
        
        for category, data in self.task_patterns.items():
            score = 0
            for pattern in data['keywords']:
                matches = len(re.findall(pattern, combined_text))
                score += matches
            # ... logic to determine best match based on score ...
        return best_match, confidence
# ... existing code ...
```

### 2.2.4 Step 4: Final Results Display (Frontend)

The results from the placement analysis are sent back to the browser. The JavaScript in `oldui.html` receives this final, enriched data and dynamically updates the results table, displaying the content type and any identified issues for each chapter.

# 3. USER DOCUMENTATION

This section provides a simple guide for end-users on how to operate the web application.

## 3.1 Running an Analysis

1.  **Launch the Application**: Ensure the Flask server is running. Once started, the application will be accessible in your web browser, typically at `http://127.0.0.1:9000`.
2.  **Upload Document**: On the main page, click the "Choose File" button under "Lastenboek (PDF)" and select the specifications document you wish to analyze. The *Meetstaat* file upload is optional and not required for the primary placement check functionality.
3.  **Select Model**: Choose the desired AI model from the dropdown list. **"Gemini 2.5 Flash"** is recommended for its balance of speed and capability.
4.  **Start Initial Analysis**: Click the **"Analyze Document"** button. The system will now perform the dynamic TOC generation. This may take several minutes for large documents. Once complete, a table containing the generated chapters and sections will appear.
5.  **Run Placement Check**: After the TOC is displayed, the **"Run Placement Check"** button will become active. Click it to initiate the detailed analysis of the document's content.
6.  **Review Results**: The table will update with the results of the placement check. Each chapter will be assigned a "Content Type" (e.g., `finishes`, `electrical`), and any potential issues or suggestions for improvement will be listed.
7.  **Export Results**: You can download the full analysis data by clicking the **"Export Placement Analysis (JSON)"** button.

# 4. CORE FUNCTION REFERENCE

This section provides a reference for the key Python functions and classes that drive the system.

### 4.1 Flask Application (`app_enhanced_oldui.py`)

**📍 Location**: `app_enhanced_oldui.py`

#### 4.1.1 `app.route('/analyze')`
-   **Purpose**: Handles the initial document upload and triggers the TOC generation.
-   **Process**:
    1.  Receives the PDF file from the frontend.
    2.  Saves the file to the `uploads/` directory.
    3.  Calls `step1_generate_toc()` to perform the AI-powered analysis.
    4.  Stores the results in the user's session.
    5.  Returns the generated TOC data to the frontend for display.

#### 4.1.2 `app.route('/run_placement_check')`
-   **Purpose**: Triggers the rule-based content analysis on the generated TOC.
-   **Process**:
    1.  Retrieves the path to the `chapters.json` file created during TOC generation.
    2.  Calls `analyze_placement_from_file()` from the `enhanced_task_checker` module.
    3.  Stores the detailed placement analysis results in the session.
    4.  Returns the results to the frontend to update the UI.

### 4.2 TOC Generation Module (`toc_generator.py`)

**📍 Location**: `toc_generation_module/toc_generator.py`

#### 4.2.1 `step1_generate_toc()`
-   **Purpose**: The core function for generating a Table of Contents from a PDF document.
-   **Process**:
    1.  Initializes a connection to the Vertex AI service with the specified Gemini model.
    2.  Loads the source PDF and splits it into a series of overlapping page batches to manage token limits.
    3.  Initiates a `chat` session with the multimodal model.
    4.  Sends each page batch to the model with a prompt asking it to identify chapter and section headers.
    5.  Calls `post_process_results()` to parse the structured data from the AI's response.
    6.  Merges the results from all batches into a single, coherent TOC.
    7.  Saves the final TOC to a `chapters.json` file.

#### 4.2.2 `post_process_results()`
-   **Purpose**: A robust parsing function designed to extract a Python dictionary from the AI model's text response.
-   **Process**:
    1.  Searches the response for a Python code block (```python...```).
    2.  Attempts to parse the content as a direct dictionary literal.
    3.  If that fails, it attempts to execute the code to find a `chapters` variable.
    4.  As a final fallback, it searches for any JSON-like structure in the text.
    5.  This flexibility is critical for handling minor variations in the LLM's output format.

### 4.3 Enhanced Task Checker (`enhanced_task_checker.py`)

**📍 Location**: `enhanced_task_checker.py`

#### 4.3.1 `analyze_placement_from_file()`
-   **Purpose**: A wrapper function that orchestrates the rule-based analysis of the document's content.
-   **Process**:
    1.  Initializes an `EnhancedTaskChecker` instance with the path to the `chapters.json` file.
    2.  Calls the `analyze_all_sections()` method to perform the classification.
    3.  Calls `generate_summary_format_report()` to structure the results.

#### 4.3.2 `EnhancedTaskChecker._classify_content_type()`
-   **Purpose**: Classifies the content of a chapter based on keyword matching.
-   **Process**:
    1.  It iterates through a predefined dictionary, `self.task_patterns`, which maps categories (e.g., `finishes`, `hvac`) to a list of keywords.
    2.  It scans the text of a chapter for these keywords, calculating a relevance score for each category.
    3.  The category with the highest score is assigned as the chapter's `content_type`. This process does not involve an LLM.

# 5. SETUP & INSTALLATION

This section describes how to set up the local development environment to run the application.

## 5.1 Prerequisites

-   Python 3.8+
-   `pip` and `virtualenv`
-   Google Cloud SDK initialized with a valid project and authentication.

## 5.2 Installation Steps

1.  **Clone the Repository**:
    ```bash
    git clone [repository-url]
    cd Meetstaatincorp
    ```

2.  **Create and Activate a Virtual Environment**:
    ```bash
    python -m venv .venv
    # On Windows
    .venv\Scripts\activate
    # On macOS/Linux
    source .venv/bin/activate
    ```

3.  **Install Dependencies**: The required Python packages are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Google Cloud Authentication**: Ensure your environment is authenticated with Google Cloud using the `gcloud` command-line interface.
    ```bash
    # This command will open a browser to authenticate your user account
    gcloud auth application-default login
    ```
    You will also need to set the `GOOGLE_CLOUD_PROJECT` environment variable to your Google Cloud Project ID.

5.  **Run the Application**:
    ```bash
    python app_enhanced_oldui.py
    ```
    The application will be available at `http://127.0.0.1:9000`.

# 6. LIMITATIONS & FUTURE IMPROVEMENTS

This section provides a transparent overview of the system's current limitations and potential areas for future development.

## 6.1 Current Limitations

-   **Requires Text-Based PDFs**: The system's current analysis pathway relies on extracting text directly from the PDF. It cannot process scanned documents where the text is embedded within images.
-   **TOC Structure Dependency**: The AI model is prompted to look for specific heading formats (e.g., `XX. TITLE`, `XX.YY TITLE`). Documents that use a significantly different numbering or structuring scheme may not be parsed correctly.
-   **Single Document Analysis**: The application is designed to process one *Lastenboek* at a time and does not currently support batch processing.

## 6.2 Future Improvements

-   **Support for Scanned Documents via OCR or Vision**: To handle image-based PDFs, two alternative pathways can be implemented:
    -   **1. OCR Pipeline**: An OCR service (like Google Cloud Vision) could be integrated to first extract the text from scanned pages. This extracted text could then be fed into the existing text-based analysis workflow.
    -   **2. Direct Vision Analysis**: Alternatively, a multimodal vision model (like a future version of Gemini 2.5) could analyze the rendered images of the PDF pages directly. This approach is a powerful alternative as it bypasses the need for a separate OCR step and can also interpret complex layouts, tables, and diagrams that are not pure text.
-   **Adaptive Prompting**: Develop a mechanism for the AI to first identify a document's unique structure and then adapt its own prompts to match the specific heading and numbering format used.
-   **Batch Processing**: Implement a feature to allow users to upload and analyze multiple documents in a single batch job.

# 7. APPENDIX

This appendix contains the full text of the primary AI prompt used for generating the Table of Contents.

## 7.1 AI Prompt for TOC Generation

The following prompt is sent to the Gemini model for each batch of pages to instruct it on how to identify and structure the chapters and sections.

**📍 Location**: `toc_generation_module/toc_generator.py`

```python
page_prompt = f'''
Find chapters/sections in pages {start_page}-{end_page}.

Look for:
- Chapters: "XX. TITLE" (e.g., "00. ALGEMENE BEPALINGEN")  
- Sections: "XX.YY TITLE" (e.g., "01.10 SECTIETITEL")

Return as Python dict:
chapters = {{"XX": {{"start": X, "end": Y, "title": "TITLE", "sections": {{"XX.YY": {{"start": X, "end": Y, "title": "TITLE"}}}}}}}}

Use global PDF page numbers only.
'''
```
