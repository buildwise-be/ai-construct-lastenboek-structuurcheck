#!/usr/bin/env python3
"""
Output Format Comparison Script

This script demonstrates how the enhanced full content versions now match 
the output format of the vision-based summary approach.

Usage:
    python compare_output_formats.py [options]
"""

import json
import argparse
import sys
import os

def load_json_file(file_path):
    """Load a JSON file safely"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {file_path}: {e}")
        return None

def analyze_format_structure(data, source_name):
    """Analyze the structure of output data"""
    if not data:
        return {"error": "No data to analyze"}
    
    analysis = {
        "source": source_name,
        "data_type": type(data).__name__,
        "total_items": len(data) if isinstance(data, (list, dict)) else 0,
        "sample_fields": [],
        "format_type": "unknown"
    }
    
    if isinstance(data, list) and data:
        # List format (summary format)
        first_item = data[0]
        if isinstance(first_item, dict):
            analysis["sample_fields"] = list(first_item.keys())
            # Check if it matches summary format
            summary_fields = {"level", "title", "start_page", "end_page", "summary"}
            if summary_fields.issubset(set(first_item.keys())):
                analysis["format_type"] = "summary_format"
            else:
                analysis["format_type"] = "list_format"
    
    elif isinstance(data, dict):
        # Dictionary format
        if data:
            first_key = list(data.keys())[0]
            first_value = data[first_key]
            if isinstance(first_value, dict):
                analysis["sample_fields"] = list(first_value.keys())
                analysis["format_type"] = "dictionary_format"
    
    return analysis

def compare_formats(vision_data, enhanced_data, direct_data):
    """Compare the formats of different analysis outputs"""
    print("=" * 80)
    print("OUTPUT FORMAT COMPARISON")
    print("=" * 80)
    
    # Analyze each format
    vision_analysis = analyze_format_structure(vision_data, "Vision-based Summary")
    enhanced_analysis = analyze_format_structure(enhanced_data, "Enhanced Task Checker")
    direct_analysis = analyze_format_structure(direct_data, "Direct OCR Analyzer")
    
    analyses = [vision_analysis, enhanced_analysis, direct_analysis]
    
    # Print comparison table
    print("\nFORMAT OVERVIEW:")
    print("-" * 80)
    print(f"{'Source':<25} {'Type':<15} {'Items':<10} {'Format':<20}")
    print("-" * 80)
    
    for analysis in analyses:
        if "error" not in analysis:
            print(f"{analysis['source']:<25} {analysis['data_type']:<15} {analysis['total_items']:<10} {analysis['format_type']:<20}")
    
    print("\nFIELD COMPARISON:")
    print("-" * 80)
    
    # Get all unique fields
    all_fields = set()
    for analysis in analyses:
        if "sample_fields" in analysis:
            all_fields.update(analysis["sample_fields"])
    
    # Print field comparison
    print(f"{'Field':<25} {'Vision':<10} {'Enhanced':<10} {'Direct':<10}")
    print("-" * 80)
    
    vision_fields = set(vision_analysis.get("sample_fields", []))
    enhanced_fields = set(enhanced_analysis.get("sample_fields", []))
    direct_fields = set(direct_analysis.get("sample_fields", []))
    
    for field in sorted(all_fields):
        vision_has = "✓" if field in vision_fields else "✗"
        enhanced_has = "✓" if field in enhanced_fields else "✗"
        direct_has = "✓" if field in direct_fields else "✗"
        
        print(f"{field:<25} {vision_has:<10} {enhanced_has:<10} {direct_has:<10}")
    
    return analyses

def show_sample_outputs(vision_data, enhanced_data, direct_data):
    """Show sample outputs from each approach"""
    print("\n" + "=" * 80)
    print("SAMPLE OUTPUT COMPARISON")
    print("=" * 80)
    
    # Show first item from each
    if vision_data and isinstance(vision_data, list):
        print("\nVISION-BASED SUMMARY (First Item):")
        print("-" * 40)
        first_item = vision_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"{key}: {value}")
    
    if enhanced_data and isinstance(enhanced_data, list):
        print("\nENHANCED TASK CHECKER (First Item):")
        print("-" * 40)
        first_item = enhanced_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            elif isinstance(value, list) and len(value) > 3:
                value = f"[{len(value)} items: {', '.join(map(str, value[:3]))}...]"
            print(f"{key}: {value}")
    
    if direct_data and isinstance(direct_data, list):
        print("\nDIRECT OCR ANALYZER (First Item):")
        print("-" * 40)
        first_item = direct_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            elif isinstance(value, list) and len(value) > 3:
                value = f"[{len(value)} items: {', '.join(map(str, value[:3]))}...]"
            print(f"{key}: {value}")

def check_format_compatibility(analyses):
    """Check how well the formats are aligned"""
    print("\n" + "=" * 80)
    print("FORMAT COMPATIBILITY ANALYSIS")
    print("=" * 80)
    
    # Check if all formats are summary format
    summary_format_count = sum(1 for a in analyses if a.get("format_type") == "summary_format")
    
    print(f"\nFormats using summary structure: {summary_format_count}/{len(analyses)}")
    
    # Check common fields
    if len(analyses) >= 2:
        vision_fields = set(analyses[0].get("sample_fields", []))
        enhanced_fields = set(analyses[1].get("sample_fields", [])) if len(analyses) > 1 else set()
        direct_fields = set(analyses[2].get("sample_fields", [])) if len(analyses) > 2 else set()
        
        # Core summary fields
        core_fields = {"level", "title", "start_page", "end_page", "summary"}
        
        print(f"\nCore summary fields present:")
        for i, analysis in enumerate(analyses):
            if "sample_fields" in analysis:
                fields = set(analysis["sample_fields"])
                present = core_fields.intersection(fields)
                missing = core_fields - fields
                print(f"  {analysis['source']}: {len(present)}/{len(core_fields)} core fields")
                if missing:
                    print(f"    Missing: {', '.join(missing)}")
        
        # Enhanced fields (specific to full content approaches)
        enhanced_fields_set = {"section_id", "content_type", "confidence", "issues", "suggested_improvements"}
        
        print(f"\nEnhanced analysis fields:")
        for i, analysis in enumerate(analyses):
            if "sample_fields" in analysis:
                fields = set(analysis["sample_fields"])
                present = enhanced_fields_set.intersection(fields)
                print(f"  {analysis['source']}: {len(present)}/{len(enhanced_fields_set)} enhanced fields")
                if present:
                    print(f"    Present: {', '.join(present)}")

def main():
    parser = argparse.ArgumentParser(description="Compare output formats between different analysis approaches")
    parser.add_argument("--vision-output", 
                       default="summarized_toc.json",
                       help="Path to vision-based summary output")
    parser.add_argument("--enhanced-output",
                       default="enhanced_placement_analysis.json", 
                       help="Path to enhanced task checker output")
    parser.add_argument("--direct-output",
                       default="direct_analysis_enhanced.json",
                       help="Path to direct OCR analyzer output")
    parser.add_argument("--consistency-output",
                       default="consistency_analysis.json",
                       help="Path to consistency analyzer output")
    parser.add_argument("--show-samples",
                       action="store_true",
                       help="Show sample outputs from each approach")
    
    args = parser.parse_args()
    
    print("Loading output files...")
    
    # Load output files
    vision_data = load_json_file(args.vision_output)
    enhanced_data = load_json_file(args.enhanced_output)
    direct_data = load_json_file(args.direct_output)
    consistency_data = load_json_file(args.consistency_output)
    
    # Check if any files were loaded
    if not any([vision_data, enhanced_data, direct_data, consistency_data]):
        print("Error: No valid output files found. Please run the analysis tools first.")
        print("\nTo generate sample outputs, run:")
        print("  python toc_summarizer.py input.pdf")
        print("  python enhanced_task_checker.py")
        print("  python direct_ocr_analyzer_june10.py")
        print("  python content_consistency_analyzer.py")
        sys.exit(1)
    
    # Compare formats including consistency analyzer
    analyses = compare_formats_extended(vision_data, enhanced_data, direct_data, consistency_data)
    
    # Show sample outputs if requested
    if args.show_samples:
        show_sample_outputs_extended(vision_data, enhanced_data, direct_data, consistency_data)
    
    # Check compatibility
    check_format_compatibility(analyses)
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("\nAll analysis approaches now output in the same format")
    print("as the vision-based summary approach, with specialized fields for")
    print("different types of analysis. This provides:")
    print("  • Consistent data structure across all approaches")
    print("  • Same visual presentation capabilities")
    print("  • Enhanced analysis from full text content")
    print("  • Consistency checking for document conflicts")
    print("  • Backward compatibility with existing tools")

def compare_formats_extended(vision_data, enhanced_data, direct_data, consistency_data):
    """Compare the formats of all analysis outputs including consistency analyzer"""
    print("=" * 80)
    print("OUTPUT FORMAT COMPARISON")
    print("=" * 80)
    
    # Analyze each format
    vision_analysis = analyze_format_structure(vision_data, "Vision-based Summary")
    enhanced_analysis = analyze_format_structure(enhanced_data, "Enhanced Task Checker")
    direct_analysis = analyze_format_structure(direct_data, "Direct OCR Analyzer")
    consistency_analysis = analyze_format_structure(consistency_data, "Consistency Analyzer")
    
    analyses = [vision_analysis, enhanced_analysis, direct_analysis, consistency_analysis]
    
    # Print comparison table
    print("\nFORMAT OVERVIEW:")
    print("-" * 80)
    print(f"{'Source':<25} {'Type':<15} {'Items':<10} {'Format':<20}")
    print("-" * 80)
    
    for analysis in analyses:
        if "error" not in analysis:
            print(f"{analysis['source']:<25} {analysis['data_type']:<15} {analysis['total_items']:<10} {analysis['format_type']:<20}")
    
    print("\nFIELD COMPARISON:")
    print("-" * 80)
    
    # Get all unique fields
    all_fields = set()
    for analysis in analyses:
        if "sample_fields" in analysis:
            all_fields.update(analysis["sample_fields"])
    
    # Print field comparison
    print(f"{'Field':<25} {'Vision':<10} {'Enhanced':<10} {'Direct':<10} {'Consistency':<12}")
    print("-" * 80)
    
    vision_fields = set(vision_analysis.get("sample_fields", []))
    enhanced_fields = set(enhanced_analysis.get("sample_fields", []))
    direct_fields = set(direct_analysis.get("sample_fields", []))
    consistency_fields = set(consistency_analysis.get("sample_fields", []))
    
    for field in sorted(all_fields):
        vision_has = "✓" if field in vision_fields else "✗"
        enhanced_has = "✓" if field in enhanced_fields else "✗"
        direct_has = "✓" if field in direct_fields else "✗"
        consistency_has = "✓" if field in consistency_fields else "✗"
        
        print(f"{field:<25} {vision_has:<10} {enhanced_has:<10} {direct_has:<10} {consistency_has:<12}")
    
    return analyses

def show_sample_outputs_extended(vision_data, enhanced_data, direct_data, consistency_data):
    """Show sample outputs from all approaches"""
    print("\n" + "=" * 80)
    print("SAMPLE OUTPUT COMPARISON")
    print("=" * 80)
    
    # Show first item from each
    if vision_data and isinstance(vision_data, list):
        print("\nVISION-BASED SUMMARY (First Item):")
        print("-" * 40)
        first_item = vision_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"{key}: {value}")
    
    if enhanced_data and isinstance(enhanced_data, list):
        print("\nENHANCED TASK CHECKER (First Item):")
        print("-" * 40)
        first_item = enhanced_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            elif isinstance(value, list) and len(value) > 3:
                value = f"[{len(value)} items: {', '.join(map(str, value[:3]))}...]"
            print(f"{key}: {value}")
    
    if direct_data and isinstance(direct_data, list):
        print("\nDIRECT OCR ANALYZER (First Item):")
        print("-" * 40)
        first_item = direct_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            elif isinstance(value, list) and len(value) > 3:
                value = f"[{len(value)} items: {', '.join(map(str, value[:3]))}...]"
            print(f"{key}: {value}")
    
    if consistency_data and isinstance(consistency_data, list):
        print("\nCONSISTENCY ANALYZER (First Item):")
        print("-" * 40)
        first_item = consistency_data[0]
        for key, value in first_item.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            elif isinstance(value, list) and len(value) > 3:
                value = f"[{len(value)} items: {', '.join(map(str, value[:3]))}...]"
            print(f"{key}: {value}")

if __name__ == "__main__":
    main()