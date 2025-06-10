#!/usr/bin/env python3
"""
Enhanced Task Placement Checker using Full OCR Text Content

This script analyzes task placement using the full text content from OCR output,
providing much more accurate and detailed analysis than summary-based approaches.

Usage:
    python enhanced_task_checker.py [options]

Options:
    --ocr-data PATH     Path to OCR chapters with text JSON file
    --task-data PATH    Path to task data (JSON or CSV)
    --output PATH       Output file for results (default: placement_analysis.json)
    --verbose          Enable verbose output
"""

import json
import argparse
import sys
import os
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import re

@dataclass
class PlacementIssue:
    """Represents a task placement issue with detailed context"""
    task_id: str
    task_description: str
    current_section: str
    issue_type: str
    severity: str  # 'high', 'medium', 'low'
    confidence: float  # 0.0 to 1.0
    suggested_sections: List[str]
    reasoning: str
    content_context: str

class EnhancedTaskChecker:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        """Initialize with full OCR text content"""
        self.verbose = verbose
        self.chapters = self._load_ocr_data(ocr_data_path)
        self.section_index = self._build_section_index()
        
        # Task classification patterns
        self.task_patterns = {
            'administrative': [
                r'permit', r'license', r'approval', r'documentation', r'contract',
                r'admin', r'legal', r'insurance', r'safety plan', r'coordination'
            ],
            'demolition': [
                r'demolit', r'remove', r'strip', r'break out', r'clear',
                r'dismantle', r'tear down'
            ],
            'structural': [
                r'concrete', r'steel', r'beam', r'column', r'foundation',
                r'structural', r'reinforc', r'load bearing'
            ],
            'hvac': [
                r'heating', r'ventilation', r'air conditioning', r'hvac',
                r'ductwork', r'climate', r'temperature control'
            ],
            'electrical': [
                r'electrical', r'wiring', r'power', r'lighting', r'outlet',
                r'circuit', r'panel', r'voltage'
            ],
            'plumbing': [
                r'plumbing', r'water', r'drain', r'pipe', r'faucet',
                r'toilet', r'sink', r'sewer'
            ],
            'finishes': [
                r'paint', r'tile', r'flooring', r'ceiling', r'wall finish',
                r'carpet', r'trim', r'molding'
            ]
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
                    'start_page': chapter_info.get('start_page'),
                    'end_page': chapter_info.get('end_page'),
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

    def _classify_task(self, task_description: str) -> List[str]:
        """Classify task based on description patterns"""
        task_lower = task_description.lower()
        classifications = []
        
        for category, patterns in self.task_patterns.items():
            for pattern in patterns:
                if re.search(pattern, task_lower):
                    classifications.append(category)
                    break
                    
        return classifications or ['general']

    def _find_relevant_sections(self, task_description: str, task_classifications: List[str]) -> List[Tuple[str, float]]:
        """Find sections most relevant to the task"""
        relevant_sections = []
        task_keywords = set(task_description.lower().split())
        
        for section_id, section_data in self.section_index.items():
            title = (section_data['title'] or '').lower()
            content = (section_data['content'] or '').lower()
            
            # Calculate relevance score
            title_matches = len(task_keywords.intersection(set(title.split())))
            content_matches = len(task_keywords.intersection(set(content.split())))
            
            # Bonus for classification matches
            classification_bonus = 0
            for classification in task_classifications:
                if classification in title or classification in content:
                    classification_bonus += 0.3
            
            # Calculate final score
            score = (title_matches * 2 + content_matches * 0.1 + classification_bonus)
            
            if score > 0.5:  # Threshold for relevance
                relevant_sections.append((section_id, score))
        
        # Sort by relevance score
        relevant_sections.sort(key=lambda x: x[1], reverse=True)
        return relevant_sections[:5]  # Top 5 most relevant

    def _analyze_current_placement(self, task_description: str, current_section: str) -> PlacementIssue:
        """Analyze if current task placement is appropriate"""
        task_classifications = self._classify_task(task_description)
        relevant_sections = self._find_relevant_sections(task_description, task_classifications)
        
        # Get current section info
        current_section_data = self.section_index.get(current_section, {})
        current_title = current_section_data.get('title', 'Unknown Section')
        current_content = current_section_data.get('content', '')
        
        # Analyze placement appropriateness
        if not relevant_sections:
            # No clearly relevant sections found
            issue = PlacementIssue(
                task_id="",
                task_description=task_description,
                current_section=current_section,
                issue_type="uncertain_classification",
                severity="low",
                confidence=0.3,
                suggested_sections=[],
                reasoning="Unable to determine optimal section placement",
                content_context=current_content[:500] if current_content else "No content available"
            )
            return issue
        
        # Check if current section is in top relevant sections
        current_in_relevant = any(section_id == current_section for section_id, _ in relevant_sections)
        best_section, best_score = relevant_sections[0]
        
        if current_in_relevant and current_section == best_section:
            # Current placement is optimal
            return None
        elif current_in_relevant:
            # Current placement is acceptable but not optimal
            issue = PlacementIssue(
                task_id="",
                task_description=task_description,
                current_section=current_section,
                issue_type="suboptimal_placement",
                severity="low",
                confidence=0.6,
                suggested_sections=[best_section],
                reasoning=f"Task is in a relevant section but {best_section} might be more appropriate",
                content_context=current_content[:500] if current_content else "No content available"
            )
            return issue
        else:
            # Current placement seems incorrect
            severity = "high" if best_score > 2.0 else "medium"
            confidence = min(best_score / 3.0, 0.9)
            
            issue = PlacementIssue(
                task_id="",
                task_description=task_description,
                current_section=current_section,
                issue_type="misplaced_task",
                severity=severity,
                confidence=confidence,
                suggested_sections=[section_id for section_id, _ in relevant_sections[:3]],
                reasoning=f"Task appears misplaced. Better suited for sections with {', '.join(task_classifications)} content",
                content_context=current_content[:500] if current_content else "No content available"
            )
            return issue

    def analyze_task_placement(self, tasks: List[Dict]) -> List[PlacementIssue]:
        """Analyze placement for a list of tasks"""
        issues = []
        
        for i, task in enumerate(tasks):
            if self.verbose and i % 10 == 0:
                print(f"Analyzing task {i+1}/{len(tasks)}")
            
            task_id = task.get('id', task.get('task_id', f'task_{i}'))
            description = task.get('description', task.get('task', ''))
            current_section = task.get('section', task.get('current_section', 'unknown'))
            
            issue = self._analyze_current_placement(description, current_section)
            if issue:
                issue.task_id = task_id
                issues.append(issue)
        
        return issues

    def generate_report(self, issues: List[PlacementIssue]) -> Dict:
        """Generate a comprehensive analysis report"""
        if not issues:
            return {
                "summary": "No placement issues detected",
                "total_issues": 0,
                "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
                "issues": []
            }
        
        # Count issues by severity
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] += 1
        
        # Convert issues to dict format
        issues_data = []
        for issue in issues:
            issues_data.append({
                "task_id": issue.task_id,
                "task_description": issue.task_description,
                "current_section": issue.current_section,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "confidence": issue.confidence,
                "suggested_sections": issue.suggested_sections,
                "reasoning": issue.reasoning,
                "content_context": issue.content_context
            })
        
        return {
            "summary": f"Found {len(issues)} potential placement issues",
            "total_issues": len(issues),
            "issues_by_severity": severity_counts,
            "issues": issues_data,
            "analysis_metadata": {
                "total_sections_analyzed": len(self.section_index),
                "classification_categories": list(self.task_patterns.keys())
            }
        }

def load_sample_tasks() -> List[Dict]:
    """Load sample tasks for testing"""
    return [
        {
            "id": "sample_001",
            "description": "Install electrical outlets in office areas",
            "section": "03.01",  # Wrong section (should be electrical)
        },
        {
            "id": "sample_002", 
            "description": "Remove existing concrete flooring",
            "section": "02.01",  # Demolition - could be correct
        },
        {
            "id": "sample_003",
            "description": "Install HVAC ductwork throughout building",
            "section": "15.01",  # HVAC section - likely correct
        }
    ]

def main():
    parser = argparse.ArgumentParser(description="Enhanced Task Placement Checker")
    parser.add_argument(
        "--ocr-data", 
        default="ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json",
        help="Path to OCR chapters with text JSON file"
    )
    parser.add_argument(
        "--task-data",
        help="Path to task data JSON or CSV file (optional - will use sample data if not provided)"
    )
    parser.add_argument(
        "--output",
        default="placement_analysis.json",
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
        
        # Load tasks
        if args.task_data:
            if args.task_data.endswith('.json'):
                with open(args.task_data, 'r', encoding='utf-8') as f:
                    tasks = json.load(f)
            else:
                print("CSV task loading not implemented yet. Using sample tasks.")
                tasks = load_sample_tasks()
        else:
            print("No task data provided. Using sample tasks for demonstration.")
            tasks = load_sample_tasks()
        
        print(f"Analyzing {len(tasks)} tasks...")
        
        # Analyze tasks
        issues = checker.analyze_task_placement(tasks)
        
        # Generate report
        report = checker.generate_report(issues)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\nAnalysis complete!")
        print(f"Total issues found: {report['total_issues']}")
        print(f"High severity: {report['issues_by_severity']['high']}")
        print(f"Medium severity: {report['issues_by_severity']['medium']}")
        print(f"Low severity: {report['issues_by_severity']['low']}")
        print(f"Results saved to: {args.output}")
        
        if args.verbose and issues:
            print(f"\nFirst few issues:")
            for issue in issues[:3]:
                print(f"- Task {issue.task_id}: {issue.severity} severity")
                print(f"  Current: {issue.current_section}, Suggested: {issue.suggested_sections}")
                print(f"  Reason: {issue.reasoning}")
                print()
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 