#!/usr/bin/env python3
"""
OCR Direct Content Analyzer - June 10th

Analyzes OCR content directly to find placement issues within the document itself.
No external task data needed - analyzes the content vs section titles and structure.

Usage:
    python ocr_direct_content_analyzer_0610.py --verbose
"""

import json
import argparse
import sys
import os
import re
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ContentIssue:
    """Represents a content placement issue"""
    section_id: str
    section_title: str
    issue_type: str
    severity: str
    confidence: float
    description: str
    content_sample: str

class DirectContentAnalyzer:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        self.verbose = verbose
        self.chapters = self._load_ocr_data(ocr_data_path)
        
        # Keywords that indicate content types
        self.content_indicators = {
            'electrical': ['electrical', 'elektriciteit', 'wiring', 'outlet', 'circuit', 'voltage', 'lighting', 'verlichting'],
            'plumbing': ['plumbing', 'sanitair', 'water', 'drain', 'pipe', 'toilet', 'bathroom'],
            'hvac': ['heating', 'ventilation', 'hvac', 'verwarming', 'airco', 'klimaat'],
            'structural': ['concrete', 'steel', 'beam', 'foundation', 'beton', 'staal'],
            'finishing': ['paint', 'tile', 'flooring', 'afwerking', 'vloer', 'tegels'],
            'demolition': ['demolition', 'remove', 'afbraak', 'slopen', 'uitbreken']
        }

    def _load_ocr_data(self, data_path: str) -> List[Dict]:
        with open(data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        if isinstance(raw_data, dict):
            data = []
            for chapter_num, chapter_info in raw_data.items():
                data.append({
                    'chapter_number': chapter_num,
                    'title': chapter_info.get('title', '') or '',
                    'content': chapter_info.get('text', '') or '',
                    'character_count': chapter_info.get('character_count', 0)
                })
        else:
            data = raw_data
        
        if self.verbose:
            print(f"Loaded {len(data)} chapters from OCR data")
        return data

    def _detect_content_type(self, text: str) -> List[Tuple[str, int]]:
        """Detect what type of content this text contains"""
        text_lower = text.lower()
        results = []
        
        for content_type, keywords in self.content_indicators.items():
            score = sum(len(re.findall(r'\b' + re.escape(keyword) + r'\b', text_lower)) for keyword in keywords)
            if score > 0:
                results.append((content_type, score))
        
        return sorted(results, key=lambda x: x[1], reverse=True)

    def _analyze_section(self, section: Dict) -> List[ContentIssue]:
        """Analyze a single section for content issues"""
        issues = []
        section_id = section['chapter_number']
        title = section['title']
        content = section['content']
        
        if not content or len(content.strip()) < 50:
            if title:  # Only flag if there's a title but no content
                issues.append(ContentIssue(
                    section_id=section_id,
                    section_title=title,
                    issue_type="empty_section",
                    severity="low",
                    confidence=1.0,
                    description="Section has title but no meaningful content",
                    content_sample=content[:200] if content else "No content"
                ))
            return issues
        
        # Detect content types in this section
        detected_types = self._detect_content_type(content)
        
        if not detected_types:
            return issues  # No specific content type detected
        
        # Check if section number/title matches content type
        title_lower = title.lower() if title else ""
        section_lower = section_id.lower()
        
        primary_content_type = detected_types[0][0]
        
        # Define section number patterns
        section_expectations = {
            'electrical': ['elektrisch', 'electrical', 'verlichting'],
            'plumbing': ['sanitair', 'plumbing', 'water'],
            'hvac': ['verwarming', 'ventilatie', 'hvac'],
            'structural': ['constructie', 'beton', 'structural'],
            'finishing': ['afwerking', 'finishing'],
            'demolition': ['afbraak', 'sloop', 'demolition']
        }
        
        # Check if content matches expected section type
        expected_in_title = False
        if title:
            for keyword in self.content_indicators[primary_content_type]:
                if keyword in title_lower:
                    expected_in_title = True
                    break
        
        # Check if section title suggests different content
        title_suggests_different = False
        title_suggested_type = None
        if title:
            for content_type, keywords in self.content_indicators.items():
                if content_type != primary_content_type:
                    for keyword in keywords:
                        if keyword in title_lower:
                            title_suggests_different = True
                            title_suggested_type = content_type
                            break
                    if title_suggests_different:
                        break
        
        # Flag potential misplacement
        if title_suggests_different:
            issues.append(ContentIssue(
                section_id=section_id,
                section_title=title,
                issue_type="content_title_mismatch",
                severity="medium",
                confidence=0.7,
                description=f"Title suggests {title_suggested_type} content but section contains {primary_content_type} content",
                content_sample=content[:300] + "..." if len(content) > 300 else content
            ))
        elif not expected_in_title and len(detected_types) > 0:
            # Content type not reflected in title - might be misplaced
            confidence = detected_types[0][1] / max(10, len(content.split()) * 0.1)  # Adjust confidence based on keyword density
            confidence = min(confidence, 0.8)  # Cap confidence
            
            if confidence > 0.3:
                issues.append(ContentIssue(
                    section_id=section_id,
                    section_title=title,
                    issue_type="unclear_section_content",
                    severity="low" if confidence < 0.5 else "medium",
                    confidence=confidence,
                    description=f"Section contains {primary_content_type} content but title doesn't clearly indicate this",
                    content_sample=content[:300] + "..." if len(content) > 300 else content
                ))
        
        return issues

    def analyze_all_content(self) -> List[ContentIssue]:
        """Analyze all OCR content for placement issues"""
        all_issues = []
        
        for i, section in enumerate(self.chapters):
            if self.verbose and i % 50 == 0:
                print(f"Analyzing section {i+1}/{len(self.chapters)}")
            
            issues = self._analyze_section(section)
            all_issues.extend(issues)
        
        return all_issues

    def generate_report(self, issues: List[ContentIssue]) -> Dict:
        """Generate analysis report"""
        if not issues:
            return {
                "summary": f"No content placement issues found in {len(self.chapters)} sections",
                "total_issues": 0,
                "issues_by_type": {},
                "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
                "issues": []
            }
        
        # Count by type and severity
        type_counts = {}
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        
        for issue in issues:
            type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1
            severity_counts[issue.severity] += 1
        
        # Convert to dict format
        issues_data = []
        for issue in issues:
            issues_data.append({
                "section_id": issue.section_id,
                "section_title": issue.section_title,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "confidence": issue.confidence,
                "description": issue.description,
                "content_sample": issue.content_sample
            })
        
        return {
            "summary": f"Found {len(issues)} content issues in {len(self.chapters)} sections analyzed",
            "total_issues": len(issues),
            "issues_by_type": type_counts,
            "issues_by_severity": severity_counts,
            "issues": issues_data,
            "analysis_metadata": {
                "sections_analyzed": len(self.chapters),
                "content_types_detected": list(self.content_indicators.keys())
            }
        }

def main():
    parser = argparse.ArgumentParser(description="Direct OCR Content Analyzer")
    parser.add_argument(
        "--ocr-data", 
        default="ocroutput/pipeline_run_20250610_094433_Anoniem_Lastenboek/final_combined_output/chapters_with_text_v3.json",
        help="Path to OCR chapters with text JSON file"
    )
    parser.add_argument(
        "--output",
        default="direct_content_analysis_0610.json",
        help="Output file for analysis results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        print(f"Loading OCR data from: {args.ocr_data}")
        analyzer = DirectContentAnalyzer(args.ocr_data, args.verbose)
        
        print("Analyzing OCR content directly for placement issues...")
        issues = analyzer.analyze_all_content()
        
        print("Generating report...")
        report = analyzer.generate_report(issues)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\n" + "="*50)
        print(f"DIRECT CONTENT ANALYSIS COMPLETE")
        print(f"="*50)
        print(f"Sections analyzed: {len(analyzer.chapters)}")
        print(f"Issues found: {report['total_issues']}")
        print(f"High severity: {report['issues_by_severity']['high']}")
        print(f"Medium severity: {report['issues_by_severity']['medium']}")
        print(f"Low severity: {report['issues_by_severity']['low']}")
        print(f"Results saved to: {args.output}")
        
        if report['issues_by_type']:
            print(f"\nIssue types found:")
            for issue_type, count in report['issues_by_type'].items():
                print(f"  - {issue_type}: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 