# Meetstaat Inc. - Construction Document Analysis Tool

<p align="center">
  <img src="assets/BWlogo.png" alt="Buildwise Logo" width="200"/>
</p>

Welcome to the **AI-Construct Structure Checker**, an advanced tool designed to analyze the structural integrity of construction specification documents (`Lastenboeken`). This locally hosted web application allows you to upload any PDF document and receive an in-depth, AI-driven analysis of task placement and overall organization. The goal is to identify potential inconsistencies, omissions, and misplacements before they become costly problems on the construction site.

## How it Works

The application combines the power of advanced OCR with the reasoning capabilities of Large Language Models (LLMs) to provide a seamless analysis experience:

1.  **PDF Processing with LlamaParse:** When you upload a PDF, it is first processed by LlamaParse. This powerful engine not only extracts the raw text but also reconstructs the full hierarchical structure of the document, including chapters, sections, and subsections.
2.  **AI-Powered Analysis:** The structured output from LlamaParse is then sent in batches to Google's `gemini-2.5-flash` model. The model analyzes each section in the context of the entire document to determine if the tasks and specifications are logically placed.
3.  **Interactive UI:** The analysis results are presented in a clear and interactive web interface. Here, you can easily navigate the document structure, review the AI's findings, filter by issue category, and get a high-level overview from the summary dashboard.

## How to Use

Using the tool is designed to be simple and intuitive:

1.  **Start the Application:** After following the installation steps, start the local web server. The tool is now accessible in your browser.
2.  **Upload a PDF:** The interface provides a clear option to select and upload a `lastenboek` in PDF format from your computer.
3.  **Wait for Processing:** LlamaParse will analyze your document. The progress is visible in the interface, and the process typically takes a few minutes, depending on the document's size.
4.  **Start the Analysis:** Once processing is complete, the file will become available in a dropdown menu. Select it and click "Start Analysis" to let the AI do its work.
5.  **View the Results:** The findings are displayed directly on the page. You can click through the chapters, read the AI's specific comments, and assess the severity of the identified issues.

## Technical Details

This tool uses advanced technologies to provide an in-depth analysis:

-   **OCR and Document Structuring:** We use **LlamaParse** for Optical Character Recognition (OCR) and document structuring. OCR is the process of converting text from images or scanned documents into machine-readable text. LlamaParse not only extracts the text but also the hierarchical structure (chapters, sections) of the document, which is essential for a contextual analysis.
-   **Structural Analysis:** For the actual analysis of the document structure, we use **batched calls to Google's `gemini-2.5-flash` model**. By analyzing multiple sections at once, the model can better understand the context of the entire document and significantly speed up the analysis. An example of the structured JSON file used as input for this step can be found in `examples/example_anonymized_specification.json`.
-   **Data Privacy (GDPR):** All AI models are called via Google Cloud's **Vertex AI** service, running on a **Belgian server (`europe-west1`)**. This ensures full compliance with GDPR regulations, as your data does not leave the EU.

## Getting Started

### Prerequisites

-   Python 3.8+
-   `pip` for package management
-   Google Cloud SDK (`gcloud`) installed and authenticated. You must be logged in via `gcloud auth application-default login`.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd Meetstaatincorp
    ```

2.  **Set up a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\\Scripts\\activate`
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set Environment Variables:**
    This project requires API keys for Google Cloud and LlamaParse. The recommended way to set them is through environment variables.

    **For LlamaParse:**
    Set the `LLAMA_CLOUD_API_KEY` environment variable to your key. For Conda environments, you can set this permanently:
    ```bash
    conda env config vars set LLAMA_CLOUD_API_KEY="your_llama_cloud_api_key"
    ```
    Alternatively, for local development, you can create a `.env` file in the root of the project and add the key there:
    ```
    LLAMA_CLOUD_API_KEY="your_llama_cloud_api_key"
    ```

5.  **Google Cloud Authentication:**
    Ensure you are authenticated with the `gcloud` CLI:
    ```bash
    gcloud auth application-default login
    ```

### Running the Application

To start the Flask web server, run the following command:

```bash
python task_placement_analyzer_app.py
```

The application will be available at `http://1227.0.0.1:5002`.

## Screenshot

![Screenshot of the tool](assets/Screenshot%202025-08-29%20172735.png)
