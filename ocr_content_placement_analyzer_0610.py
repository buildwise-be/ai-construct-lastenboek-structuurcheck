#!/usr/bin/env python3
"""
OCR Content Placement Analyzer - June 10th

This script analyzes the OCR content directly to find placement issues within the document itself,
rather than requiring external task data. It examines section content vs section titles to identify misplaced content.

Usage:
    python ocr_content_placement_analyzer_0610.py [options]

Options:
    --ocr-data PATH     Path to OCR chapters with text JSON file
    --output PATH       Output file for results (default: ocr_content_analysis_0610.json)
    --verbose          Enable verbose output
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
    """Represents a content placement issue within the OCR data"""
    section_id: str
    section_title: str
    issue_type: str
    severity: str  # 'high', 'medium', 'low'
    confidence: float  # 0.0 to 1.0
    description: str
    problematic_content: str
    suggested_action: str
    content_sample: str

class OCRContentAnalyzer:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        """Initialize with OCR content data"""
        self.verbose = verbose
        self.chapters = self._load_ocr_data(ocr_data_path)
        self.section_index = self._build_section_index()
        
        # Content classification patterns - what should be in which sections
        self.section_patterns = {
            'algemeen': ['general', 'common', 'overview', 'introduction', 'algemeen'],
            'administratief': ['permit', 'license', 'documentation', 'contract', 'admin', 'legal'],
            'voorbereidend': ['preparation', 'setup', 'preliminary', 'voorbereidend', 'werf'],
            'afbraak': ['demolition', 'remove', 'strip', 'break', 'sloop', 'afbraak'],
            'ruwbouw': ['structure', 'concrete', 'masonry', 'foundation', 'ruwbouw', 'metsel'],
            'dak': ['roof', 'roofing', 'dakwerk', 'isolatie', 'bedekking'],
            'ramen_deuren': ['windows', 'doors', 'glazing', 'ramen', 'deuren', 'beglazing'],
            'isolatie': ['insulation', 'thermal', 'isolatie', 'thermisch'],
            'afwerking': ['finishing', 'paint', 'tiles', 'flooring', 'afwerking', 'tegels'],
            'sanitair': ['plumbing', 'sanitary', 'bathroom', 'sanitair', 'badkamer'],
            'elektriciteit': ['electrical', 'wiring', 'lighting', 'elektriciteit', 'verlichting'],
            'hvac': ['heating', 'ventilation', 'air conditioning', 'verwarming', 'ventilatie']
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
                    'content': chapter_info.get('text', ''),
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
        """Build an index of sections for analysis"""
        index = {}
        
        for chapter in self.chapters:
            chapter_num = chapter.get('chapter_number', 'Unknown')
            title = chapter.get('title', '') or ''
            content = chapter.get('full_text', chapter.get('content', '')) or ''
            
            index[chapter_num] = {
                'title': title,
                'content': content,
                'character_count': len(content),
                'chapter_data': chapter
            }
            
        if self.verbose:
            print(f"Built section index with {len(index)} sections")
            
        return index

    def _classify_section_content(self, content: str) -> List[str]:
        """Classify what type of content this appears to be"""
        content_lower = content.lower()
        classifications = []
        
        for category, patterns in self.section_patterns.items():
            score = 0
            for pattern in patterns:
                # Count occurrences of pattern words
                score += len(re.findall(r'\b' + re.escape(pattern) + r'\b', content_lower))
            
            if score > 0:
                classifications.append((category, score))
        
        # Sort by score and return top classifications
        classifications.sort(key=lambda x: x[1], reverse=True)
        return [cat for cat, score in classifications[:3]]  # Top 3

    def _analyze_section_consistency(self, section_id: str, title: str, content: str) -> Optional[ContentIssue]:
        """Analyze if section content matches its title/expected content"""
        if not content.strip() or len(content) < 50:
            return None  # Skip very short sections
        
        title_lower = title.lower()
        content_classifications = self._classify_section_content(content)
        
        # Determine expected content type from title
        expected_type = None
        for category, patterns in self.section_patterns.items():
            for pattern in patterns:
                if pattern in title_lower:
                    expected_type = category
                    break
            if expected_type:
                break
        
        # If we couldn't determine expected type from title, try from section number
        if not expected_type:
            section_lower = section_id.lower()
            if section_lower.startswith('00'):
                expected_type = 'algemeen'
            elif section_lower.startswith('01'):
                expected_type = 'administratief'
            elif section_lower.startswith('02'):
                expected_type = 'voorbereidend'
            elif 'afbraak' in section_lower or 'sloop' in section_lower:
                expected_type = 'afbraak'
            elif any(x in section_lower for x in ['21', '22', '23', '24']):  # Common masonry sections
                expected_type = 'ruwbouw'
        
        # Check for mismatches
        if expected_type and content_classifications:
            top_classification = content_classifications[0]
            
            if expected_type != top_classification and expected_type not in content_classifications:
                # Found a mismatch
                confidence = 0.7 if len(content_classifications) > 1 else 0.5
                severity = "high" if confidence > 0.6 else "medium"
                
                return ContentIssue(
                    section_id=section_id,
                    section_title=title,
                    issue_type="content_section_mismatch",
                    severity=severity,
                    confidence=confidence,
                    description=f"Section appears to contain {top_classification} content but is titled/positioned as {expected_type}",
                    problematic_content=f"Expected: {expected_type}, Found: {', '.join(content_classifications)}",
                    suggested_action=f"Review if content belongs in a {top_classification} section instead",
                    content_sample=content[:300] + "..." if len(content) > 300 else content
                )
        
        return None

    def _find_duplicate_content(self) -> List[ContentIssue]:
        """Find sections with significantly similar content"""
        issues = []
        sections = list(self.section_index.items())
        
        for i, (section_id1, data1) in enumerate(sections):
            for j, (section_id2, data2) in enumerate(sections[i+1:], i+1):
                content1 = data1['content'].lower().strip()
                content2 = data2['content'].lower().strip()
                
                if len(content1) < 100 or len(content2) < 100:
                    continue  # Skip short sections
                
                # Simple similarity check - count common words
                words1 = set(content1.split())
                words2 = set(content2.split())
                
                if len(words1) == 0 or len(words2) == 0:
                    continue
                    
                common_words = words1.intersection(words2)
                similarity = len(common_words) / min(len(words1), len(words2))
                
                if similarity > 0.8:  # 80% similarity threshold
                    issue = ContentIssue(
                        section_id=f"{section_id1} & {section_id2}",
                        section_title=f"{data1['title']} / {data2['title']}",
                        issue_type="duplicate_content",
                        severity="medium",
                        confidence=similarity,
                        description=f"Sections contain {similarity:.1%} similar content",
                        problematic_content=f"Similarity: {similarity:.1%}",
                        suggested_action="Review if one section is redundant or misplaced",
                        content_sample=f"Section 1: {content1[:200]}...\nSection 2: {content2[:200]}..."
                    )
                    issues.append(issue)
        
        return issues

    def _find_empty_or_minimal_sections(self) -> List[ContentIssue]:
        """Find sections with no meaningful content"""
        issues = []
        
        for section_id, data in self.section_index.items():
            content = data['content'].strip()
            title = data['title']
            
            if len(content) == 0:
                issue = ContentIssue(
                    section_id=section_id,
                    section_title=title,
                    issue_type="empty_section",
                    severity="low",
                    confidence=1.0,
                    description="Section has no content",
                    problematic_content="No content found",
                    suggested_action="Add content or remove section",
                    content_sample=""
                )
                issues.append(issue)
            elif len(content) < 50 and len(content.split()) < 5:
                issue = ContentIssue(
                    section_id=section_id,
                    section_title=title,
                    issue_type="minimal_content",
                    severity="low",
                    confidence=0.8,
                    description=f"Section has very little content ({len(content)} chars)",
                    problematic_content=content,
                    suggested_action="Expand content or merge with related section",
                    content_sample=content
                )
                issues.append(issue)
        
        return issues

    def analyze_ocr_content(self) -> List[ContentIssue]:
        """Main analysis function - analyzes the OCR content for placement issues"""
        all_issues = []
        
        if self.verbose:
            print("Analyzing section content consistency...")
        
        # Check each section for content-title mismatches
        for section_id, data in self.section_index.items():
            if self.verbose and len(all_issues) % 50 == 0:
                print(f"Analyzed {len(all_issues)} sections so far...")
            
            issue = self._analyze_section_consistency(
                section_id, 
                data['title'], 
                data['content']
            )
            if issue:
                all_issues.append(issue)
        
        if self.verbose:
            print("Checking for duplicate content...")
        
        # Find duplicate content
        duplicate_issues = self._find_duplicate_content()
        all_issues.extend(duplicate_issues)
        
        if self.verbose:
            print("Checking for empty/minimal sections...")
        
        # Find empty/minimal sections
        empty_issues = self._find_empty_or_minimal_sections()
        all_issues.extend(empty_issues)
        
        return all_issues

    def generate_report(self, issues: List[ContentIssue]) -> Dict:
        """Generate a comprehensive analysis report"""
        if not issues:
            return {
                "summary": "No significant content placement issues detected",
                "total_issues": 0,
                "issues_by_type": {},
                "issues_by_severity": {"high": 0, "medium": 0, "low": 0},
                "issues": []
            }
        
        # Count issues by type and severity
        type_counts = {}
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        
        for issue in issues:
            type_counts[issue.issue_type] = type_counts.get(issue.issue_type, 0) + 1
            severity_counts[issue.severity] += 1
        
        # Convert issues to dict format
        issues_data = []
        for issue in issues:
            issues_data.append({
                "section_id": issue.section_id,
                "section_title": issue.section_title,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "confidence": issue.confidence,
                "description": issue.description,
                "problematic_content": issue.problematic_content,
                "suggested_action": issue.suggested_action,
                "content_sample": issue.content_sample
            })
        
        return {
            "summary": f"Found {len(issues)} content placement issues across {len(self.section_index)} sections",
            "total_issues": len(issues),
            "issues_by_type": type_counts,
            "issues_by_severity": severity_counts,
            "issues": issues_data,
            "analysis_metadata": {
                "total_sections_processed": len(self.section_index),
                "content_categories": list(self.section_patterns.keys()),
                "analysis_types": ["content_section_mismatch", "duplicate_content", "empty_section", "minimal_content"]
            }
        }

def main():
    parser = argparse.ArgumentParser(description="OCR Content Placement Analyzer")
    parser.add_argument(
        "--ocr-data", 
        default="ocroutput/pipeline_run_20250610_094433_Anoniem_Lastenboek/final_combined_output/chapters_with_text_v3.json",
        help="Path to OCR chapters with text JSON file"
    )
    parser.add_argument(
        "--output",
        default="ocr_content_analysis_0610.json",
        help="Output file for analysis results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize analyzer
        print(f"Loading OCR data from: {args.ocr_data}")
        analyzer = OCRContentAnalyzer(args.ocr_data, args.verbose)
        
        print(f"Analyzing {len(analyzer.section_index)} sections for content placement issues...")
        
        # Analyze content
        issues = analyzer.analyze_ocr_content()
        
        # Generate report
        report = analyzer.generate_report(issues)
        
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
            print(f"\nIssue breakdown by type:")
            for issue_type, count in report['issues_by_type'].items():
                print(f"- {issue_type}: {count}")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 