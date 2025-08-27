#!/usr/bin/env python3
"""
Template Deployment Script

This script deploys the documentation template to other project directories,
making it easy to spread the documentation methodology across multiple projects.

Usage:
    python deploy_template.py --target-dir /path/to/project --project-name "Project Name"
    python deploy_template.py --target-dir ../other-project --project-name "Other Project"
    python deploy_template.py --list-deployments  # Show previous deployments
"""

import os
import sys
import argparse
import shutil
import json
from datetime import datetime
from pathlib import Path

class TemplateDeployer:
    def __init__(self):
        self.template_root = Path(__file__).parent.parent
        self.deployment_log = Path.home() / ".documentation_deployments.json"
        
    def load_deployment_history(self):
        """Load deployment history from log file"""
        if self.deployment_log.exists():
            try:
                with open(self.deployment_log, 'r') as f:
                    return json.load(f)
            except:
                return {"deployments": []}
        return {"deployments": []}
    
    def save_deployment_record(self, target_dir, project_name):
        """Save deployment record to log file"""
        history = self.load_deployment_history()
        
        deployment_record = {
            "project_name": project_name,
            "target_directory": str(Path(target_dir).absolute()),
            "deployed_at": datetime.now().isoformat(),
            "template_version": "1.0"
        }
        
        history["deployments"].append(deployment_record)
        
        with open(self.deployment_log, 'w') as f:
            json.dump(history, f, indent=2)
    
    def deploy_to_directory(self, target_dir, project_name, force=False):
        """Deploy template to target directory"""
        target_path = Path(target_dir)
        docs_path = target_path / "docs"
        
        print(f"🚀 Deploying documentation template to: {target_path.absolute()}")
        print(f"📝 Project: {project_name}")
        
        # Check if target directory exists
        if not target_path.exists():
            print(f"❌ Target directory does not exist: {target_path}")
            return False
        
        # Check if docs directory already exists
        if docs_path.exists() and not force:
            print(f"⚠️  Documentation directory already exists: {docs_path}")
            response = input("Continue and overwrite? (y/N): ")
            if response.lower() != 'y':
                print("❌ Deployment cancelled")
                return False
        
        try:
            # Create docs directory
            docs_path.mkdir(exist_ok=True)
            
            # Copy template structure
            print("📁 Creating directory structure...")
            self._copy_template_structure(docs_path, project_name)
            
            # Run setup script
            print("⚙️ Initializing documentation...")
            self._run_setup_script(docs_path, project_name)
            
            # Save deployment record
            self.save_deployment_record(target_dir, project_name)
            
            print("✅ Template deployment successful!")
            print(f"📍 Documentation created at: {docs_path}")
            print()
            print("📋 Next Steps:")
            print(f"   1. cd {docs_path}")
            print("   2. Edit files in sections/ with your project content")
            print("   3. Add images to assets/images/")
            print("   4. Run scripts/merge_documentation.py when ready")
            
            return True
            
        except Exception as e:
            print(f"❌ Deployment failed: {e}")
            return False
    
    def _copy_template_structure(self, target_docs_path, project_name):
        """Copy the template structure to target directory"""
        
        # Copy templates
        templates_source = self.template_root / "templates"
        templates_target = target_docs_path / "templates"
        if templates_source.exists():
            shutil.copytree(templates_source, templates_target, dirs_exist_ok=True)
            print("   ✅ Copied templates")
        
        # Copy guides
        guides_source = self.template_root / "guides"
        guides_target = target_docs_path / "guides"
        if guides_source.exists():
            shutil.copytree(guides_source, guides_target, dirs_exist_ok=True)
            print("   ✅ Copied guides")
        
        # Copy scripts
        scripts_source = self.template_root / "scripts"
        scripts_target = target_docs_path / "scripts"
        if scripts_source.exists():
            shutil.copytree(scripts_source, scripts_target, dirs_exist_ok=True)
            print("   ✅ Copied scripts")
        
        # Copy README template
        readme_source = self.template_root / "README.md"
        readme_target = target_docs_path / "TEMPLATE_README.md"
        if readme_source.exists():
            shutil.copy2(readme_source, readme_target)
            print("   ✅ Copied template README")
    
    def _run_setup_script(self, docs_path, project_name):
        """Run the setup script to initialize the documentation"""
        setup_script = docs_path / "scripts" / "setup_documentation.py"
        
        if setup_script.exists():
            # Change to docs directory
            original_cwd = os.getcwd()
            os.chdir(docs_path)
            
            try:
                # Import and run setup
                sys.path.insert(0, str(docs_path / "scripts"))
                from setup_documentation import DocumentationSetup
                
                setup = DocumentationSetup(project_name, "./")
                setup.run_setup()
                
            finally:
                os.chdir(original_cwd)
                sys.path.pop(0)
    
    def list_deployments(self):
        """List all previous deployments"""
        history = self.load_deployment_history()
        deployments = history.get("deployments", [])
        
        if not deployments:
            print("📋 No previous deployments found")
            return
        
        print("📋 Documentation Template Deployments")
        print("=" * 50)
        
        for i, deployment in enumerate(deployments, 1):
            print(f"{i}. {deployment['project_name']}")
            print(f"   📍 Location: {deployment['target_directory']}")
            print(f"   📅 Deployed: {deployment['deployed_at']}")
            print(f"   🏷️  Template Version: {deployment.get('template_version', 'Unknown')}")
            print()
    
    def deploy_to_multiple(self, projects_config_file):
        """Deploy to multiple projects from configuration file"""
        config_path = Path(projects_config_file)
        
        if not config_path.exists():
            print(f"❌ Configuration file not found: {config_path}")
            return False
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            projects = config.get("projects", [])
            if not projects:
                print("❌ No projects found in configuration file")
                return False
            
            print(f"🚀 Deploying to {len(projects)} projects...")
            
            success_count = 0
            for project in projects:
                project_name = project.get("name")
                target_dir = project.get("directory")
                
                if not project_name or not target_dir:
                    print(f"⚠️  Skipping invalid project configuration: {project}")
                    continue
                
                print(f"\n📝 Deploying: {project_name}")
                if self.deploy_to_directory(target_dir, project_name, force=True):
                    success_count += 1
            
            print(f"\n✅ Successfully deployed to {success_count}/{len(projects)} projects")
            return success_count == len(projects)
            
        except Exception as e:
            print(f"❌ Batch deployment failed: {e}")
            return False

def create_sample_config():
    """Create a sample configuration file for batch deployment"""
    sample_config = {
        "projects": [
            {
                "name": "Customer API",
                "directory": "../customer-api"
            },
            {
                "name": "Data Processing Pipeline", 
                "directory": "../data-pipeline"
            },
            {
                "name": "ML Model Service",
                "directory": "../ml-service"
            }
        ]
    }
    
    config_file = "deployment_config_sample.json"
    with open(config_file, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"📝 Created sample configuration: {config_file}")
    print("Edit this file with your project directories and run:")
    print(f"python deploy_template.py --batch-deploy {config_file}")

def main():
    parser = argparse.ArgumentParser(
        description="Deploy documentation template to other project directories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy to single project
  python deploy_template.py --target-dir ../my-api --project-name "My API"
  
  # Deploy to multiple projects
  python deploy_template.py --batch-deploy projects.json
  
  # List previous deployments
  python deploy_template.py --list-deployments
  
  # Create sample batch configuration
  python deploy_template.py --create-sample-config
        """
    )
    
    parser.add_argument(
        "--target-dir",
        help="Target project directory to deploy template to"
    )
    
    parser.add_argument(
        "--project-name",
        help="Name of the target project"
    )
    
    parser.add_argument(
        "--batch-deploy",
        help="Deploy to multiple projects from JSON configuration file"
    )
    
    parser.add_argument(
        "--list-deployments",
        action="store_true",
        help="List all previous template deployments"
    )
    
    parser.add_argument(
        "--create-sample-config",
        action="store_true",
        help="Create sample configuration file for batch deployment"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing documentation without prompting"
    )
    
    args = parser.parse_args()
    
    deployer = TemplateDeployer()
    
    if args.list_deployments:
        deployer.list_deployments()
    elif args.create_sample_config:
        create_sample_config()
    elif args.batch_deploy:
        deployer.deploy_to_multiple(args.batch_deploy)
    elif args.target_dir and args.project_name:
        deployer.deploy_to_directory(args.target_dir, args.project_name, args.force)
    else:
        parser.print_help()
        print("\n❌ Either provide --target-dir and --project-name, or use --batch-deploy, --list-deployments, or --create-sample-config")

if __name__ == "__main__":
    main()
