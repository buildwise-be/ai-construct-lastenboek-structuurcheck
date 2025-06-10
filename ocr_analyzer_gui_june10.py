#!/usr/bin/env python3
"""
OCR Analyzer GUI - June 10th
Simple GUI for analyzing OCR content with file selection
"""

import json
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import threading
from datetime import datetime

class OCRAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OCR Content Analyzer - June 10th")
        self.root.geometry("800x600")
        
        # Default OCR file path
        self.default_ocr_path = "ocroutput/pipeline_run_20250610_094433_Anoniem_Lastenboek/final_combined_output/chapters_with_text_v3.json"
        self.selected_file = self.default_ocr_path
        
        self.setup_ui()
        
    def setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="OCR Content Placement Analyzer", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # File selection
        ttk.Label(main_frame, text="OCR Data File:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.file_var = tk.StringVar(value=self.selected_file)
        file_entry = ttk.Entry(main_frame, textvariable=self.file_var, width=60)
        file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 5))
        
        browse_btn = ttk.Button(main_frame, text="Browse", command=self.browse_file)
        browse_btn.grid(row=1, column=2, pady=5)
        
        # Quick select buttons for common files
        quick_frame = ttk.LabelFrame(main_frame, text="Quick Select", padding="5")
        quick_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        quick_frame.columnconfigure(0, weight=1)
        quick_frame.columnconfigure(1, weight=1)
        
        anoniem_btn = ttk.Button(quick_frame, text="Anoniem Lastenboek", 
                                command=lambda: self.set_file(self.default_ocr_path))
        anoniem_btn.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        cathlab_btn = ttk.Button(quick_frame, text="Cathlab Project", 
                                command=lambda: self.set_file("ocroutput/pipeline_run_20250605_112516_cathlabarchitectlb/final_combined_output/chapters_with_text_v3.json"))
        cathlab_btn.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        # Control buttons
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=3, column=0, columnspan=3, pady=20)
        
        self.analyze_btn = ttk.Button(control_frame, text="Analyze OCR Content", 
                                     command=self.run_analysis, style="Accent.TButton")
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_btn = ttk.Button(control_frame, text="Save Results", 
                                  command=self.save_results, state="disabled")
        self.save_btn.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        self.progress.grid_remove()  # Hide initially
        
        # Results area
        results_frame = ttk.LabelFrame(main_frame, text="Analysis Results", padding="5")
        results_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, 
                                                     width=80, height=20, state=tk.DISABLED)
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready to analyze OCR content")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, 
                                relief=tk.SUNKEN, anchor=tk.W)
        status_label.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 0))
        
        self.results_data = None
        
    def set_file(self, file_path):
        """Set the selected file path"""
        self.selected_file = file_path
        self.file_var.set(file_path)
        
    def browse_file(self):
        """Open file browser to select OCR file"""
        filename = filedialog.askopenfilename(
            title="Select OCR Chapters File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="ocroutput"
        )
        if filename:
            self.set_file(filename)
            
    def load_ocr_data(self, file_path):
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

    def analyze_content_issues(self, sections):
        """Analyze sections for content placement issues"""
        issues = []
        
        # Content type keywords
        keywords = {
            'electrical': ['electrical', 'elektriciteit', 'outlet', 'wiring', 'lighting', 'verlichting'],
            'plumbing': ['plumbing', 'sanitair', 'water', 'pipe', 'toilet', 'badkamer'],
            'hvac': ['heating', 'ventilation', 'hvac', 'verwarming', 'klimaat', 'airco'],
            'structural': ['concrete', 'steel', 'foundation', 'beton', 'staal', 'fundering'],
            'finishing': ['paint', 'tile', 'afwerking', 'vloer', 'tegels', 'verf'],
            'demolition': ['demolition', 'afbraak', 'slopen', 'uitbreken', 'remove']
        }
        
        total = len(sections)
        for i, section in enumerate(sections):
            # Update progress in status
            if i % 20 == 0:
                progress_pct = int((i / total) * 100)
                self.status_var.set(f"Analyzing section {i+1}/{total} ({progress_pct}%)")
                self.root.update_idletasks()
            
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

    def run_analysis(self):
        """Run the analysis in a separate thread"""
        if not os.path.exists(self.file_var.get()):
            messagebox.showerror("Error", f"File not found: {self.file_var.get()}")
            return
            
        # Disable button and show progress
        self.analyze_btn.config(state="disabled")
        self.progress.grid()
        self.progress.start(10)
        
        # Clear previous results
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state=tk.DISABLED)
        
        # Start analysis in thread
        thread = threading.Thread(target=self._analyze_worker)
        thread.daemon = True
        thread.start()
        
    def _analyze_worker(self):
        """Worker function for analysis (runs in separate thread)"""
        try:
            self.status_var.set("Loading OCR data...")
            sections = self.load_ocr_data(self.file_var.get())
            
            self.status_var.set(f"Analyzing {len(sections)} sections...")
            issues = self.analyze_content_issues(sections)
            
            # Create report
            report = {
                "summary": f"Analyzed {len(sections)} sections, found {len(issues)} issues",
                "total_sections": len(sections),
                "total_issues": len(issues),
                "issues": issues,
                "analysis_time": datetime.now().isoformat(),
                "source_file": self.file_var.get()
            }
            
            self.results_data = report
            
            # Update UI (must be done in main thread)
            self.root.after(0, self._update_results, report)
            
        except Exception as e:
            self.root.after(0, self._show_error, str(e))
    
    def _update_results(self, report):
        """Update results display (called in main thread)"""
        # Stop progress bar
        self.progress.stop()
        self.progress.grid_remove()
        self.analyze_btn.config(state="normal")
        self.save_btn.config(state="normal")
        
        # Display results
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        # Summary
        self.results_text.insert(tk.END, "="*60 + "\n")
        self.results_text.insert(tk.END, "OCR CONTENT ANALYSIS RESULTS\n")
        self.results_text.insert(tk.END, "="*60 + "\n\n")
        
        self.results_text.insert(tk.END, f"File analyzed: {report['source_file']}\n")
        self.results_text.insert(tk.END, f"Total sections: {report['total_sections']}\n")
        self.results_text.insert(tk.END, f"Issues found: {report['total_issues']}\n")
        self.results_text.insert(tk.END, f"Analysis time: {report['analysis_time']}\n\n")
        
        if report['issues']:
            # Issue breakdown
            issue_types = {}
            for issue in report['issues']:
                issue_type = issue['issue']
                issue_types[issue_type] = issue_types.get(issue_type, 0) + 1
            
            self.results_text.insert(tk.END, "Issue types found:\n")
            for issue_type, count in issue_types.items():
                self.results_text.insert(tk.END, f"  • {issue_type}: {count}\n")
            
            self.results_text.insert(tk.END, "\n" + "-"*50 + "\n")
            self.results_text.insert(tk.END, "DETAILED ISSUES:\n")
            self.results_text.insert(tk.END, "-"*50 + "\n\n")
            
            # Show first 10 issues in detail
            for i, issue in enumerate(report['issues'][:10]):
                self.results_text.insert(tk.END, f"Issue #{i+1}:\n")
                self.results_text.insert(tk.END, f"  Section: {issue['section_id']} - {issue['title']}\n")
                self.results_text.insert(tk.END, f"  Type: {issue['issue']} ({issue['severity']} severity)\n")
                self.results_text.insert(tk.END, f"  Description: {issue['description']}\n")
                if 'content_type_found' in issue:
                    self.results_text.insert(tk.END, f"  Content type detected: {issue['content_type_found']}\n")
                self.results_text.insert(tk.END, "\n")
            
            if len(report['issues']) > 10:
                self.results_text.insert(tk.END, f"... and {len(report['issues']) - 10} more issues\n")
                self.results_text.insert(tk.END, "(Save results to see all issues)\n")
        else:
            self.results_text.insert(tk.END, "No content placement issues detected!\n")
        
        self.results_text.config(state=tk.DISABLED)
        self.status_var.set(f"Analysis complete - {report['total_issues']} issues found")
    
    def _show_error(self, error_msg):
        """Show error message (called in main thread)"""
        self.progress.stop()
        self.progress.grid_remove()
        self.analyze_btn.config(state="normal")
        self.status_var.set("Error occurred during analysis")
        messagebox.showerror("Analysis Error", f"Error during analysis:\n{error_msg}")
    
    def save_results(self):
        """Save analysis results to file"""
        if not self.results_data:
            messagebox.showwarning("Warning", "No results to save")
            return
        
        filename = filedialog.asksaveasfilename(
            title="Save Analysis Results",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"ocr_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.results_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Success", f"Results saved to:\n{filename}")
                self.status_var.set(f"Results saved to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save results:\n{e}")

def main():
    root = tk.Tk()
    app = OCRAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main() 