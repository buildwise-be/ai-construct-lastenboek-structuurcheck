# === Enhanced Placement Checker Application ===
# This application is a simplified Flask server dedicated to running the
# enhanced task placement analysis. It uses the full-text content from
# the latest OCR output to provide a more accurate analysis.
# ===============================================

from flask import Flask, render_template, request, jsonify, session, make_response
from flask_session import Session
import os
import logging
import json
import glob

# Import the enhanced checker function
from enhanced_task_checker import analyze_placement_from_file as run_enhanced_placement_analysis

app = Flask(__name__, instance_relative_config=True)
app.logger.setLevel(logging.INFO)

# --- Configure Flask-Session ---
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, 'flask_session_enhanced')  # Use a separate session dir
app.config["SECRET_KEY"] = os.urandom(24)

try:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
except OSError:
    pass

Session(app)
# --------------------------------


def get_available_analysis_files():
    """Scans the output directory and returns a list of available analysis files."""
    try:
        search_pattern = os.path.join('ocroutput', '*', 'final_combined_output', 'chapters_with_text_v3.json')
        found_files = glob.glob(search_pattern)
        # Return just the filenames, not the full path, for the user to select
        return [os.path.basename(os.path.dirname(os.path.dirname(f))) for f in found_files]
    except Exception as e:
        app.logger.error(f"Error scanning for analysis files: {e}")
        return []


@app.route('/get_analysis_files', methods=['GET'])
def list_analysis_files():
    """API endpoint to get a list of available analysis file identifiers."""
    files = get_available_analysis_files()
    return jsonify(files)


def get_latest_enhanced_toc_path():
    """Finds the most recent 'chapters_with_text_v3.json' file in the output directories."""
    try:
        search_pattern = os.path.join('ocroutput', '*', 'final_combined_output', 'chapters_with_text_v3.json')
        found_files = glob.glob(search_pattern)

        if not found_files:
            app.logger.error(
                "No enhanced TOC file ('chapters_with_text_v3.json') found using pattern: %s", search_pattern
            )
            return None

        latest_file = max(found_files, key=os.path.getctime)
        app.logger.info(f"Found latest enhanced TOC file: {latest_file}")
        return latest_file
    except Exception as e:
        app.logger.error(f"Error while searching for TOC file: {e}")
        return None


def run_placement_analysis(json_path):
    """Runs the enhanced task placement analysis on a given JSON file."""
    try:
        app.logger.info(f"Starting enhanced placement analysis for {json_path}")

        # --- Unset credentials env var to ensure gcloud auth is used ---
        original_creds = os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
        if original_creds:
            app.logger.info("Temporarily unsetting GOOGLE_APPLICATION_CREDENTIALS to use gcloud auth.")
        # --------------------------------------------------------------

        # --- Vertex AI configuration ---
        project_id = "aico25"
        location = "europe-west1"
        model_name = "gemini-1.5-flash"
        # -----------------------------

        analysis_results = run_enhanced_placement_analysis(
            ocr_data_path=json_path,
            project_id=project_id,
            location=location,
            model_name=model_name,
            verbose=True
        )
        app.logger.info("Enhanced placement analysis completed.")
        return analysis_results
    except Exception as e:
        app.logger.error(f"An error occurred during enhanced placement analysis: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        # --- Restore credentials env var if it was originally set ---
        if original_creds:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = original_creds
            app.logger.info("Restored GOOGLE_APPLICATION_CREDENTIALS.")
        # ---------------------------------------------------------


@app.route('/')
def index():
    """Route for the main page - serves the enhanced UI."""
    session.clear()
    app.logger.info("Session cleared for new visit.")
    return render_template('enhanced_ui.html')


@app.route('/analyze', methods=['POST'])
def analyze():
    """Handles initiating the ENHANCED PLACEMENT ANALYSIS on a selected file."""
    session.clear()
    app.logger.info("Cleared session for new analysis request.")

    selected_file_id = request.form.get('analysis_file')
    if not selected_file_id:
        return jsonify({"error": "No analysis file selected."}), 400

    # Construct the full path from the selected file identifier
    toc_path = os.path.join(
        'ocroutput', selected_file_id, 'final_combined_output', 'chapters_with_text_v3.json'
    )

    if not os.path.exists(toc_path):
        app.logger.error("Selected analysis file does not exist at path: %s", toc_path)
        return jsonify({"error": f"Selected analysis file not found on server: {selected_file_id}"}), 404

    session['toc_path'] = toc_path

    try:
        analysis_results = run_placement_analysis(toc_path)
        session['enhanced_analysis_results'] = analysis_results

        issue_count = 0
        if isinstance(analysis_results, list):
            issue_count = sum(len(chapter.get('analysis', {}).get('issues_found', [])) for chapter in analysis_results if isinstance(chapter, dict))

        return jsonify({
            "message": "Analyse voltooid. {} mogelijke problemen gevonden.".format(issue_count),
            "status": "complete",
            "issue_count": issue_count
        })

    except Exception as e:
        app.logger.error(f"An error occurred during enhanced analysis: {e}", exc_info=True)
        return jsonify({"error": f"An unexpected error occurred during analysis: {e}"}), 500


@app.route('/get_enhanced_results', methods=['GET'])
def get_enhanced_results():
    """Returns the stored enhanced analysis results from the session."""
    results = session.get('enhanced_analysis_results')
    if results:
        if isinstance(results, dict) and 'error' in results:
            return jsonify({"error": "Analysis failed: {}".format(results['error'])}), 500

        app.logger.info("Returning enhanced results.")
        return jsonify(results)
    else:
        return jsonify({"error": "No analysis results found in session. Please run an analysis first."}), 404


@app.route('/export_enhanced_json')
def export_enhanced_json():
    """Exports the full enhanced analysis results as a JSON file."""
    results = session.get('enhanced_analysis_results')
    if not results:
        return "No results to export. Please run an analysis first.", 404

    response = make_response(json.dumps(results, indent=4, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    original_filename = os.path.basename(session.get('toc_path', 'analysis.json'))
    new_filename = f"placement_analysis_{original_filename}"
    response.headers['Content-Disposition'] = f'attachment; filename="{new_filename}"'

    app.logger.info(f"Exporting enhanced analysis results to {new_filename}")
    return response


if __name__ == '__main__':
    # Running on a different port to avoid conflict with the main app.py
    # Using 'stat' reloader to prevent issues with watchdog on Windows
    app.run(debug=True, port=5002, reloader_type='stat') 