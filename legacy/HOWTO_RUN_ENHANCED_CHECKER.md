# How to Run the Enhanced Task Placement Checker

## Quick Start

The enhanced task placement checker uses the full OCR text content to provide much more accurate task placement analysis than the original summary-based approach.

### 1. Basic Run (With Sample Data)

```bash
python enhanced_task_checker.py --verbose
```

This will:
- Load the OCR data from `ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json`
- Use 3 sample tasks for demonstration
- Save results to `placement_analysis.json`
- Show verbose output during processing

### 2. Run With Your Own Task Data

```bash
python enhanced_task_checker.py --task-data your_tasks.json --verbose
```

Your task JSON file should have this format:
```json
[
  {
    "id": "task_001",
    "description": "Install electrical outlets in office areas", 
    "section": "03.01"
  },
  {
    "id": "task_002",
    "description": "Remove existing concrete flooring",
    "section": "02.01"
  }
]
```

### 3. Specify Custom Output File

```bash
python enhanced_task_checker.py --output my_analysis.json --verbose
```

### 4. Use Different OCR Data

```bash
python enhanced_task_checker.py --ocr-data path/to/other/chapters_with_text.json --verbose
```

## Command Line Options

- `--ocr-data PATH`: Path to OCR chapters with text JSON file (default: uses cathlab project data)
- `--task-data PATH`: Path to task data JSON file (optional - uses sample data if not provided)
- `--output PATH`: Output file for results (default: placement_analysis.json)
- `--verbose`: Enable detailed output during processing

## Output

The checker creates a JSON file with:

### Summary
- Total issues found
- Breakdown by severity (high/medium/low)

### Detailed Issues
For each problematic task:
- **Task ID & Description**: What task was analyzed
- **Current Section**: Where it's currently placed
- **Issue Type**: Type of problem detected
  - `misplaced_task`: Task is in wrong section
  - `suboptimal_placement`: Task is okay but could be better placed
  - `uncertain_classification`: Can't determine optimal placement
- **Severity**: high/medium/low
- **Confidence**: 0.0 to 1.0 how confident the analysis is
- **Suggested Sections**: Better placement recommendations
- **Reasoning**: Why the issue was flagged
- **Content Context**: Sample of section content for reference

## What Makes It Better

The enhanced checker uses **full OCR text content** (1,000-10,000+ characters per section) instead of **brief summaries** (100-500 characters), providing:

✅ **Better Context Understanding**: Analyzes complete section content
✅ **More Accurate Classification**: Uses comprehensive text analysis  
✅ **Reduced False Positives**: Better understanding prevents incorrect flagging
✅ **Detailed Recommendations**: Specific suggestions with confidence levels
✅ **Construction Hierarchy Awareness**: Understands 00.xx = General, 01.xx = Admin, etc.

## Example Results

```json
{
  "task_id": "sample_001",
  "task_description": "Install electrical outlets in office areas",
  "current_section": "03.01", 
  "issue_type": "misplaced_task",
  "severity": "medium",
  "confidence": 0.67,
  "suggested_sections": ["04.6"],
  "reasoning": "Task appears misplaced. Better suited for sections with electrical content"
}
```

This shows an electrical task incorrectly placed in section 03.01 (likely structural) when it should be in section 04.6 (electrical systems). 