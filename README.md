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

4.  **Google Cloud Authentication:**
    Ensure you are authenticated with the `gcloud` CLI:
    ```bash
    gcloud auth application-default login
    ```

### Running the Application

To start the Flask web server, run the following command:

```bash
python task_placement_analyzer_app.py
```

The application will be available at `http://127.0.0.1:5002`.

## Usage

1.  **Open the web interface** in your browser.
2.  **Select an analysis file** from the dropdown menu. These files are automatically detected from the `ocroutput` directory.
3.  **Click "Start Analyse"** to begin the analysis.
4.  **View the results** in the interactive UI. You can expand and collapse sections, filter by issue category, and view the summary dashboard.

## Project Structure

-   `task_placement_analyzer_app.py`: The main Flask application that runs the web server.
-   `enhanced_task_checker.py`: The core logic for the AI-powered analysis.
-   `Templates/enhanced_ui.html`: The HTML template for the web interface.
-   `requirements.txt`: The list of Python dependencies.
-   `.flake8`: The configuration file for the linter.
-   `ocroutput/`: The directory where the OCR output and analysis files are stored.
-   `legacy/`: Older scripts and documentation.
-   `Basisdocument/`: The template documents that provide the ideal structure for the analysis.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your proposed changes.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.
