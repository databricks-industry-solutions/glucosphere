#!/usr/bin/env python3
"""
Multi-Workspace Deployment Script
Easily deploy to different Databricks workspaces

Usage:
    python3 deploy.py field-eng     # Deploy to field-eng workspace
    python3 deploy.py buildathon    # Deploy to buildathon workspace
    python3 deploy.py               # Shows available workspaces
"""

import sys
import os
import shutil
import json

# Available workspaces
WORKSPACES = {
    'field-eng': {
        'config_file': 'config/databricks_config_field-eng.json',
        'description': 'Field Engineering Workspace',
        'url': 'https://adb-984752964297111.11.azuredatabricks.net'
    },
    'buildathon': {
        'config_file': 'config/databricks_config_buildathon.json',
        'description': 'Buildathon Workspace',
        'url': 'https://fe-vm-industry-solutions-buildathon.cloud.databricks.com'
    }
}

def show_workspaces():
    """Display available workspaces"""
    print("\n" + "="*70)
    print("📋 AVAILABLE WORKSPACES")
    print("="*70)
    
    for name, info in WORKSPACES.items():
        print(f"\n🏢 {name.upper()}")
        print(f"   Description: {info['description']}")
        print(f"   URL: {info['url']}")
        print(f"   Config: {info['config_file']}")
    
    print("\n" + "="*70)
    print("\n💡 Usage:")
    print("   python3 deploy.py field-eng    # Deploy to field-eng")
    print("   python3 deploy.py buildathon   # Deploy to buildathon")
    print("="*70 + "\n")

def switch_workspace(workspace_name):
    """Switch to specified workspace and deploy"""
    if workspace_name not in WORKSPACES:
        print(f"\n❌ Unknown workspace: {workspace_name}")
        print(f"   Available: {', '.join(WORKSPACES.keys())}")
        show_workspaces()
        return False
    
    workspace = WORKSPACES[workspace_name]
    config_file = workspace['config_file']
    
    # Check if config exists
    if not os.path.exists(config_file):
        print(f"\n❌ Config file not found: {config_file}")
        return False
    
    # Load config to show info
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    print("\n" + "="*70)
    print(f"🎯 DEPLOYING TO: {workspace_name.upper()}")
    print("="*70)
    print(f"   Workspace: {workspace['description']}")
    print(f"   URL: {config['databricks_host']}")
    print(f"   App: {config['app_name']}")
    print("="*70 + "\n")
    
    # Copy workspace config to main config file
    shutil.copy(config_file, 'config/databricks_config.json')
    print(f"✅ Switched to {workspace_name} workspace\n")
    
    # Import and run the deployment script
    import databricks_deploy
    return databricks_deploy.deploy()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_workspaces()
        sys.exit(1)
    
    workspace_name = sys.argv[1].lower()
    
    try:
        success = switch_workspace(workspace_name)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

