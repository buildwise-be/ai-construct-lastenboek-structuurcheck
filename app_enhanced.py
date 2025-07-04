#!/usr/bin/env python3
"""
Enhanced Flask App for Task Placement Analysis using OCR ToC Subdirectory Information

This version uses the enhanced task placement checker with full OCR text content
instead of the traditional summary-based approach.
"""

from flask import Flask, request, jsonify, session, make_response
from flask_session import Session
import os
import logging
import json
import time
import glob
from werkzeug.utils import secure_filename
from datetime import datetime

# Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
DEFAULT_MODEL = "gemini-2.0-flash-001"

# Vertex AI imports
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
    print("Vertex AI libraries not found")

# Allowed file extensions
ALLOWED_EXTENSIONS_JSON = {'json'}

def allowed_file(filename, allowed_extensions):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Initialize Flask app
app = Flask(__name__, instance_relative_config=True)

# Configure logging
app.logger.setLevel(logging.INFO)

# Configure session
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(app.instance_path, 'flask_session')
app.config["SECRET_KEY"] = os.urandom(24)

# Ensure directories exist
try:
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["SESSION_FILE_DIR"], exist_ok=True)
except OSError:
    pass

Session(app)

# Upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Default OCR ToC path - using the correct current path for testing
DEFAULT_OCR_PATH = "ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json"

def get_available_ocr_files():
    """Find available OCR ToC files."""
    available = {}
    
    # Check default path
    if os.path.exists(DEFAULT_OCR_PATH):
        available["cathlab_current"] = DEFAULT_OCR_PATH
        app.logger.info(f"Found default OCR file: {DEFAULT_OCR_PATH}")
    
    # Look for other OCR output files
    ocr_pattern = "ocroutput/*/final_combined_output/chapters_with_text_v3.json"
    for path in glob.glob(ocr_pattern):
        parts = path.split('/')
        if len(parts) >= 2:
            pipeline_name = parts[1].replace('pipeline_run_', '')
            if pipeline_name not in available:
                available[pipeline_name] = path
    
    app.logger.info(f"Total OCR files found: {list(available.keys())}")
    return available

def initialize_vertex_ai():
    """Initialize Vertex AI if available."""
    if not VERTEX_AI_AVAILABLE or not PROJECT_ID:
        app.logger.warning("Vertex AI not available or PROJECT_ID not set")
        return None
    
    try:
        aiplatform.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel(DEFAULT_MODEL)
        app.logger.info("Vertex AI initialized successfully")
        return model
    except Exception as e:
        app.logger.error(f"Failed to initialize Vertex AI: {e}")
        return None

@app.route('/')
def index():
    """Main page with enhanced analysis options."""
    available_files = get_available_ocr_files()
    
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Enhanced Task Placement Checker</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 900px; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        .form-group {{ margin: 20px 0; }}
        label {{ display: block; margin-bottom: 8px; font-weight: bold; color: #34495e; }}
        input, select, button {{ padding: 10px; margin: 5px 0; border: 1px solid #bdc3c7; border-radius: 4px; }}
        button {{ background: #3498db; color: white; border: none; padding: 12px 24px; cursor: pointer; border-radius: 5px; }}
        button:hover {{ background: #2980b9; }}
        .info-box {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .results {{ margin-top: 30px; }}
        .section {{ border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 5px; }}
        .major {{ border-left: 5px solid #e74c3c; background: #fdf2f2; }}
        .minor {{ border-left: 5px solid #f39c12; background: #fef9e7; }}
        .none {{ border-left: 5px solid #27ae60; background: #eafaf1; }}
        .status {{ font-size: 12px; color: #7f8c8d; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Enhanced Task Placement Checker</h1>
        <div class="info-box">
            <strong>Uses OCR ToC subdirectory information with full text content for superior analysis.</strong><br>
            This enhanced version analyzes complete section content (1,000-10,000+ characters) instead of limited summaries,
            providing much more accurate placement detection and detailed recommendations.
        </div>
        
        <form id="analysisForm">
            <div class="form-group">
                <label>Input Source:</label>
                <select name="input_source" id="inputSource" style="width: 300px;">
                    <option value="default">Use Available OCR File</option>
                    <option value="file">Upload OCR JSON File</option>
                </select>
            </div>
            
            <div class="form-group" id="fileUpload" style="display:none;">
                <label>OCR JSON File (chapters_with_text_v3.json):</label>
                <input type="file" name="ocr_file" accept=".json" style="width: 400px;">
            </div>
            
            <div class="form-group">
                <label>Available OCR Files:</label>
                <select name="selected_ocr_file" style="width: 400px;">
                    {chr(10).join([f'<option value="{name}">{name}</option>' for name in available_files.keys()])}
                </select>
            </div>
            
            <div class="form-group">
                <label>Analysis Mode:</label>
                <select name="analysis_mode" style="width: 300px;">
                    <option value="full">Full Text Analysis (Complete Content)</option>
                    <option value="chunked">Chunked Analysis (For Very Long Sections)</option>
                </select>
                <small style="color: #7f8c8d;"> Full text uses complete section content for maximum accuracy</small>
            </div>
            
            <button type="button" onclick="startAnalysis()">Analyze with Enhanced Checker</button>
        </form>
        
        <div id="results" class="results"></div>
        
        <div class="status">
            <strong>Status:</strong> Vertex AI Available: {VERTEX_AI_AVAILABLE} | 
            OCR Files Found: {len(available_files)} | 
            Ready for samengevoegdlastenboek analysis when OCR data is available
        </div>
    </div>
    
    <script>
        document.getElementById('inputSource').addEventListener('change', function() {{
            const fileUpload = document.getElementById('fileUpload');
            fileUpload.style.display = this.value === 'file' ? 'block' : 'none';
        }});
        
        function startAnalysis() {{
            const form = document.getElementById('analysisForm');
            const formData = new FormData(form);
            
            document.getElementById('results').innerHTML = '<p>Analyzing sections with enhanced checker...</p>';
            
            fetch('/analyze_enhanced', {{
                method: 'POST',
                body: formData
            }})
            .then(response => response.json())
            .then(data => {{
                if (data.success) {{
                    displayResults(data);
                }} else {{
                    document.getElementById('results').innerHTML = '<p style="color: #e74c3c;">Error: ' + data.error + '</p>';
                }}
            }})
            .catch(error => {{
                document.getElementById('results').innerHTML = '<p style="color: #e74c3c;">Network Error: ' + error + '</p>';
            }});
        }}
        
        function displayResults(data) {{
            const summary = data.summary;
            const results = data.results;
            
            let html = '<h2>Analysis Results</h2>';
            html += '<div class="info-box">';
            html += '<strong>Summary:</strong> Analyzed ' + summary.analyzed_sections + ' sections in ' + summary.processing_time + ' seconds<br>';
            html += '<strong>Issues Found:</strong> Major(' + summary.issue_counts.major + ') Minor(' + summary.issue_counts.minor + ') None(' + summary.issue_counts.none + ')<br>';
            html += '<strong>Data Source:</strong> ' + summary.data_type + ' (' + summary.input_file + ')';
            html += '</div>';
            
            for (const [code, result] of Object.entries(results)) {{
                if (result.error) {{
                    html += '<div class="section"><strong>' + code + '</strong>: Error - ' + result.error + '</div>';
                    continue;
                }}
                
                const severity = result.assessment?.severity || 'unknown';
                const matches = result.assessment?.content_matches_code || false;
                const summary_text = result.assessment?.content_summary || 'No summary';
                const confidence = result.assessment?.confidence || 'unknown';
                
                html += '<div class="section ' + severity + '">';
                html += '<h3>Section ' + code + '</h3>';
                html += '<p><strong>Matches Expected Content:</strong> ' + matches + '</p>';
                html += '<p><strong>Severity:</strong> ' + severity.toUpperCase() + ' | <strong>Confidence:</strong> ' + confidence.toUpperCase() + '</p>';
                html += '<p><strong>Content Summary:</strong> <em>' + summary_text + '</em></p>';
                
                if (result.assessment?.issues_found?.length > 0) {{
                    html += '<p><strong>Issues Found:</strong> ' + result.assessment.issues_found.join('; ') + '</p>';
                }}
                
                if (result.recommendations && result.recommendations !== 'None needed') {{
                    html += '<p><strong>Recommendations:</strong> ' + result.recommendations + '</p>';
                }}
                html += '</div>';
            }}
            
            html += '<div style="margin-top: 20px;"><button onclick="exportResults()">Export Results</button></div>';
            
            document.getElementById('results').innerHTML = html;
        }}
        
        function exportResults() {{
            window.open('/export_enhanced_json', '_blank');
        }}
    </script>
</body>
</html>
    """

def load_ocr_data(file_path):
    """Load OCR chapters data from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        app.logger.info(f"Loaded {len(data)} chapters from {file_path}")
        return data
    except Exception as e:
        app.logger.error(f"Failed to load OCR data from {file_path}: {e}")
        return None

def extract_sections_for_analysis(ocr_data, use_full_text=True):
    """Extract sections suitable for analysis with full text content."""
    sections = []
    
    for code, data in ocr_data.items():
        if not isinstance(data, dict):
            continue
            
        title = data.get('title', '')
        text = data.get('text', '')
        char_count = data.get('character_count', len(text))
        
        # Only filter out very short or empty sections
        if char_count < 100 or not title:
            continue
            
        section = {
            'code': code,
            'title': title,
            'text': text,  # Use FULL text content
            'char_count': char_count,
            'start_page': data.get('start_page', data.get('start', 0)),
            'end_page': data.get('end_page', data.get('end', 0)),
            'token_estimate': len(text) // 4  # Rough token estimate (4 chars per token)
        }
        sections.append(section)
    
    return sections

def chunk_text(text, max_chunk_tokens=12000):
    """Split very long text into manageable chunks."""
    # Rough estimate: 4 characters per token
    max_chars = max_chunk_tokens * 4
    
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(text):
        # Find a good break point (paragraph, sentence, or space)
        end_pos = min(current_pos + max_chars, len(text))
        
        if end_pos < len(text):
            # Look for paragraph break
            paragraph_break = text.rfind('\n\n', current_pos, end_pos)
            if paragraph_break > current_pos + max_chars // 2:
                end_pos = paragraph_break
            else:
                # Look for sentence break
                sentence_break = text.rfind('. ', current_pos, end_pos)
                if sentence_break > current_pos + max_chars // 2:
                    end_pos = sentence_break + 1
                else:
                    # Look for space
                    space_break = text.rfind(' ', current_pos, end_pos)
                    if space_break > current_pos + max_chars // 2:
                        end_pos = space_break
        
        chunk = text[current_pos:end_pos].strip()
        if chunk:
            chunks.append(chunk)
        
        current_pos = end_pos
    
    return chunks

def analyze_section_placement(section, model, analysis_mode='full'):
    """Analyze a single section's placement using the enhanced approach with full text."""
    
    text_content = section['text']
    token_estimate = section.get('token_estimate', len(text_content) // 4)
    
    # For very long sections, use chunking if requested
    if analysis_mode == 'chunked' and token_estimate > 15000:
        return analyze_section_with_chunking(section, model)
    
    # Use full text content (up to model limits)
    max_content_length = 50000  # About 12K tokens worth of characters
    if len(text_content) > max_content_length:
        app.logger.info(f"Section {section['code']} is very long ({len(text_content)} chars), using first {max_content_length} chars")
        text_content = text_content[:max_content_length] + "\n\n[Content continues beyond analysis limit...]"
    
    prompt = f"""You are analyzing construction specifications for task placement accuracy using COMPLETE section content.

Construction specification hierarchy:
- 00.xx: General provisions
- 01.xx: Administrative/General requirements
- 02.xx: Existing conditions, Site work
- 03.xx: Concrete
- 04.xx: Masonry, Finishes
- 05.xx: Metals
- 06.xx: Wood/Plastics
- 07.xx: Thermal/Moisture protection
- 08.xx: Openings (doors/windows)
- 09.xx: Finishes
- 10.xx: Specialties

Analyze if this content matches the expected section hierarchy. You have the FULL section content:

Section: {section['code']}
Title: {section['title']}
Character Count: {section['char_count']}
Pages: {section.get('start_page', 'N/A')} - {section.get('end_page', 'N/A')}

COMPLETE SECTION CONTENT:
{text_content}

Analyze the ENTIRE content above and return JSON:
{{
  "code": "{section['code']}",
  "assessment": {{
    "content_matches_code": true/false,
    "content_summary": "comprehensive summary of what the content covers",
    "expected_content": "what should be in this section type",
    "issues_found": ["detailed list of specific issues"],
    "severity": "none|minor|major",
    "confidence": "low|medium|high",
    "content_analysis": "detailed analysis of the content quality and placement"
  }},
  "recommendations": "specific actionable recommendations or 'None needed'",
  "content_stats": {{
    "analyzed_chars": {len(text_content)},
    "is_complete": {"true" if len(text_content) == len(section['text']) else "false"}
  }}
}}"""

    try:
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.8,
                "max_output_tokens": 3072,  # Increased for more detailed analysis
                "response_mime_type": "application/json"
            }
        )
        
        if response and response.candidates:
            response_text = response.candidates[0].content.parts[0].text
            result = json.loads(response_text.strip())
            return result
            
    except Exception as e:
        app.logger.error(f"Error analyzing section {section['code']}: {e}")
        return {
            'code': section['code'],
            'error': str(e),
            'section_stats': {
                'char_count': section['char_count'],
                'token_estimate': token_estimate
            }
        }

def analyze_section_with_chunking(section, model):
    """Analyze very long sections using multiple chunks."""
    
    text_content = section['text']
    chunks = chunk_text(text_content, max_chunk_tokens=12000)
    
    app.logger.info(f"Section {section['code']} split into {len(chunks)} chunks for analysis")
    
    chunk_results = []
    
    for i, chunk in enumerate(chunks):
        chunk_prompt = f"""Analyze this chunk ({i+1}/{len(chunks)}) of section {section['code']}:

Section: {section['code']} - Part {i+1}/{len(chunks)}
Title: {section['title']}

CHUNK CONTENT:
{chunk}

Return JSON with partial analysis:
{{
  "chunk_number": {i+1},
  "total_chunks": {len(chunks)},
  "content_summary": "what this chunk covers",
  "issues_found": ["issues in this chunk"],
  "relevant_content": "key content relevant to section classification"
}}"""

        try:
            response = model.generate_content(
                chunk_prompt,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "max_output_tokens": 2048,
                    "response_mime_type": "application/json"
                }
            )
            
            if response and response.candidates:
                chunk_result = json.loads(response.candidates[0].content.parts[0].text.strip())
                chunk_results.append(chunk_result)
                
        except Exception as e:
            app.logger.error(f"Error analyzing chunk {i+1} of section {section['code']}: {e}")
            chunk_results.append({
                "chunk_number": i+1,
                "error": str(e)
            })
        
        time.sleep(0.5)  # Small delay between chunk analyses
    
    # Combine chunk results into final assessment
    return combine_chunk_results(section, chunk_results, model)

def combine_chunk_results(section, chunk_results, model):
    """Combine multiple chunk analyses into a single assessment."""
    
    # Summarize all chunk findings
    chunk_summaries = []
    all_issues = []
    
    for chunk_result in chunk_results:
        if 'error' not in chunk_result:
            chunk_summaries.append(f"Chunk {chunk_result.get('chunk_number', '?')}: {chunk_result.get('content_summary', 'No summary')}")
            chunk_issues = chunk_result.get('issues_found', [])
            all_issues.extend(chunk_issues)
    
    # Create final assessment prompt
    final_prompt = f"""Based on analysis of {len(chunk_results)} chunks of section {section['code']}, provide final assessment:

Section: {section['code']}
Title: {section['title']}
Total Character Count: {section['char_count']}

CHUNK SUMMARIES:
{chr(10).join(chunk_summaries)}

ALL ISSUES FOUND:
{chr(10).join([f"- {issue}" for issue in all_issues])}

Provide final comprehensive assessment:
{{
  "code": "{section['code']}",
  "assessment": {{
    "content_matches_code": true/false,
    "content_summary": "comprehensive summary based on all chunks",
    "expected_content": "what should be in this section type",
    "issues_found": ["consolidated list of issues"],
    "severity": "none|minor|major",
    "confidence": "low|medium|high",
    "content_analysis": "overall analysis based on complete content review"
  }},
  "recommendations": "specific recommendations based on full content analysis",
  "content_stats": {{
    "analyzed_chars": {section['char_count']},
    "chunks_analyzed": {len(chunk_results)},
    "is_complete": true
  }}
}}"""

    try:
        response = model.generate_content(
            final_prompt,
            generation_config={
                "temperature": 0.2,
                "top_p": 0.8,
                "max_output_tokens": 3072,
                "response_mime_type": "application/json"
            }
        )
        
        if response and response.candidates:
            return json.loads(response.candidates[0].content.parts[0].text.strip())
            
    except Exception as e:
        app.logger.error(f"Error combining chunk results for section {section['code']}: {e}")
        
    # Fallback result if combination fails
    return {
        'code': section['code'],
        'assessment': {
            'content_matches_code': None,
            'content_summary': f"Analyzed {len(chunk_results)} chunks, combination failed",
            'issues_found': all_issues[:10],  # Limit to first 10 issues
            'severity': 'unknown',
            'confidence': 'low'
        },
        'recommendations': 'Manual review required due to analysis complexity',
        'content_stats': {
            'analyzed_chars': section['char_count'],
            'chunks_analyzed': len(chunk_results),
            'error': 'Chunk combination failed'
        }
    }

@app.route('/analyze_enhanced', methods=['POST'])
def analyze_enhanced():
    """Enhanced analysis using OCR ToC subdirectory information."""
    
    # Get input source
    input_source = request.form.get('input_source', 'default')
    ocr_file_path = None
    
    if input_source == 'file' and 'ocr_file' in request.files:
        # Handle uploaded file
        ocr_file = request.files['ocr_file']
        if ocr_file.filename != '' and allowed_file(ocr_file.filename, ALLOWED_EXTENSIONS_JSON):
            filename = secure_filename(ocr_file.filename)
            ocr_file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            ocr_file.save(ocr_file_path)
            app.logger.info(f"Saved OCR file to: {ocr_file_path}")
    
    if not ocr_file_path:
        # Use selected default file
        selected_file = request.form.get('selected_ocr_file')
        available_files = get_available_ocr_files()
        
        if selected_file in available_files:
            ocr_file_path = available_files[selected_file]
        else:
            ocr_file_path = DEFAULT_OCR_PATH
        
        app.logger.info(f"Using OCR file: {ocr_file_path}")
    
    # Get analysis parameters
    analysis_mode = request.form.get('analysis_mode', 'full')
    
    try:
        # Initialize Vertex AI
        model = initialize_vertex_ai()
        if not model:
            return jsonify({'error': 'Vertex AI not available. Please check GOOGLE_CLOUD_PROJECT environment variable.'}), 500
        
        # Load OCR data
        app.logger.info(f"Loading OCR data from: {ocr_file_path}")
        ocr_data = load_ocr_data(ocr_file_path)
        
        if not ocr_data:
            return jsonify({'error': 'Failed to load OCR data. Check file path and format.'}), 500
        
        # Extract analyzable sections with full text
        sections = extract_sections_for_analysis(ocr_data, use_full_text=True)
        app.logger.info(f"Extracted {len(sections)} analyzable sections")
        
        if not sections:
            return jsonify({'error': 'No analyzable sections found in OCR data.'}), 400
        
        # Process sections (limit to first 5 for demo)
        start_time = time.time()
        results = {}
        
        # Process more sections since we have full text analysis
        num_sections_to_analyze = 10 if analysis_mode == 'full' else 5
        
        for i, section in enumerate(sections[:num_sections_to_analyze]):
            app.logger.info(f"Analyzing section {i+1}/{num_sections_to_analyze}: {section['code']} ({section['char_count']} chars)")
            result = analyze_section_placement(section, model, analysis_mode)
            results[section['code']] = result
            time.sleep(1)  # Small delay between requests
        
        processing_time = time.time() - start_time
        
        # Count issues
        issue_counts = {
            'major': 0,
            'minor': 0,
            'none': 0,
            'total': len(results)
        }
        
        for result in results.values():
            if 'error' in result:
                continue
            severity = result.get('assessment', {}).get('severity', 'unknown')
            if severity in issue_counts:
                issue_counts[severity] += 1
        
        # Prepare response
        analysis_summary = {
            'total_sections': len(sections),
            'analyzed_sections': len(results),
            'processing_time': round(processing_time, 2),
            'issue_counts': issue_counts,
            'input_file': os.path.basename(ocr_file_path),
            'analysis_date': datetime.now().isoformat(),
            'data_type': 'ocr_full_text'
        }
        
        # Store in session for export
        session['enhanced_results'] = {
            'results': results,
            'summary': analysis_summary,
            'sections': sections[:num_sections_to_analyze],
            'analysis_mode': analysis_mode
        }
        
        app.logger.info(f"Enhanced analysis complete: {len(results)} sections analyzed in {processing_time:.2f}s")
        
        return jsonify({
            'success': True,
            'summary': analysis_summary,
            'results': results
        })
        
    except Exception as e:
        app.logger.error(f"Error in enhanced analysis: {e}")
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500

@app.route('/export_enhanced_json')
def export_enhanced_json():
    """Export enhanced analysis results as JSON."""
    
    if 'enhanced_results' not in session:
        return jsonify({'error': 'No analysis results to export'}), 404
    
    results_data = session['enhanced_results']
    
    # Create export data
    export_data = {
        'metadata': {
            'export_date': datetime.now().isoformat(),
            'analysis_type': 'enhanced_task_placement',
            'data_source': 'ocr_full_text',
            'app_version': 'enhanced_app_v1.0'
        },
        'summary': results_data['summary'],
        'results': results_data['results']
    }
    
    # Create response
    response = make_response(json.dumps(export_data, indent=2, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = f'attachment; filename=enhanced_analysis_{int(time.time())}.json'
    
    return response

@app.route('/health')
def health():
    """Health check endpoint."""
    
    status = {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'components': {
            'vertex_ai': VERTEX_AI_AVAILABLE,
            'available_ocr_files': len(get_available_ocr_files()),
            'default_ocr_path': DEFAULT_OCR_PATH,
            'default_ocr_exists': os.path.exists(DEFAULT_OCR_PATH)
        }
    }
    
    return jsonify(status)

if __name__ == '__main__':
    app.logger.info("Starting Enhanced Task Placement Analysis App")
    app.logger.info(f"Vertex AI available: {VERTEX_AI_AVAILABLE}")
    app.logger.info(f"Available OCR files: {list(get_available_ocr_files().keys())}")
    app.logger.info(f"Default OCR path: {DEFAULT_OCR_PATH}")
    app.logger.info(f"Starting server on http://localhost:5001")
    
    app.run(debug=True, host='0.0.0.0', port=5001)
 