#!/usr/bin/env python3
"""
Documentation Setup Script

This script initializes a new documentation project using the enterprise documentation template.
It creates the directory structure, copies templates, and customizes them with project-specific information.

Usage:
    python setup_documentation.py --project-name "Your Project Name"
    python setup_documentation.py --project-name "Your Project Name" --output-dir "./docs"
"""

import os
import sys
import argparse
import shutil
from datetime import datetime
from pathlib import Path

class DocumentationSetup:
    def __init__(self, project_name, output_dir="./project_docs"):
        self.project_name = project_name
        self.output_dir = Path(output_dir)
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.guides_dir = Path(__file__).parent.parent / "guides"
        self.scripts_dir = Path(__file__).parent
        
        # Create safe project identifier (for filenames, etc.)
        self.project_id = project_name.lower().replace(" ", "_").replace("-", "_")
        
    def create_directory_structure(self):
        """Create the basic directory structure for documentation"""
        print(f"📁 Creating directory structure in {self.output_dir}")
        
        directories = [
            self.output_dir,
            self.output_dir / "sections",
            self.output_dir / "guides", 
            self.output_dir / "scripts",
            self.output_dir / "assets",
            self.output_dir / "assets" / "images",
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Created: {directory}")
    
    def copy_and_customize_templates(self):
        """Copy templates and customize them with project information"""
        print(f"📝 Copying and customizing templates for '{self.project_name}'")
        
        template_files = [
            ("01_overview_template.md", "01_overview.md"),
            ("02_architecture_template.md", "02_technical_architecture.md"),
            ("03_user_guide_template.md", "03_user_documentation.md"),
            ("04_developer_docs_template.md", "04_developer_documentation.md"),
            ("05_deployment_template.md", "05_deployment_operations.md"),
            ("06_troubleshooting_template.md", "06_troubleshooting_support.md"),
            ("07_compliance_template.md", "07_data_compliance.md"),
        ]
        
        for template_file, output_file in template_files:
            template_path = self.template_dir / template_file
            output_path = self.output_dir / "sections" / output_file
            
            if template_path.exists():
                # Read template
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Replace placeholders
                content = self.customize_content(content)
                
                # Write customized file
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"   ✅ Created: {output_file}")
            else:
                print(f"   ⚠️  Template not found: {template_file}")
    
    def customize_content(self, content):
        """Replace template placeholders with project-specific information"""
        replacements = {
            "[PROJECT_NAME]": self.project_name,
            "[PROJECT_ID]": self.project_id,
            "[DATE]": datetime.now().strftime("%Y-%m-%d"),
            "[YEAR]": datetime.now().strftime("%Y"),
            "[MONTH_YEAR]": datetime.now().strftime("%B %Y"),
        }
        
        for placeholder, replacement in replacements.items():
            content = content.replace(placeholder, replacement)
        
        return content
    
    def copy_guides_and_scripts(self):
        """Copy documentation guides and utility scripts"""
        print("📚 Copying documentation guides and scripts")
        
        # Copy guides
        if self.guides_dir.exists():
            for guide_file in self.guides_dir.glob("*.md"):
                shutil.copy2(guide_file, self.output_dir / "guides")
                print(f"   ✅ Copied guide: {guide_file.name}")
        
        # Copy scripts
        script_files = ["merge_documentation.py", "validate_content.py", "generate_toc.py"]
        for script_file in script_files:
            script_path = self.scripts_dir / script_file
            if script_path.exists():
                shutil.copy2(script_path, self.output_dir / "scripts")
                print(f"   ✅ Copied script: {script_file}")
    
    def create_main_readme(self):
        """Create the main README file for the documentation project"""
        print("📋 Creating main README file")
        
        readme_content = f"""# {self.project_name} Documentation

This directory contains comprehensive technical documentation for {self.project_name}.

## 📁 Structure

```
{self.project_id}_docs/
├── sections/                    # Individual documentation sections
│   ├── 01_overview.md
│   ├── 02_technical_architecture.md
│   ├── 03_user_documentation.md
│   ├── 04_developer_documentation.md
│   ├── 05_deployment_operations.md
│   ├── 06_troubleshooting_support.md
│   └── 07_data_compliance.md
├── guides/                      # Documentation creation and import guides
├── scripts/                     # Automation scripts
├── assets/                      # Images and other assets
│   └── images/
└── README.md                    # This file
```

## 🚀 Getting Started

### 1. Fill in the Templates
Edit the files in the `sections/` directory with your project-specific content:

1. **01_overview.md** - Business context and system overview
2. **02_technical_architecture.md** - System design and components
3. **03_user_documentation.md** - End-user guidance
4. **04_developer_documentation.md** - API reference and dev guides
5. **05_deployment_operations.md** - Deployment and operational procedures
6. **06_troubleshooting_support.md** - Problem resolution
7. **07_data_compliance.md** - Data management and compliance

### 2. Add Visual Content
- Place images in `assets/images/`
- Replace image placeholders (📸) with actual screenshots and diagrams
- Use consistent naming: `section_X_description.png`

### 3. Generate Consolidated Documentation
```bash
cd scripts/
python merge_documentation.py
```

### 4. Import to Confluence
Follow the guide in `guides/CONFLUENCE_IMPORT_GUIDE.md` for step-by-step import instructions.

## 📊 Documentation Standards

- **Target Word Count**: 5,000-8,000 words per section
- **Total Expected**: 50,000+ words comprehensive documentation
- **Format**: GitHub Flavored Markdown
- **Structure**: 4-level hierarchy maximum
- **Images**: Strategic placeholders with descriptive text

## 🛠️ Available Scripts

- **`merge_documentation.py`** - Combine all sections into single file
- **`validate_content.py`** - Check completeness and formatting
- **`generate_toc.py`** - Create detailed table of contents

## 📚 Resources

- **Creation Guide**: `guides/DOCUMENTATION_CREATION_GUIDE.md`
- **Import Guide**: `guides/CONFLUENCE_IMPORT_GUIDE.md`
- **Template Methodology**: Based on enterprise documentation best practices

---

*Documentation initialized: {datetime.now().strftime("%B %d, %Y")}*  
*Project: {self.project_name}*  
*Template Version: 1.0*
"""
        
        readme_path = self.output_dir / "README.md"
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        
        print(f"   ✅ Created: README.md")
    
    def create_config_file(self):
        """Create configuration file for the documentation project"""
        print("⚙️ Creating configuration file")
        
        config_content = f"""# {self.project_name} Documentation Configuration

project:
  name: "{self.project_name}"
  id: "{self.project_id}"
  created: "{datetime.now().isoformat()}"
  
structure:
  sections:
    - "01_overview.md"
    - "02_technical_architecture.md"
    - "03_user_documentation.md"
    - "04_developer_documentation.md"
    - "05_deployment_operations.md"
    - "06_troubleshooting_support.md"
    - "07_data_compliance.md"
  
output:
  consolidated_file: "{self.project_id}_complete_documentation.md"
  confluence_ready: true
  
formatting:
  max_heading_level: 4
  include_toc: true
  image_placeholder_format: "📸 Image showing {{description}} should be placed here"
  
validation:
  min_words_per_section: 3000
  required_sections: 7
  check_image_placeholders: true
  validate_cross_references: true
"""
        
        config_path = self.output_dir / "doc_config.yaml"
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"   ✅ Created: doc_config.yaml")
    
    def run_setup(self):
        """Run the complete setup process"""
        print(f"🚀 Setting up documentation for '{self.project_name}'")
        print(f"📍 Output directory: {self.output_dir.absolute()}")
        print()
        
        try:
            self.create_directory_structure()
            print()
            
            self.copy_and_customize_templates()
            print()
            
            self.copy_guides_and_scripts()
            print()
            
            self.create_main_readme()
            print()
            
            self.create_config_file()
            print()
            
            print("✅ Documentation setup complete!")
            print()
            print("📋 Next Steps:")
            print(f"   1. cd {self.output_dir}")
            print("   2. Edit files in sections/ with your project content")
            print("   3. Add images to assets/images/")
            print("   4. Run scripts/merge_documentation.py when ready")
            print("   5. Import to Confluence using guides/CONFLUENCE_IMPORT_GUIDE.md")
            print()
            print("📚 Resources:")
            print("   - guides/DOCUMENTATION_CREATION_GUIDE.md - Detailed methodology")
            print("   - README.md - Project-specific instructions")
            
        except Exception as e:
            print(f"❌ Setup failed: {e}")
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Initialize enterprise documentation for a new project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_documentation.py --project-name "My API Project"
  python setup_documentation.py --project-name "Data Pipeline" --output-dir "./documentation"
  python setup_documentation.py --project-name "ML Platform" --output-dir "../docs"
        """
    )
    
    parser.add_argument(
        "--project-name", 
        required=True,
        help="Name of your project (e.g., 'Customer API', 'Data Processing Pipeline')"
    )
    
    parser.add_argument(
        "--output-dir",
        default="./project_docs",
        help="Output directory for documentation (default: ./project_docs)"
    )
    
    args = parser.parse_args()
    
    # Validate project name
    if not args.project_name.strip():
        print("❌ Project name cannot be empty")
        sys.exit(1)
    
    # Initialize and run setup
    setup = DocumentationSetup(args.project_name.strip(), args.output_dir)
    setup.run_setup()

if __name__ == "__main__":
    main()
