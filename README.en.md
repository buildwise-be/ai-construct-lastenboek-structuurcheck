# Meetstaat Inc. - Construction Document Analysis Tool

![Demonstration of the tool in action](Requirements/GIF/Minidemosplit.gif)

This tool provides an advanced analysis of construction specification documents (`Lastenboeken`) to identify misplaced tasks and organizational issues. It uses a combination of Optical Character Recognition (OCR) and Google's Gemini AI to provide a deep, contextual understanding of the documents.

## How it Works

The application follows a multi-step process to analyze construction documents:

1.  **OCR Processing:** The process starts with a PDF document, which is run through an OCR pipeline to extract the full text and identify the table of contents.
2.  **AI-Powered Analysis:** The extracted text is then sent to Google's Gemini 2.5 Flash model, which analyzes each section for misplaced tasks and organizational issues.
3.  **Interactive UI:** The results are presented in a user-friendly web interface where you can review the analysis, filter by issue category, and get a high-level overview from the summary dashboard.

## Features

-   **AI-Powered Analysis:** Leverages Google's Gemini 2.5 Flash model to analyze the full text of construction documents.
-   **Contextual Understanding:** Goes beyond simple keyword matching to understand the conceptual relationships between different sections.
-   **Nuanced Issue Categorization:** Classifies issues into `Critical Misplacement`, `Poor Organization`, and `Suggestion for Improvement` for a more meaningful analysis.
-   **Interactive Web UI:** Provides a user-friendly interface to upload documents, view results, and filter issues.
-   **Summary Dashboard:** Offers a high-level overview of the analysis results with key metrics.

## Getting Started

### Prerequisites

-   Python 3.8+
-   `pip` for package management
-   Google Cloud SDK (`gcloud`) installed and authenticated

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