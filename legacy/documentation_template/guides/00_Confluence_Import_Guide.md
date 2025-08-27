# DNSH-5 Documentation - Confluence Import Guide

## 📋 Overview

This guide provides step-by-step instructions for importing your DNSH-5 documentation into Confluence, with multiple methods to suit different organizational needs and technical capabilities.

---

## 🎯 Pre-Import Planning

### 1. Create Confluence Space Structure

**Recommended Space Structure:**
```
DNSH-5 Compliance Pipeline (Space)
├── 📋 Overview & Quick Start
├── 🏗️ Technical Documentation
│   ├── Architecture Overview
│   ├── API Reference
│   └── Configuration Guide
├── 👥 User Documentation
│   ├── User Guide
│   ├── Process Overview
│   └── Troubleshooting
└── 📊 Operations & Maintenance
    ├── Runbooks
    ├── Monitoring
    └── Change Log
```

### 2. Prepare Your Files

**Files to Import (in order):**
1. `01_DNSH5_Main_Overview.md` → **Space Homepage**
2. `07_Process_and_Automation_Overview.md` → **Process Overview**
3. `02_Technical_Architecture.md` → **Architecture Overview**
4. `03_User_Guide.md` → **User Guide**
5. `04_API_Reference.md` → **API Reference**
6. `05_Troubleshooting_Guide.md` → **Troubleshooting**
7. `06_Configuration_Reference.md` → **Configuration Guide**

---

## 🚀 Method 1: Direct Copy-Paste (Recommended for Small Teams)

### Step 1: Create Confluence Space
1. Go to Confluence → **Spaces** → **Create Space**
2. Choose **Team Space** or **Documentation Space**
3. Name: `DNSH-5 Compliance Pipeline`
4. Key: `DNSH5` (or your preferred abbreviation)

### Step 2: Create Page Structure
1. **Create Parent Pages:**
   ```
   - Overview & Quick Start (Homepage)
   - Technical Documentation
   - User Documentation  
   - Operations & Maintenance
   ```

2. **Create Child Pages under each parent**

### Step 3: Import Content Page by Page

**For each markdown file:**

1. **Open the markdown file** in your text editor
2. **Copy the entire content**
3. **In Confluence:**
   - Create new page or edit existing
   - Switch to **"/"** command menu
   - Type `markdown` and select **"Markdown"**
   - Paste your content
   - Click **"Convert"**

### Step 4: Fix Formatting Issues

**Common fixes needed:**
- **Tables:** May need manual reformatting
- **Code blocks:** Ensure proper syntax highlighting
- **Links:** Convert internal links to Confluence page links
- **Mermaid diagrams:** See Method 3 for diagram handling

---

## 🔧 Method 2: Confluence CLI (For Tech Teams)

### Prerequisites
```bash
# Install Atlassian CLI
npm install -g @atlassian/confluence-cli
# OR
pip install confluence-cli
```

### Step 1: Configure CLI
```bash
# Set up authentication
confluence-cli configure
# Enter your Confluence URL, username, and API token
```

### Step 2: Bulk Import Script
```bash
#!/bin/bash
# bulk_import.sh

SPACE_KEY="DNSH5"
PARENT_PAGE_ID="123456789"  # Get this from Confluence URL

# Import files in order
confluence-cli create-page \
  --space "$SPACE_KEY" \
  --title "DNSH-5 Main Overview" \
  --file "confluence_docs/01_DNSH5_Main_Overview.md" \
  --parent-id "$PARENT_PAGE_ID"

confluence-cli create-page \
  --space "$SPACE_KEY" \
  --title "Process and Automation Overview" \
  --file "confluence_docs/07_Process_and_Automation_Overview.md" \
  --parent-id "$PARENT_PAGE_ID"

# Continue for all files...
```

### Step 3: Run Import
```bash
chmod +x bulk_import.sh
./bulk_import.sh
```

---

## 📊 Method 3: Advanced Import with Diagram Support

### Step 1: Prepare Mermaid Diagrams

**Option A: Convert to Images**
```bash
# Install mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Convert diagrams to images
mmdc -i diagram.mmd -o diagram.png -t dark -b white
```

**Option B: Use Confluence Mermaid Plugin**
- Install "Mermaid for Confluence" app
- Keep diagrams as code blocks with `mermaid` language

### Step 2: Enhanced Content Preparation

**Create a preprocessing script:**
```python
# preprocess_for_confluence.py
import re
import os

def process_markdown_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix internal links
    content = re.sub(r'\[([^\]]+)\]\((\d+_[^)]+\.md)\)', 
                    r'[\1](@\2)', content)
    
    # Add Confluence macros for better formatting
    content = content.replace('## 🎯', '{panel:title=🎯 Goals}\n## 🎯')
    content = content.replace('---', '{panel}\n\n---')
    
    # Save processed version
    output_path = file_path.replace('.md', '_confluence.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return output_path

# Process all files
for file in os.listdir('confluence_docs'):
    if file.endswith('.md') and not file.startswith('00_'):
        process_markdown_file(f'confluence_docs/{file}')
```

---

## 🔗 Method 4: Automated Import with Python

### Step 1: Install Dependencies
```bash
pip install atlassian-python-api markdown
```

### Step 2: Create Import Script
```python
# confluence_importer.py
from atlassian import Confluence
import markdown
import os

# Configuration
CONFLUENCE_URL = "https://yourcompany.atlassian.net/wiki"
USERNAME = "your-email@company.com"
API_TOKEN = "your-api-token"
SPACE_KEY = "DNSH5"

confluence = Confluence(
    url=CONFLUENCE_URL,
    username=USERNAME,
    password=API_TOKEN
)

def import_markdown_file(file_path, title, parent_id=None):
    """Import a markdown file as a Confluence page"""
    
    with open(file_path, 'r', encoding='utf-8') as f:
        markdown_content = f.read()
    
    # Convert markdown to HTML
    html_content = markdown.markdown(markdown_content, extensions=['tables', 'fenced_code'])
    
    # Create or update page
    try:
        page = confluence.create_page(
            space=SPACE_KEY,
            title=title,
            body=html_content,
            parent_id=parent_id
        )
        print(f"✅ Created page: {title}")
        return page['id']
    except Exception as e:
        print(f"❌ Failed to create page {title}: {e}")
        return None

# Import files
files_to_import = [
    ("confluence_docs/01_DNSH5_Main_Overview.md", "DNSH-5 Main Overview"),
    ("confluence_docs/07_Process_and_Automation_Overview.md", "Process and Automation Overview"),
    ("confluence_docs/02_Technical_Architecture.md", "Technical Architecture"),
    ("confluence_docs/03_User_Guide.md", "User Guide"),
    ("confluence_docs/04_API_Reference.md", "API Reference"),
    ("confluence_docs/05_Troubleshooting_Guide.md", "Troubleshooting Guide"),
    ("confluence_docs/06_Configuration_Reference.md", "Configuration Reference"),
]

for file_path, title in files_to_import:
    if os.path.exists(file_path):
        import_markdown_file(file_path, title)
```

### Step 3: Run the Import
```bash
python confluence_importer.py
```

---

## 🎨 Post-Import Optimization

### 1. Fix Navigation Links

**Update internal links:**
- Replace `[User Guide](03_User_Guide.md)` with Confluence page links
- Use Confluence's link picker for internal references

### 2. Add Confluence Macros

**Enhance with Confluence features:**
```
{info}
This is an info panel for important notes
{info}

{code:language=bash}
python scripts/batch_processing/async_batch_process.py
{code}

{expand:title=Click to expand details}
Detailed content here
{expand}
```

### 3. Create Page Templates

**For consistent formatting:**
1. Go to **Space Settings** → **Page Templates**
2. Create templates based on your imported pages
3. Use for future documentation

### 4. Set up Page Tree

**Organize with proper hierarchy:**
```
DNSH-5 Compliance Pipeline (Homepage)
├── 📋 Process and Automation Overview
├── 🏗️ Technical Architecture  
├── 👥 User Guide
├── 🔧 API Reference
├── 🚨 Troubleshooting Guide
└── ⚙️ Configuration Reference
```

---

## 📊 Method 5: Confluence Cloud Import Feature

### Step 1: Prepare Import Package
```bash
# Create a zip file with your markdown files
zip -r dnsh5_docs.zip confluence_docs/
```

### Step 2: Use Confluence Import
1. Go to **Space Settings** → **Content Tools** → **Import**
2. Choose **"Upload file"**
3. Select your zip file
4. Choose **"Markdown"** as import format
5. Map files to page structure

### Step 3: Review and Adjust
- Check imported pages for formatting
- Fix any broken links or images
- Update navigation structure

---

## 🔄 Ongoing Maintenance Workflow

### 1. Version Control Integration

**Option A: Manual Updates**
- Update markdown files in your repository
- Copy changes to Confluence manually
- Use page history for tracking

**Option B: Automated Sync**
```bash
# sync_to_confluence.sh
#!/bin/bash

# Check for changes in confluence_docs/
if git diff --name-only HEAD~1 | grep -q "confluence_docs/"; then
    echo "Documentation changes detected, updating Confluence..."
    python confluence_importer.py
fi
```

### 2. Content Review Process

**Monthly Review Checklist:**
- [ ] Check all internal links work
- [ ] Verify code examples are current  
- [ ] Update screenshots if UI changed
- [ ] Review and update version numbers
- [ ] Check for broken external links

### 3. Access Control

**Set appropriate permissions:**
- **View:** All team members
- **Edit:** Documentation team + developers
- **Admin:** Space administrators

---

## 🚨 Troubleshooting Common Issues

### Issue 1: Tables Don't Import Correctly
**Solution:** 
- Import as plain text first
- Use Confluence table editor to recreate
- Or use HTML table syntax

### Issue 2: Code Blocks Lose Formatting
**Solution:**
```
{code:language=python}
your code here
{code}
```

### Issue 3: Mermaid Diagrams Not Supported
**Solutions:**
- Install Mermaid app for Confluence
- Convert to images using mermaid CLI
- Use Confluence's built-in diagramming tools

### Issue 4: Internal Links Break
**Solution:**
- Use Confluence's link picker after import
- Create a link mapping document
- Use page anchors for section links

---

## ✅ Final Checklist

Before going live with your Confluence documentation:

- [ ] All pages imported successfully
- [ ] Navigation structure is logical
- [ ] Internal links work correctly
- [ ] Code examples are properly formatted
- [ ] Tables display correctly
- [ ] Diagrams are visible and clear
- [ ] Permissions are set appropriately
- [ ] Space homepage is welcoming and informative
- [ ] Search functionality works for key terms
- [ ] Mobile view is acceptable

---

## 📞 Getting Help

### Confluence Support Resources
- **Atlassian Documentation:** https://support.atlassian.com/confluence-cloud/
- **Community:** https://community.atlassian.com/
- **Markdown Import Guide:** Search for "Import markdown to Confluence"

### Internal Support
- Contact your Confluence administrator for space creation
- IT team for API access and authentication
- Documentation team for style guide compliance

---

*Import Guide Version: 1.0*  
*Last Updated: January 2025*  
*Next Review: February 2025*


