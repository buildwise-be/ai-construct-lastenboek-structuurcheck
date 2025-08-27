#!/usr/bin/env python3
"""
Content Consistency Analyzer

This script analyzes document content for inconsistencies, contradictions, 
and logical conflicts. It looks for things that don't make sense or 
contradict each other within the document.

Usage:
    python content_consistency_analyzer.py [options]

Options:
    --ocr-data PATH     Path to OCR chapters with text JSON file
    --output PATH       Output file for results (default: consistency_analysis.json)
    --verbose          Enable verbose output
"""

import json
import argparse
import sys
import re
from typing import Dict, List, Any, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict
import difflib

@dataclass
class ConsistencyIssue:
    """Represents a consistency issue found in the document"""
    issue_type: str
    severity: str  # 'critical', 'major', 'minor'
    description: str
    sections_involved: List[str]
    conflicting_content: List[str]
    suggested_resolution: str
    confidence: float

class ContentConsistencyAnalyzer:
    def __init__(self, ocr_data_path: str, verbose: bool = False):
        """Initialize the consistency analyzer"""
        self.verbose = verbose
        self.chapters = self._load_ocr_data(ocr_data_path)
        self.section_index = self._build_section_index()
        self.consistency_issues = []
        
        # Define patterns for detecting different types of content
        self.material_patterns = {
            'concrete': [r'beton', r'concrete', r'C\d+/\d+', r'mortel'],
            'steel': [r'staal', r'steel', r'S\d+', r'ijzer'],
            'wood': [r'hout', r'wood', r'timber', r'houten'],
            'aluminum': [r'aluminium', r'aluminum', r'alu'],
            'pvc': [r'pvc', r'kunststof', r'plastic'],
            'glass': [r'glas', r'glass', r'glazen'],
            'ceramic': [r'keramiek', r'ceramic', r'tegels', r'tiles']
        }
        
        self.measurement_patterns = {
            'length': [r'(\d+(?:\.\d+)?)\s*(?:mm|cm|m|meter)', r'(\d+(?:\.\d+)?)\s*(?:millimeter|centimeter)'],
            'area': [r'(\d+(?:\.\d+)?)\s*(?:m²|m2|vierkante\s+meter)'],
            'volume': [r'(\d+(?:\.\d+)?)\s*(?:m³|m3|kubieke\s+meter|liter|l)'],
            'weight': [r'(\d+(?:\.\d+)?)\s*(?:kg|kilogram|gram|g|ton)'],
            'thickness': [r'(\d+(?:\.\d+)?)\s*(?:mm|cm)\s+(?:dik|thick|dikte)']
        }
        
        self.quality_standards = {
            'concrete_strength': [r'C\d+/\d+', r'sterkteklasse', r'strength\s+class'],
            'steel_grade': [r'S\d+', r'staalsoort', r'steel\s+grade'],
            'water_resistance': [r'IP\d+', r'waterbestendig', r'water\s+resistant'],
            'fire_resistance': [r'EI\d+', r'brandweerstand', r'fire\s+resistance']
        }

    def _load_ocr_data(self, data_path: str) -> List[Dict]:
        """Load OCR data"""
        with open(data_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        data = []
        
        if isinstance(raw_data, dict):
            # Dictionary format (full OCR data)
            for chapter_num, chapter_info in raw_data.items():
                chapter_data = {
                    'chapter_number': chapter_num,
                    'title': chapter_info.get('title', ''),
                    'content': chapter_info.get('text', chapter_info.get('content', '')),
                    'start_page': chapter_info.get('start_page', 1),
                    'end_page': chapter_info.get('end_page', 1)
                }
                data.append(chapter_data)
        elif isinstance(raw_data, list):
            # List format (summary format or enhanced format)
            for i, item in enumerate(raw_data):
                if isinstance(item, dict):
                    # Handle summary format
                    chapter_data = {
                        'chapter_number': item.get('section_id', f'section_{i}'),
                        'title': item.get('title', ''),
                        'content': item.get('summary', ''),  # Use summary as content for consistency checking
                        'start_page': item.get('start_page', 1),
                        'end_page': item.get('end_page', 1)
                    }
                    data.append(chapter_data)
        
        if self.verbose:
            print(f"Loaded {len(data)} chapters for consistency analysis")
            print(f"First chapter sample: {data[0] if data else 'No data'}")
        
        return data

    def _build_section_index(self) -> Dict[str, Dict]:
        """Build section index"""
        index = {}
        for chapter in self.chapters:
            chapter_num = chapter.get('chapter_number', 'Unknown')
            index[chapter_num] = {
                'title': chapter.get('title', ''),
                'content': chapter.get('content', ''),
                'chapter_data': chapter
            }
        return index

    def _extract_materials_mentioned(self, content: str) -> Set[str]:
        """Extract materials mentioned in content"""
        materials = set()
        content_lower = content.lower()
        
        for material, patterns in self.material_patterns.items():
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    materials.add(material)
        
        return materials

    def _extract_measurements(self, content: str) -> Dict[str, List[float]]:
        """Extract measurements from content"""
        measurements = defaultdict(list)
        
        for measure_type, patterns in self.measurement_patterns.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    try:
                        value = float(match)
                        measurements[measure_type].append(value)
                    except ValueError:
                        continue
        
        return dict(measurements)

    def _extract_quality_standards(self, content: str) -> Dict[str, List[str]]:
        """Extract quality standards mentioned"""
        standards = defaultdict(list)
        
        for standard_type, patterns in self.quality_standards.items():
            for pattern in patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                standards[standard_type].extend(matches)
        
        return dict(standards)

    def _check_material_contradictions(self) -> List[ConsistencyIssue]:
        """Check for contradictory material specifications"""
        issues = []
        material_usage = defaultdict(list)
        
        # Collect all material mentions by section
        for chapter in self.chapters:
            section_id = chapter.get('chapter_number', 'Unknown')
            content = chapter.get('content', '')
            title = chapter.get('title', '')
            materials = self._extract_materials_mentioned(content)
            
            for material in materials:
                material_usage[material].append({
                    'section_id': section_id,
                    'title': title,
                    'content_snippet': content[:200]
                })
        
        # Look for conflicting specifications for the same element
        for section_id, section_data in self.section_index.items():
            content = section_data['content']
            title = section_data['title']
            
            # Check for multiple contradictory materials for same element
            if any(word in content.lower() for word in ['vloer', 'floor', 'wand', 'wall']):
                materials_in_section = self._extract_materials_mentioned(content)
                
                # Check for incompatible material combinations
                incompatible_combinations = [
                    (['steel', 'aluminum'], "Steel and aluminum should not be in direct contact due to galvanic corrosion"),
                    (['wood', 'concrete'], "Direct wood-concrete contact requires moisture barriers"),
                    (['pvc', 'steel'], "PVC and steel expansion rates differ significantly")
                ]
                
                for incompatible_materials, reason in incompatible_combinations:
                    if all(mat in materials_in_section for mat in incompatible_materials):
                        issues.append(ConsistencyIssue(
                            issue_type="material_incompatibility",
                            severity="major",
                            description=f"Potentially incompatible materials specified: {', '.join(incompatible_materials)}",
                            sections_involved=[section_id],
                            conflicting_content=[f"{title}: {reason}"],
                            suggested_resolution=f"Review material compatibility. {reason}",
                            confidence=0.7
                        ))
        
        return issues

    def _check_measurement_inconsistencies(self) -> List[ConsistencyIssue]:
        """Check for inconsistent measurements across sections"""
        issues = []
        global_measurements = defaultdict(list)
        
        # Collect measurements by type and context
        for chapter in self.chapters:
            section_id = chapter.get('chapter_number', 'Unknown')
            content = chapter.get('content', '')
            title = chapter.get('title', '')
            measurements = self._extract_measurements(content)
            
            for measure_type, values in measurements.items():
                for value in values:
                    global_measurements[measure_type].append({
                        'value': value,
                        'section_id': section_id,
                        'title': title,
                        'context': content[:300]
                    })
        
        # Check for unrealistic or contradictory measurements
        for measure_type, measurements in global_measurements.items():
            if len(measurements) > 1:
                values = [m['value'] for m in measurements]
                
                # Check for extreme outliers
                if len(values) >= 3:
                    values_sorted = sorted(values)
                    median = values_sorted[len(values_sorted) // 2]
                    
                    for measurement in measurements:
                        value = measurement['value']
                        
                        # Flag values that are extremely different from median
                        if value > median * 10 or value < median / 10:
                            issues.append(ConsistencyIssue(
                                issue_type="measurement_outlier",
                                severity="minor",
                                description=f"Unusual {measure_type} measurement: {value} (median: {median})",
                                sections_involved=[measurement['section_id']],
                                conflicting_content=[f"{measurement['title']}: {value}"],
                                suggested_resolution="Verify measurement accuracy and units",
                                confidence=0.6
                            ))
                
                # Check for impossible dimensions
                if measure_type == 'thickness':
                    for measurement in measurements:
                        value = measurement['value']
                        if value > 1000:  # thickness > 1m seems unusual
                            issues.append(ConsistencyIssue(
                                issue_type="unrealistic_measurement",
                                severity="major",
                                description=f"Unusually thick specification: {value}mm",
                                sections_involved=[measurement['section_id']],
                                conflicting_content=[measurement['context']],
                                suggested_resolution="Check if measurement is in correct units (mm vs cm vs m)",
                                confidence=0.8
                            ))
        
        return issues

    def _check_specification_conflicts(self) -> List[ConsistencyIssue]:
        """Check for conflicting specifications across sections"""
        issues = []
        
        # Look for conflicting quality standards
        standard_specifications = defaultdict(list)
        
        for chapter in self.chapters:
            section_id = chapter.get('chapter_number', 'Unknown')
            content = chapter.get('content', '')
            title = chapter.get('title', '')
            standards = self._extract_quality_standards(content)
            
            for standard_type, values in standards.items():
                for value in values:
                    standard_specifications[standard_type].append({
                        'value': value,
                        'section_id': section_id,
                        'title': title,
                        'content': content[:200]
                    })
        
        # Check for conflicting standards of the same type
        for standard_type, specifications in standard_specifications.items():
            if len(specifications) > 1:
                unique_values = set(spec['value'] for spec in specifications)
                
                if len(unique_values) > 1:
                    # Multiple different standards specified
                    sections_involved = [spec['section_id'] for spec in specifications]
                    conflicting_content = [f"{spec['title']}: {spec['value']}" for spec in specifications]
                    
                    issues.append(ConsistencyIssue(
                        issue_type="conflicting_standards",
                        severity="major",
                        description=f"Conflicting {standard_type} standards: {', '.join(unique_values)}",
                        sections_involved=sections_involved,
                        conflicting_content=conflicting_content,
                        suggested_resolution="Standardize specifications across document or clarify where different standards apply",
                        confidence=0.9
                    ))
        
        return issues

    def _check_logical_inconsistencies(self) -> List[ConsistencyIssue]:
        """Check for logical inconsistencies in content"""
        issues = []
        
        # Check for contradictory statements
        contradiction_pairs = [
            (['waterbestendig', 'water resistant'], ['niet waterbestendig', 'not water resistant']),
            (['brandbestendig', 'fire resistant'], ['brandbaar', 'flammable']),
            (['isolerend', 'insulating'], ['geleidend', 'conductive']),
            (['flexibel', 'flexible'], ['stijf', 'rigid', 'stiff']),
            (['permanent', 'definitief'], ['tijdelijk', 'temporary']),
            (['binnen', 'indoor', 'interior'], ['buiten', 'outdoor', 'exterior'])
        ]
        
        for chapter in self.chapters:
            section_id = chapter.get('chapter_number', 'Unknown')
            content = chapter.get('content', '').lower()
            title = chapter.get('title', '')
            
            for positive_terms, negative_terms in contradiction_pairs:
                has_positive = any(term in content for term in positive_terms)
                has_negative = any(term in content for term in negative_terms)
                
                if has_positive and has_negative:
                    positive_found = [term for term in positive_terms if term in content]
                    negative_found = [term for term in negative_terms if term in content]
                    
                    issues.append(ConsistencyIssue(
                        issue_type="logical_contradiction",
                        severity="major",
                        description=f"Contradictory properties specified: {positive_found[0]} vs {negative_found[0]}",
                        sections_involved=[section_id],
                        conflicting_content=[f"{title}: Contains both '{positive_found[0]}' and '{negative_found[0]}'"],
                        suggested_resolution="Clarify which property applies or if they apply to different elements",
                        confidence=0.8
                    ))
        
        return issues

    def _check_duplicate_or_conflicting_sections(self) -> List[ConsistencyIssue]:
        """Check for duplicate or conflicting section content"""
        issues = []
        
        # Compare sections for similarity and conflicts
        for i, chapter1 in enumerate(self.chapters):
            for j, chapter2 in enumerate(self.chapters[i+1:], i+1):
                section1_id = chapter1.get('chapter_number', f'section_{i}')
                section2_id = chapter2.get('chapter_number', f'section_{j}')
                
                content1 = chapter1.get('content', '').strip()
                content2 = chapter2.get('content', '').strip()
                
                title1 = chapter1.get('title', '')
                title2 = chapter2.get('title', '')
                
                if not content1 or not content2:
                    continue
                
                # Check for very similar content (potential duplicates)
                similarity = difflib.SequenceMatcher(None, content1, content2).ratio()
                
                if similarity > 0.8:
                    issues.append(ConsistencyIssue(
                        issue_type="duplicate_content",
                        severity="minor",
                        description=f"Very similar content found (similarity: {similarity:.2f})",
                        sections_involved=[section1_id, section2_id],
                        conflicting_content=[f"{title1} vs {title2}"],
                        suggested_resolution="Check if content is intentionally repeated or if consolidation is needed",
                        confidence=similarity
                    ))
                
                # Check for similar titles but different content (potential conflicts)
                title_similarity = difflib.SequenceMatcher(None, title1.lower(), title2.lower()).ratio()
                
                if title_similarity > 0.7 and similarity < 0.3:
                    issues.append(ConsistencyIssue(
                        issue_type="conflicting_similar_sections",
                        severity="major", 
                        description=f"Similar titles but different content (title similarity: {title_similarity:.2f})",
                        sections_involved=[section1_id, section2_id],
                        conflicting_content=[f"{title1} vs {title2}"],
                        suggested_resolution="Review if both sections are needed or if they should be merged",
                        confidence=title_similarity
                    ))
        
        return issues

    def analyze_document_consistency(self) -> List[ConsistencyIssue]:
        """Perform comprehensive consistency analysis"""
        if self.verbose:
            print("Analyzing document consistency...")
        
        all_issues = []
        
        # Run all consistency checks
        consistency_checks = [
            ("Material Contradictions", self._check_material_contradictions),
            ("Measurement Inconsistencies", self._check_measurement_inconsistencies),
            ("Specification Conflicts", self._check_specification_conflicts),
            ("Logical Inconsistencies", self._check_logical_inconsistencies),
            ("Duplicate/Conflicting Sections", self._check_duplicate_or_conflicting_sections)
        ]
        
        for check_name, check_function in consistency_checks:
            if self.verbose:
                print(f"  Running {check_name}...")
            
            try:
                issues = check_function()
                all_issues.extend(issues)
                
                if self.verbose:
                    print(f"    Found {len(issues)} issues")
                    
            except Exception as e:
                if self.verbose:
                    print(f"    Error in {check_name}: {e}")
        
        # Sort issues by severity and confidence
        severity_order = {'critical': 0, 'major': 1, 'minor': 2}
        all_issues.sort(key=lambda x: (severity_order.get(x.severity, 3), -x.confidence))
        
        self.consistency_issues = all_issues
        return all_issues

    def generate_summary_format_report(self, issues: List[ConsistencyIssue]) -> List[Dict]:
        """Generate report in summary format compatible with HTML UI"""
        report = []
        
        # Group issues by severity for better organization
        critical_issues = [i for i in issues if i.severity == 'critical']
        major_issues = [i for i in issues if i.severity == 'major']
        minor_issues = [i for i in issues if i.severity == 'minor']
        
        # Create summary sections
        if critical_issues or major_issues or minor_issues:
            # Overall summary
            report.append({
                "level": 1,
                "title": "Document Consistency Analysis Summary",
                "start_page": 1,
                "end_page": max([chapter.get('end_page', 1) for chapter in self.chapters]) if self.chapters else 1,
                "summary": f"Found {len(issues)} consistency issues: {len(critical_issues)} critical, {len(major_issues)} major, {len(minor_issues)} minor. Document requires review for internal contradictions, conflicting specifications, and logical inconsistencies.",
                "issue_count": len(issues),
                "critical_count": len(critical_issues),
                "major_count": len(major_issues),
                "minor_count": len(minor_issues)
            })
            
            # Critical issues section
            if critical_issues:
                report.append({
                    "level": 2,
                    "title": "Critical Consistency Issues",
                    "start_page": 1,
                    "end_page": 1,
                    "summary": f"Found {len(critical_issues)} critical issues requiring immediate attention. These represent fundamental contradictions that could impact project execution.",
                    "issues": [self._format_issue_for_display(issue) for issue in critical_issues]
                })
            
            # Major issues section  
            if major_issues:
                report.append({
                    "level": 2,
                    "title": "Major Consistency Issues", 
                    "start_page": 1,
                    "end_page": 1,
                    "summary": f"Found {len(major_issues)} major issues that should be resolved. These represent significant contradictions or conflicting specifications.",
                    "issues": [self._format_issue_for_display(issue) for issue in major_issues]
                })
            
            # Minor issues section
            if minor_issues:
                report.append({
                    "level": 2,
                    "title": "Minor Consistency Issues",
                    "start_page": 1, 
                    "end_page": 1,
                    "summary": f"Found {len(minor_issues)} minor issues for review. These represent potential inconsistencies that may need clarification.",
                    "issues": [self._format_issue_for_display(issue) for issue in minor_issues]
                })
        else:
            # No issues found
            report.append({
                "level": 1,
                "title": "Document Consistency Analysis - Clean",
                "start_page": 1,
                "end_page": max([chapter.get('end_page', 1) for chapter in self.chapters]) if self.chapters else 1,
                "summary": "No significant consistency issues detected. The document appears to have internally consistent specifications and requirements."
            })
        
        return report

    def _format_issue_for_display(self, issue: ConsistencyIssue) -> Dict:
        """Format an issue for display in the UI"""
        return {
            "type": issue.issue_type,
            "severity": issue.severity,
            "description": issue.description,
            "sections": issue.sections_involved,
            "conflicts": issue.conflicting_content,
            "resolution": issue.suggested_resolution,
            "confidence": f"{issue.confidence:.2f}"
        }

def main():
    parser = argparse.ArgumentParser(description="Content Consistency Analyzer")
    parser.add_argument(
        "--ocr-data",
        default="ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json",
        help="Path to OCR chapters with text JSON file"
    )
    parser.add_argument(
        "--output",
        default="consistency_analysis.json",
        help="Output file for consistency analysis results"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        print(f"Loading document from: {args.ocr_data}")
        analyzer = ContentConsistencyAnalyzer(args.ocr_data, args.verbose)
        
        print("Analyzing document for consistency issues...")
        issues = analyzer.analyze_document_consistency()
        
        # Generate report in summary format
        report = analyzer.generate_summary_format_report(issues)
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Print summary
        print(f"\nConsistency Analysis Complete!")
        print(f"Total issues found: {len(issues)}")
        
        if issues:
            # Count by severity
            severity_counts = {'critical': 0, 'major': 0, 'minor': 0}
            issue_type_counts = {}
            
            for issue in issues:
                severity_counts[issue.severity] += 1
                issue_type_counts[issue.issue_type] = issue_type_counts.get(issue.issue_type, 0) + 1
            
            print(f"By severity:")
            print(f"  Critical: {severity_counts['critical']}")
            print(f"  Major: {severity_counts['major']}")
            print(f"  Minor: {severity_counts['minor']}")
            
            print(f"\nBy type:")
            for issue_type, count in sorted(issue_type_counts.items()):
                print(f"  {issue_type}: {count}")
            
            if args.verbose:
                print(f"\nTop issues:")
                for issue in issues[:5]:
                    print(f"  [{issue.severity.upper()}] {issue.description}")
                    print(f"    Sections: {', '.join(issue.sections_involved)}")
                    print(f"    Resolution: {issue.suggested_resolution}")
                    print()
        else:
            print("No consistency issues detected!")
        
        print(f"Results saved to: {args.output}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()