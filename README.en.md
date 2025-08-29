# Meetstaat Inc. - Construction Document Analysis Tool

![Screenshot of the tool](Requirements/Screenshot%202025-08-29%20172735.png)

<p align="center">
  <img src="Requirements/BWlogo.png" alt="Buildwise Logo" width="200"/>
</p>

This tool provides an advanced analysis of construction specification documents (`Lastenboeken`) to identify misplaced tasks and organizational issues. It is a locally hosted web application that can process any PDF `lastenboek` and present the results in an interactive interface.

## How it Works

The application follows a multi-step process to analyze construction documents:

1.  **PDF Processing with LlamaParse:** The process starts with a PDF document, which is run through the LlamaParse pipeline to extract the full text and identify the document structure.
2.  **AI-Powered Analysis:** The structured text is then sent to Google's `gemini-2.5-flash` model, which analyzes each section for misplaced tasks and organizational issues.
3.  **Interactive UI:** The results are presented in a user-friendly web interface where you can review the analysis, filter by issue category, and get a high-level overview from the summary dashboard.

## How to Use

1.  **Start the Application:** Follow the installation steps below and start the web server. The tool runs locally on your machine.
2.  **Upload a PDF:** Open the web interface and upload any `lastenboek` in PDF format.
3.  **Wait for Processing:** The tool will process the PDF with LlamaParse. This may take a few minutes.
4.  **Start the Analysis:** Once processing is complete, your file will appear in the list. Select it and start the analysis.
5.  **View the Results:** The results are displayed directly in the tool, with an overview of potential issues, categorized for clarity.

## Technical Details

This tool uses advanced technologies to provide an in-depth analysis:

-   **OCR and Document Structuring:** We use **LlamaParse** for Optical Character Recognition (OCR) and document structuring. OCR is the process of converting text from images or scanned documents into machine-readable text. LlamaParse not only extracts the text but also the hierarchical structure (chapters, sections) of the document.
-   **Structural Analysis:** For the actual analysis of the document structure, we use **batched calls to Google's `gemini-2.5-flash` model**. By analyzing multiple sections at once, we can better understand the context of the entire document and speed up the analysis.
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

```