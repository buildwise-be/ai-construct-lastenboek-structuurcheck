# Meetstaat Inc. - Construction Document Analysis Tool

This tool provides an advanced analysis of construction specification documents (`Lastenboeken`) to identify misplaced tasks and organizational issues. It uses a combination of Optical Character Recognition (OCR) and Google's Gemini AI to provide a deep, contextual understanding of the documents.

[Nederlands](README.md) | [Français](README.fr.md)

## How it Works

The application follows a multi-step process to analyze construction documents:

1.  **OCR Processing:** The process starts with a PDF document, which is run through an OCR pipeline to extract the full text and identify the table of contents.
2.  **AI Analysis:** The full text is then analyzed by a `Generative Language Model` (Google Gemini 1.5 Flash). Unlike traditional methods that rely on keywords, this model understands the context and conceptual relationships between different sections.
3.  **Results UI:** The results are presented in a user-friendly web interface, where you can filter issues by their category and view the details of each issue.

## Features

-   **AI-Powered Analysis:** Leverages Google's Gemini 1.5 Flash model to analyze the full text of construction documents.
-   **Contextual Understanding:** Goes beyond simple keyword matching to understand the conceptual relationships between different sections.
-   **Nuanced Issue Categorization:** Classifies issues into `Critical Misplacement`, `Poor Organization`, and `Suggestion for Improvement` for a more meaningful analysis.
-   **Interactive Web UI:** Provides a user-friendly interface to upload documents, view results, and filter issues.
-   **Summary Dashboard:** Offers a high-level overview of the analysis results, including the total number of issues per category.

## Getting Started

### Prerequisites

-   Python 3.8+
-   Google Cloud SDK (with `gcloud` authenticated)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/buildwise-be/ai-construct-lastenboek-structuurcheck.git
    cd ai-construct-lastenboek-structuurcheck
    ```

2.  **Create a virtual environment and install the dependencies:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    pip install -r requirements.txt
    ```

3.  **Set up your Google Cloud project:**
    Ensure you are logged in with the gcloud CLI and that your project is set:
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_PROJECT_ID
    ```

### Usage

1.  **Start the Flask application:**
    ```bash
    python task_placement_analyzer_app.py
    ```
2.  **Open the web interface:**
    Navigate to `http://127.0.0.1:5000` in your web browser.

3.  **Select and analyze:**
    -   Select an available analysis file from the dropdown menu.
    -   Click "Start Analysis".
    -   The results will appear below once the analysis is complete.

## Contributing

Contributions are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
