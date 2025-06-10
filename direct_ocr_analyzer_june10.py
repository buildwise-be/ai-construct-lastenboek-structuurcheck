#!/usr/bin/env python3
"""
Direct OCR Analyzer - June 10th
Analyzes OCR content directly without needing external tasks
"""

import json
import argparse
import sys

def load_ocr_data(file_path):
    """Load OCR data and convert to analyzable format"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    sections = []
    for section_id, section_info in data.items():
        sections.append({
            'id': section_id,
            'title': section_info.get('title', '') or '',
            'content': section_info.get('text', '') or '',
            'char_count': section_info.get('character_count', 0)
        })
    
    return sections

def analyze_content_issues(sections, verbose=False):
    """Analyze sections for content placement issues"""
    issues = []
    
    # Content type keywords
    keywords = {
        'electrical': ['electrical', 'elektriciteit', 'outlet', 'wiring', 'lighting'],
        'plumbing': ['plumbing', 'sanitair', 'water', 'pipe', 'toilet'],
        'hvac': ['heating', 'ventilation', 'hvac', 'verwarming'],
        'structural': ['concrete', 'steel', 'foundation', 'beton'],
        'finishing': ['paint', 'tile', 'afwerking', 'vloer']
    }
    
    for i, section in enumerate(sections):
        if verbose and i % 100 == 0:
            print(f"Analyzing section {i+1}/{len(sections)}")
        
        content = section['content'].lower()
        title = section['title'].lower()
        
        if not content.strip():
            if title:  # Has title but no content
                issues.append({
                    'section_id': section['id'],
                    'title': section['title'],
                    'issue': 'empty_section',
                    'severity': 'low',
                    'description': 'Section has title but no content'
                })
            continue
        
        # Find dominant content type
        content_scores = {}
        for content_type, word_list in keywords.items():
            score = sum(content.count(word) for word in word_list)
            if score > 0:
                content_scores[content_type] = score
        
        if not content_scores:
            continue  # No specific content detected
        
        # Get top content type
        top_content = max(content_scores, key=content_scores.get)
        
        # Check if title matches content
        title_matches = any(word in title for word in keywords[top_content])
        
        if not title_matches and content_scores[top_content] > 2:
            # Content doesn't match title
            issues.append({
                'section_id': section['id'], 
                'title': section['title'],
                'issue': 'content_mismatch',
                'severity': 'medium',
                'description': f'Contains {top_content} content but title suggests otherwise',
                'content_type_found': top_content,
                'content_sample': section['content'][:200]
            })
    
    return issues

def main():
    parser = argparse.ArgumentParser(description="Direct OCR Content Analyzer")
    parser.add_argument("--ocr-data", 
                       default="ocroutput/pipeline_run_20250610_094433_Anoniem_Lastenboek/final_combined_output/chapters_with_text_v3.json")
    parser.add_argument("--output", default="direct_analysis_june10.json")
    parser.add_argument("--verbose", action="store_true")
    
    args = parser.parse_args()
    
    try:
        print(f"Loading: {args.ocr_data}")
        sections = load_ocr_data(args.ocr_data)
        print(f"Loaded {len(sections)} sections")
        
        print("Analyzing content...")
        issues = analyze_content_issues(sections, args.verbose)
        
        # Create report
        report = {
            "summary": f"Analyzed {len(sections)} sections, found {len(issues)} issues",
            "total_sections": len(sections),
            "total_issues": len(issues),
            "issues": issues
        }
        
        # Save results
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\nRESULTS:")
        print(f"Sections analyzed: {len(sections)}")
        print(f"Issues found: {len(issues)}")
        print(f"Saved to: {args.output}")
        
        # Show issue breakdown
        if issues:
            issue_types = {}
            for issue in issues:
                issue_type = issue['issue']
                issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
            
            print(f"\nIssue types:")
            for issue_type, count in issue_types.items():
                print(f"  {issue_type}: {count}")
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 