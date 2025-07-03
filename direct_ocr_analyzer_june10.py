#!/usr/bin/env python3
"""
Direct OCR Analyzer - June 10th - Updated to Mirror Summary Format
Analyzes OCR content directly without needing external tasks
Now outputs in the same format as the vision-based approach.
"""

import json
import argparse
import sys
import re
from typing import Dict, List, Any, Tuple

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
            'start_page': section_info.get('start_page', 1),
            'end_page': section_info.get('end_page', 1),
            'char_count': section_info.get('character_count', 0)
        })
    
    return sections

def determine_section_level(section_id: str, title: str) -> int:
    """Determine the hierarchical level of a section"""
    # Parse section number to determine level
    if not section_id or section_id == 'Unknown':
        return 1
    
    # Count dots in section number
    dot_count = section_id.count('.')
    
    # Check title for level indicators
    title_lower = title.lower()
    if any(word in title_lower for word in ['hoofdstuk', 'chapter', 'deel', 'regie', 'voorwerp']):
        return 1
    elif any(word in title_lower for word in ['sectie', 'section', 'aard van']):
        return 2
    elif dot_count == 0:
        return 1
    elif dot_count == 1:
        return 2
    else:
        return 3

def classify_content_type(content: str, title: str) -> Tuple[str, float]:
    """Classify content type based on text analysis"""
    content_lower = content.lower()
    title_lower = title.lower()
    combined_text = content_lower + " " + title_lower
    
    # Enhanced content type patterns
    content_patterns = {
        'administrative': {
            'keywords': [
                r'permit', r'license', r'approval', r'documentation', r'contract',
                r'admin', r'legal', r'insurance', r'safety plan', r'coordination',
                r'voorschrift', r'vergunning', r'goedkeuring', r'documentatie',
                r'overeenkomst', r'veiligheid', r'regie'
            ]
        },
        'demolition': {
            'keywords': [
                r'demolit', r'remove', r'strip', r'break out', r'clear',
                r'dismantle', r'tear down', r'opbreken', r'slopen', r'verwijderen',
                r'uiteennemen', r'uitnemen'
            ]
        },
        'structural': {
            'keywords': [
                r'concrete', r'steel', r'beam', r'column', r'foundation',
                r'structural', r'reinforc', r'load bearing', r'beton', r'staal',
                r'funderingen', r'constructie', r'draagconstructie'
            ]
        },
        'hvac': {
            'keywords': [
                r'heating', r'ventilation', r'air conditioning', r'hvac',
                r'ductwork', r'climate', r'temperature control', r'verwarming',
                r'ventilatie', r'klimaat', r'luchtkanaleen'
            ]
        },
        'electrical': {
            'keywords': [
                r'electrical', r'wiring', r'power', r'lighting', r'outlet',
                r'circuit', r'panel', r'voltage', r'elektrisch', r'bedrading',
                r'verlichting', r'elektriciteit'
            ]
        },
        'plumbing': {
            'keywords': [
                r'plumbing', r'water', r'drain', r'pipe', r'faucet',
                r'toilet', r'sink', r'sewer', r'sanitair', r'riolering',
                r'leidingen', r'afvoer'
            ]
        },
        'finishes': {
            'keywords': [
                r'paint', r'tile', r'flooring', r'ceiling', r'wall finish',
                r'carpet', r'trim', r'molding', r'verf', r'tegels',
                r'vloerbedekking', r'afwerking', r'estrade', r'dekvloer'
            ]
        },
        'site_preparation': {
            'keywords': [
                r'site', r'werf', r'aankondiging', r'bescherming', r'omheining',
                r'signalisatie', r'bebakening', r'plaatsbeschrijving',
                r'werfcondities', r'nazorg'
            ]
        }
    }
    
    best_match = 'general'
    best_score = 0.0
    
    for category, data in content_patterns.items():
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

def generate_enhanced_summary(content: str, title: str, content_type: str) -> str:
    """Generate enhanced summary with execution details"""
    if not content.strip():
        return "No content available for analysis."
    
    # Extract key execution details
    content_lower = content.lower()
    execution_details = []
    
    # Look for specific execution patterns
    if 'must' in content_lower or 'shall' in content_lower or 'required' in content_lower or 'moet' in content_lower:
        execution_details.append("Contains mandatory requirements")
    
    if any(word in content_lower for word in ['material', 'equipment', 'tool', 'materiaal', 'gereedschap']):
        execution_details.append("Specifies materials or equipment")
    
    if any(word in content_lower for word in ['method', 'procedure', 'process', 'methode', 'werkwijze']):
        execution_details.append("Describes execution methods")
    
    if any(word in content_lower for word in ['quality', 'standard', 'specification', 'kwaliteit', 'norm']):
        execution_details.append("Includes quality standards")
    
    if any(word in content_lower for word in ['safety', 'protect', 'veiligheid', 'bescherm']):
        execution_details.append("Contains safety requirements")
    
    # Create summary based on content type
    summary_parts = []
    
    if content_type == 'administrative':
        summary_parts.append("Administrative requirements and project coordination")
    elif content_type == 'demolition':
        summary_parts.append("Demolition and removal work")
    elif content_type == 'structural':
        summary_parts.append("Structural construction work")
    elif content_type == 'electrical':
        summary_parts.append("Electrical installation work")
    elif content_type == 'plumbing':
        summary_parts.append("Plumbing and sanitary work")
    elif content_type == 'hvac':
        summary_parts.append("HVAC installation work")
    elif content_type == 'finishes':
        summary_parts.append("Finishing and flooring work")
    elif content_type == 'site_preparation':
        summary_parts.append("Site preparation and organization")
    else:
        summary_parts.append("General construction work")
    
    # Add execution details
    if execution_details:
        summary_parts.extend(execution_details)
    
    # Add content snippet for context
    content_snippet = content[:300].strip()
    if content_snippet:
        # Clean up the snippet
        lines = content_snippet.split('\n')
        first_meaningful_line = ""
        for line in lines:
            if line.strip() and len(line.strip()) > 10:
                first_meaningful_line = line.strip()
                break
        
        if first_meaningful_line:
            summary_parts.append(f"Key content: {first_meaningful_line}")
    
    return " - ".join(summary_parts)

def identify_content_issues(content: str, title: str, content_type: str) -> List[str]:
    """Identify potential issues in the section"""
    issues = []
    
    if not content.strip():
        issues.append("Empty or missing content")
        return issues
    
    content_lower = content.lower()
    
    # Check for very short content
    if len(content.strip()) < 50:
        issues.append("Very short content - may be incomplete")
    
    # Check for missing key information based on content type
    if content_type == 'demolition':
        if not any(word in content_lower for word in ['remove', 'break', 'demolish', 'verwijderen', 'slopen']):
            issues.append("Missing demolition action verbs")
    
    elif content_type == 'electrical':
        if not any(word in content_lower for word in ['install', 'connect', 'wire', 'installeren', 'aansluiten']):
            issues.append("Missing electrical installation details")
    
    elif content_type == 'plumbing':
        if not any(word in content_lower for word in ['pipe', 'connect', 'install', 'leiding', 'aansluiten']):
            issues.append("Missing plumbing installation details")
    
    # Check for repeated or duplicate content
    lines = content.split('\n')
    unique_lines = set()
    repeated_lines = 0
    for line in lines:
        if line.strip():
            if line.strip() in unique_lines:
                repeated_lines += 1
            else:
                unique_lines.add(line.strip())
    
    if repeated_lines > 3:
        issues.append("Contains repeated content")
    
    return issues

def suggest_improvements(content: str, title: str, content_type: str, issues: List[str]) -> List[str]:
    """Suggest improvements for the section"""
    suggestions = []
    
    if "Empty or missing content" in issues:
        suggestions.append("Add detailed content describing the work requirements")
    
    if "Very short content" in issues:
        suggestions.append("Expand content with more detailed specifications")
    
    if "Missing demolition action verbs" in issues:
        suggestions.append("Add specific demolition methods and procedures")
    
    if "Missing electrical installation details" in issues:
        suggestions.append("Include wiring specifications and connection details")
    
    if "Missing plumbing installation details" in issues:
        suggestions.append("Add pipe specifications and connection procedures")
    
    if "Contains repeated content" in issues:
        suggestions.append("Remove duplicate content and consolidate information")
    
    # Content-type specific suggestions
    if content_type == 'demolition':
        suggestions.append("Include safety procedures and debris disposal methods")
    elif content_type == 'structural':
        suggestions.append("Specify materials, connections, and load requirements")
    elif content_type == 'electrical':
        suggestions.append("Include safety standards and testing procedures")
    elif content_type == 'plumbing':
        suggestions.append("Add pressure testing and inspection requirements")
    elif content_type == 'site_preparation':
        suggestions.append("Include timeline and coordination requirements")
    
    return suggestions

def analyze_content_comprehensive(sections, verbose=False):
    """Analyze sections comprehensively and return in summary format"""
    analyzed_sections = []
    
    for i, section in enumerate(sections):
        if verbose and i % 100 == 0:
            print(f"Analyzing section {i+1}/{len(sections)}")
        
        section_id = section['id']
        title = section['title']
        content = section['content']
        start_page = section['start_page']
        end_page = section['end_page']
        
        # Determine level and content type
        level = determine_section_level(section_id, title)
        content_type, confidence = classify_content_type(content, title)
        
        # Generate enhanced summary
        summary = generate_enhanced_summary(content, title, content_type)
        
        # Identify issues and suggestions
        issues = identify_content_issues(content, title, content_type)
        suggestions = suggest_improvements(content, title, content_type, issues)
        
        # Create section analysis in summary format
        section_analysis = {
            "level": level,
            "title": title,
            "start_page": start_page,
            "end_page": end_page,
            "summary": summary,
            # Enhanced fields from full content analysis
            "section_id": section_id,
            "content_type": content_type,
            "confidence": confidence,
            "issues": issues,
            "suggested_improvements": suggestions,
            "character_count": len(content)
        }
        
        analyzed_sections.append(section_analysis)
    
    return analyzed_sections

def main():
    parser = argparse.ArgumentParser(description="Direct OCR Content Analyzer - Summary Format")
    parser.add_argument("--ocr-data", 
                       default="ocroutput/pipeline_run_20250610_094433_Anoniem_Lastenboek/final_combined_output/chapters_with_text_v3.json",
                       help="Path to OCR chapters with text JSON file")
    parser.add_argument("--output", default="direct_analysis_enhanced.json",
                       help="Output file for analysis results")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        print(f"Loading: {args.ocr_data}")
        sections = load_ocr_data(args.ocr_data)
        print(f"Loaded {len(sections)} sections")
        
        print("Analyzing content comprehensively...")
        analyzed_sections = analyze_content_comprehensive(sections, args.verbose)
        
        # Save results in summary format
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(analyzed_sections, f, indent=2, ensure_ascii=False)
        
        print(f"\nRESULTS:")
        print(f"Sections analyzed: {len(analyzed_sections)}")
        print(f"Saved to: {args.output}")
        
        # Show content type breakdown
        content_types = {}
        total_issues = 0
        
        for section in analyzed_sections:
            content_type = section['content_type']
            content_types[content_type] = content_types.get(content_type, 0) + 1
            total_issues += len(section.get('issues', []))
        
        print(f"\nContent types identified:")
        for content_type, count in sorted(content_types.items()):
            print(f"  {content_type}: {count}")
        
        print(f"\nTotal issues identified: {total_issues}")
        
        # Show level distribution
        level_counts = {}
        for section in analyzed_sections:
            level = section['level']
            level_counts[level] = level_counts.get(level, 0) + 1
        
        print(f"\nLevel distribution:")
        for level, count in sorted(level_counts.items()):
            print(f"  Level {level}: {count}")
        
        if args.verbose and analyzed_sections:
            print(f"\nFirst few sections:")
            for section in analyzed_sections[:3]:
                print(f"- {section['title']} (Level {section['level']})")
                print(f"  Type: {section['content_type']} (confidence: {section['confidence']:.2f})")
                print(f"  Summary: {section['summary'][:100]}...")
                if section['issues']:
                    print(f"  Issues: {', '.join(section['issues'])}")
                print()
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 