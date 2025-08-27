#!/usr/bin/env python3
"""
Enhanced Task Placement Checker using Full OCR Text Content - Updated to Mirror Summary Format

This script analyzes task placement using the full text content from OCR output,
providing much more accurate and detailed analysis than summary-based approaches.
Now outputs in the same format as the vision-based approach.

Usage:
    python enhanced_task_checker.py [options]

Options:
    --ocr-data PATH     Path to OCR chapters with text JSON file
    --task-data PATH    Path to task data (JSON or CSV)
    --output PATH       Output file for results (default: enhanced_placement_analysis.json)
    --verbose          Enable verbose output
"""

import json
import argparse
import sys
import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import re

# --- Vertex AI Imports ---
try:
    from google.cloud import aiplatform
    from vertexai.generative_models import GenerativeModel
    import google.auth
    VERTEX_AI_AVAILABLE = True
except ImportError:
    VERTEX_AI_AVAILABLE = False
# -------------------------

@dataclass
class EnhancedSectionAnalysis:
    """Enhanced section analysis with summary format"""
    level: int
    title: str
    start_page: int
    end_page: int
    summary: str
    section_id: str
    content_type: str
    confidence: float
    issues: List[str]
    suggested_improvements: List[str]

class EnhancedTaskChecker:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        """Initialize with full OCR text content"""
        self.verbose = verbose
        self.chapters = self._load_ocr_data(ocr_data_path)
        self.section_index = self._build_section_index()
        
        # This will be replaced by LLM analysis, but we can keep it for reference or fallback.
        # Enhanced task classification patterns
        self.task_patterns = {
            'administrative': {
                'keywords': [
                    r'permit', r'license', r'approval', r'documentation', r'contract',
                    r'admin', r'legal', r'insurance', r'safety plan', r'coordination',
                    r'voorschrift', r'vergunning', r'goedkeuring', r'documentatie'
                ],
                'level': 1
            },
            'demolition': {
                'keywords': [
                    r'demolit', r'remove', r'strip', r'break out', r'clear',
                    r'dismantle', r'tear down', r'opbreken', r'slopen', r'verwijderen'
                ],
                'level': 2
            },
            'structural': {
                'keywords': [
                    r'concrete', r'steel', r'beam', r'column', r'foundation',
                    r'structural', r'reinforc', r'load bearing', r'beton', r'staal',
                    r'funderingen'
                ],
                'level': 2
            },
            'hvac': {
                'keywords': [
                    r'heating', r'ventilation', r'air conditioning', r'hvac',
                    r'ductwork', r'climate', r'temperature control', r'verwarming',
                    r'ventilatie', r'klimaat'
                ],
                'level': 3
            },
            'electrical': {
                'keywords': [
                    r'electrical', r'wiring', r'power', r'lighting', r'outlet',
                    r'circuit', r'panel', r'voltage', r'elektrisch', r'bedrading',
                    r'verlichting'
                ],
                'level': 3
            },
            'plumbing': {
                'keywords': [
                    r'plumbing', r'water', r'drain', r'pipe', r'faucet',
                    r'toilet', r'sink', r'sewer', r'sanitair', r'riolering',
                    r'leidingen'
                ],
                'level': 3
            },
            'finishes': {
                'keywords': [
                    r'paint', r'tile', r'flooring', r'ceiling', r'wall finish',
                    r'carpet', r'trim', r'molding', r'verf', r'tegels',
                    r'vloerbedekking', r'afwerking'
                ],
                'level': 3
            }
        }

    def _load_ocr_data(self, data_path: str) -> List[Dict]:
        """Load and validate OCR chapter data"""
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"OCR data file not found: {data_path}")
        
        with open(data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        # Convert dictionary format to list format
        if isinstance(raw_data, dict):
            data = []
            for chapter_num, chapter_info in raw_data.items():
                chapter_data = {
                    'chapter_number': chapter_num,
                    'title': chapter_info.get('title', ''),
                    'full_text': chapter_info.get('text', ''),
                    'content': chapter_info.get('text', ''),  # fallback
                    'start_page': chapter_info.get('start_page', 1),
                    'end_page': chapter_info.get('end_page', 1),
                    'character_count': chapter_info.get('character_count', 0)
                }
                data.append(chapter_data)
        else:
            data = raw_data
        
        if self.verbose:
            print(f"Loaded {len(data)} chapters from OCR data")
            
        return data

    def _build_section_index(self) -> Dict[str, Dict]:
        """Build an index of sections for quick lookup"""
        index = {}
        
        for chapter in self.chapters:
            chapter_num = chapter.get('chapter_number', 'Unknown')
            title = chapter.get('title', '')
            content = chapter.get('full_text', chapter.get('content', ''))
            
            index[chapter_num] = {
                'title': title,
                'content': content,
                'chapter_data': chapter
            }
            
        if self.verbose:
            print(f"Built section index with {len(index)} sections")
            
        return index

    def _determine_section_level(self, section_id: str, title: str) -> int:
        """Determine the hierarchical level of a section"""
        # Parse section number to determine level
        if not section_id or section_id == 'Unknown':
            return 1
        
        # Count dots in section number
        dot_count = section_id.count('.')
        
        # Check title for level indicators
        title_lower = title.lower() if title else ""
        if any(word in title_lower for word in ['hoofdstuk', 'chapter', 'deel']):
            return 1
        elif any(word in title_lower for word in ['sectie', 'section']):
            return 2
        elif dot_count == 0:
            return 1
        elif dot_count == 1:
            return 2
        else:
            return 3

    def _classify_content_type(self, content: str, title: str) -> Tuple[str, float]:
        """Classify content type based on text analysis"""
        content_lower = content.lower() if content else ""
        title_lower = title.lower() if title else ""
        combined_text = content_lower + " " + title_lower
        
        best_match = 'general'
        best_score = 0.0
        
        for category, data in self.task_patterns.items():
            score = 0
            for pattern in data['keywords']:
                matches = len(re.findall(pattern, combined_text))
                score += matches
            
            # Normalize score by content length
            if len(combined_text) > 0:
                normalized_score = score / (len(combined_text) / 1000)
                if normalized_score > best_score:
                    best_score = normalized_score
                    best_match = category
        
        confidence = min(best_score, 1.0)
        return best_match, confidence

    def _generate_enhanced_summary(self, content: str, title: str, content_type: str) -> str:
        """Generate enhanced summary with execution details"""
        if not content.strip():
            return "No content available for analysis."
        
        # Extract key execution details
        content_lower = content.lower()
        execution_details = []
        
        # Look for specific execution patterns
        if 'must' in content_lower or 'shall' in content_lower or 'required' in content_lower:
            execution_details.append("Contains mandatory requirements")
        
        if any(word in content_lower for word in ['material', 'equipment', 'tool', 'materiaal']):
            execution_details.append("Specifies materials or equipment")
        
        if any(word in content_lower for word in ['method', 'procedure', 'process', 'methode']):
            execution_details.append("Describes execution methods")
        
        if any(word in content_lower for word in ['quality', 'standard', 'specification', 'kwaliteit']):
            execution_details.append("Includes quality standards")
        
        # Create summary based on content type
        summary_parts = []
        
        if content_type == 'demolition':
            summary_parts.append("Demolition work section")
        elif content_type == 'structural':
            summary_parts.append("Structural construction work")
        elif content_type == 'electrical':
            summary_parts.append("Electrical installation work")
        elif content_type == 'plumbing':
            summary_parts.append("Plumbing and sanitary work")
        elif content_type == 'hvac':
            summary_parts.append("HVAC installation work")
        elif content_type == 'finishes':
            summary_parts.append("Finishing work")
        elif content_type == 'administrative':
            summary_parts.append("Administrative requirements")
        else:
            summary_parts.append("General construction work")
        
        # Add execution details
        if execution_details:
            summary_parts.extend(execution_details)
        
        # Add content snippet
        content_snippet = content[:200].strip()
        if content_snippet:
            summary_parts.append(f"Content preview: {content_snippet}...")
        
        return " - ".join(summary_parts)

    def _identify_issues(self, content: str, title: str, content_type: str) -> List[str]:
        """Identify potential issues in the section"""
        issues = []
        
        if not content.strip():
            issues.append("Empty or missing content")
            return issues
        
        content_lower = content.lower()
        title_lower = title.lower() if title else ""
        
        # Check for content-title mismatch
        title_indicators = []
        for category, data in self.task_patterns.items():
            for pattern in data['keywords']:
                if re.search(pattern, title_lower):
                    title_indicators.append(category)
                    break
        
        if title_indicators and content_type not in title_indicators:
            issues.append(f"Content type ({content_type}) may not match title indicators")
        
        # Check for incomplete information
        if len(content) < 100:
            issues.append("Very short content - may be incomplete")
        
        # Check for missing key information
        if content_type in ['electrical', 'plumbing', 'hvac'] and not any(word in content_lower for word in ['install', 'connect', 'pipe', 'wire']):
            issues.append("Missing installation details")
        
        return issues

    def _suggest_improvements(self, content: str, title: str, content_type: str, issues: List[str]) -> List[str]:
        """Suggest improvements for the section"""
        suggestions = []
        
        if "Empty or missing content" in issues:
            suggestions.append("Add detailed content describing the work requirements")
        
        if "Content type" in str(issues):
            suggestions.append("Review section placement or adjust content to match title")
        
        if "Very short content" in issues:
            suggestions.append("Expand content with more detailed specifications")
        
        if "Missing installation details" in issues:
            suggestions.append("Add specific installation procedures and requirements")
        
        # Content-type specific suggestions
        if content_type == 'demolition':
            suggestions.append("Include safety procedures and debris disposal methods")
        elif content_type == 'structural':
            suggestions.append("Specify materials, connections, and load requirements")
        elif content_type == 'electrical':
            suggestions.append("Include wiring specifications and safety standards")
        
        return suggestions

    def _analyze_batch_with_llm(self, batch: List[Dict], model: GenerativeModel) -> Dict[str, Any]:
        """
        Analyzes a batch of sections using a generative model.
        """
        if not batch:
            return {}

        prompt_parts = [
            "You are an expert construction contract analyst reviewing sections from a Lastenboek (Specifications).",
            "For EACH section provided below, perform a TASK PLACEMENT CHECK.",
            "Evaluate if the tasks described in the section's FULL TEXT seem contextually appropriate for the section defined by its ID and Title.",
            "Look for content that seems misplaced given the section's title or its place in the hierarchy.",
            "Examples of misplacements: painting tasks described under a woodworking section, detailed electrical work in a structural chapter, foundation details in a finishing chapter.",
            "\nFormat your analysis for EACH section as a JSON object in this exact structure:",
            "{",
            "  \"section_id\": \"the section ID\",",
            "  \"analysis\": {",
            "    \"issues_found\": [",
            "      {",
            "        \"description\": \"A detailed description of a single misplaced task or issue.\",",
            "        \"severity\": \"low|medium|high\"",
            "      }",
            "    ],",
            "    \"summary\": \"A brief overall summary of any placement issues for this section, or 'No placement issues identified.'\"",
            "  }",
            "}",
            "\nGuidelines:",
            "1. Base your judgment on the FULL TEXT provided for each section.",
            "2. If no issues are found, 'issues_found' MUST be an empty list [].",
            "3. For 'severity', use 'high' for clear contradictions, 'medium' for likely issues, and 'low' for minor inconsistencies.",
            "4. Provide a concise but complete 'summary'.",
            "\n--- SECTIONS FOR ANALYSIS ---"
        ]

        for section in batch:
            prompt_parts.append("\n---")
            prompt_parts.append(f"Section ID: {section.get('chapter_number', 'N/A')}")
            prompt_parts.append(f"Title: {section.get('title', 'N/A')}")
            # Use a reasonable portion of the text to avoid excessively long prompts
            content_preview = section.get('full_text', '')[:4000]
            prompt_parts.append(f"FULL TEXT (first 4000 chars):\n{content_preview}")

        prompt_parts.append("\n--- END SECTIONS --- ")
        prompt_parts.append("\nReturn your analysis STRICTLY as a JSON array of objects, with one object per section. Ensure the output is valid JSON.")
        
        prompt = "\n".join(prompt_parts)

        try:
            response = model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "max_output_tokens": 8192,
                    "response_mime_type": "application/json",
                }
            )
            
            response_json = json.loads(response.text)
            
            # Re-key the results by section_id for easier lookup
            results_by_id = {item['section_id']: item for item in response_json}
            return results_by_id

        except Exception as e:
            if self.verbose:
                print(f"Error during LLM batch analysis: {e}")
            # Return an error structure for each item in the batch
            return {
                section.get('chapter_number'): {
                    "section_id": section.get('chapter_number'),
                    "analysis": {
                        "issues_found": [f"LLM analysis failed: {e}"],
                        "summary": "Failed to analyze this section."
                    }
                } for section in batch
            }


    def analyze_all_sections(self, model: GenerativeModel) -> List[EnhancedSectionAnalysis]:
        """Analyze all sections using the LLM and return enhanced analysis"""
        all_analyses = {}
        batch_size = 5 # Process 5 sections at a time

        batches = [self.chapters[i:i + batch_size] for i in range(0, len(self.chapters), batch_size)]

        for i, batch in enumerate(batches):
            if self.verbose:
                print(f"Analyzing batch {i+1}/{len(batches)}...")
            
            batch_results = self._analyze_batch_with_llm(batch, model)
            all_analyses.update(batch_results)

        # Now, format the results into the original dataclass structure
        final_report = []
        for chapter in self.chapters:
            section_id = chapter.get('chapter_number', 'Unknown')
            llm_result = all_analyses.get(section_id, {}).get('analysis', {})
            
            analysis = EnhancedSectionAnalysis(
                level=self._determine_section_level(section_id, chapter.get('title')),
                title=chapter.get('title', 'Untitled Section'),
                start_page=chapter.get('start_page', 1),
                end_page=chapter.get('end_page', 1),
                summary=llm_result.get('summary', 'Analysis may have failed for this item.'),
                section_id=section_id,
                content_type='llm_analyzed', # We can use a new content type
                confidence=llm_result.get('confidence', 0.9 if 'issues_found' in llm_result else 0.5), # Dummy confidence
                issues=llm_result.get('issues_found', []),
                suggested_improvements=llm_result.get('suggested_improvements', [])
            )
            final_report.append(analysis)
            
        return final_report

    def generate_summary_format_report(self, analyses: List[EnhancedSectionAnalysis]) -> List[Dict]:
        """Generate report in the same format as the vision-based approach"""
        report = []
        
        for analysis in analyses:
            section_data = {
                "level": analysis.level,
                "title": analysis.title,
                "start_page": analysis.start_page,
                "end_page": analysis.end_page,
                "summary": analysis.summary,
                # Enhanced fields from full content analysis
                "section_id": analysis.section_id,
                "content_type": analysis.content_type,
                "confidence": analysis.confidence,
                "issues": analysis.issues,
                "suggested_improvements": analysis.suggested_improvements
            }
            report.append(section_data)
        
        return report

def main():
    parser = argparse.ArgumentParser(description="Enhanced Task Placement Checker - Summary Format")
    parser.add_argument(
        "--ocr-data", 
        default="ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json",
        help="Path to OCR chapters with text JSON file"
    )
    parser.add_argument(
        "--output",
        default="enhanced_placement_analysis.json",
        help="Output file for analysis results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize checker
        print(f"Loading OCR data from: {args.ocr_data}")
        checker = EnhancedTaskChecker(args.ocr_data, args.verbose)
        
        print(f"Analyzing {len(checker.chapters)} sections...")
        
        # Analyze all sections
        analyses = checker.analyze_all_sections()
        
        # Generate report in summary format
        report = checker.generate_summary_format_report(analyses)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\nAnalysis complete!")
        print(f"Total sections analyzed: {len(report)}")
        
        # Count by content type
        content_types = {}
        issues_count = 0
        for item in report:
            content_type = item.get('content_type', 'unknown')
            content_types[content_type] = content_types.get(content_type, 0) + 1
            if item.get('issues'):
                issues_count += len(item['issues'])
        
        print(f"Content types identified:")
        for content_type, count in content_types.items():
            print(f"  {content_type}: {count}")
        
        print(f"Total issues identified: {issues_count}")
        print(f"Results saved to: {args.output}")
        
        if args.verbose and report:
            print(f"\nFirst few sections:")
            for item in report[:3]:
                print(f"- {item['title']} (Level {item['level']})")
                print(f"  Type: {item['content_type']}")
                print(f"  Summary: {item['summary'][:100]}...")
                if item['issues']:
                    print(f"  Issues: {', '.join(item['issues'])}")
                print()
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


def analyze_placement_from_file(ocr_data_path: str, project_id: str, location: str, 
                               model_name: str, verbose: bool = False) -> List[Dict]:
    """
    Wrapper function for enhanced placement analysis that matches the expected interface.
    
    Args:
        ocr_data_path: Path to the OCR data JSON file
        project_id: Google Cloud project ID
        location: Google Cloud location
        model_name: Model name for the generative model
        verbose: Enable verbose output
        
    Returns:
        List of analysis results in the expected format
    """
    if not VERTEX_AI_AVAILABLE:
        raise ImportError("Vertex AI libraries not found or failed to import.")

    try:
        # --- Initialize Vertex AI ---
        if verbose:
            print(f"Initializing Vertex AI with project={project_id}, location={location}")
        
        google.auth.default() # This will raise an error if auth is not configured
        aiplatform.init(project=project_id, location=location)
        model = GenerativeModel(model_name)
        # --------------------------

        # Initialize the enhanced task checker
        checker = EnhancedTaskChecker(ocr_data_path, verbose)
        
        if verbose:
            print(f"Analyzing {len(checker.chapters)} sections with model {model_name}...")
        
        # Analyze all sections using the LLM
        analyses = checker.analyze_all_sections(model)
        
        # Generate report in summary format
        report = checker.generate_summary_format_report(analyses)
        
        # Transform to match expected output format (list of chapters with analysis)
        result = []
        for item in report:
            chapter_result = {
                'chapter': item['section_id'],
                'title': item['title'],
                'start_page': item['start_page'],
                'end_page': item['end_page'],
                'analysis': {
                    'summary': item['summary'],
                    'content_type': item['content_type'],
                    'confidence': item['confidence'],
                    'issues_found': item['issues'],
                    'suggested_improvements': item['suggested_improvements'],
                    'level': item['level']
                }
            }
            result.append(chapter_result)
        
        if verbose:
            print(f"Enhanced placement analysis completed. Analyzed {len(result)} sections.")
            
        return result
        
    except Exception as e:
        if verbose:
            print(f"Error in enhanced placement analysis: {e}")
        raise


if __name__ == "__main__":
    main() 