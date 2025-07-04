# Table of Contents (TOC) Generation Module

This module is responsible for generating a hierarchical table of contents from a PDF document using Google's Vertex AI (Gemini models).

## 1. Setup

### Prerequisites
- Python 3.x
- A Google Cloud Platform (GCP) project with the Vertex AI API enabled.

### Installation
1.  **Install Python dependencies:**
    Open a terminal in this directory and run:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configure GCP Authentication:**
    Ensure your environment is authenticated with Google Cloud. The recommended way is to use the gcloud CLI:
    ```bash
    gcloud auth application-default login
    ```

3.  **Set Environment Variable:**
    The script requires the `GOOGLE_CLOUD_PROJECT` environment variable to be set to your GCP project ID.

    **Windows (Command Prompt):**
    ```cmd
    set GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    ```

    **Windows (PowerShell):**
    ```powershell
    $env:GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    ```

    **Linux/macOS:**
    ```bash
    export GOOGLE_CLOUD_PROJECT="your-gcp-project-id"
    ```
    Replace `"your-gcp-project-id"` with your actual project ID.

## 2. Usage

You can run the script from the command line.

### Basic Usage
To process a PDF file, provide the path to the file as an argument.

```bash
python toc_generator.py "path/to/your/document.pdf"
```

### Options
-   `--model {pro|flash}`: Choose the Gemini model. `pro` is for high accuracy (default), and `flash` is for speed.
-   `-o, --output-base-dir <directory>`: Specify a directory to save the output files. By default, it saves to an `output/` folder.

### Examples

**Run with the default (pro) model:**
```bash
python toc_generator.py "C:/path/to/my_report.pdf"
```

**Run with the faster (flash) model and a custom output directory:**
```bash
python toc_generator.py "my_report.pdf" --model flash -o "toc_results"
```

## 3. Output
The script generates two primary files in the output directory:

-   `chapters.json`: A machine-readable JSON file containing the hierarchical structure of the table of contents, including titles, levels, and page numbers.
-   `toc_report.md`: A human-readable Markdown file summarizing the generated table of contents. 