#!/usr/bin/env python3
"""
Databricks Apps Management Utility
Easily manage your Databricks Apps across workspaces

Usage:
    python3 manage_apps.py list buildathon          # List apps in workspace
    python3 manage_apps.py status buildathon        # Show app status
    python3 manage_apps.py delete buildathon        # Delete app from workspace
    python3 manage_apps.py stop buildathon          # Stop app
    python3 manage_apps.py start buildathon         # Start app
"""

import sys
import json
import requests

# Workspace configs
WORKSPACES = {
    'field-eng': 'config/databricks_config_field-eng.json',
    'buildathon': 'config/databricks_config_buildathon.json'
}

def load_config(workspace_name):
    """Load workspace configuration"""
    if workspace_name not in WORKSPACES:
        print(f"❌ Unknown workspace: {workspace_name}")
        print(f"   Available: {', '.join(WORKSPACES.keys())}")
        return None
    
    config_file = WORKSPACES[workspace_name]
    with open(config_file, 'r') as f:
        return json.load(f)

def list_apps(workspace_name):
    """List all apps in workspace"""
    config = load_config(workspace_name)
    if not config:
        return
    
    headers = {
        "Authorization": f"Bearer {config['databricks_token']}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"{config['databricks_host']}/api/2.0/apps",
        headers=headers
    )
    
    if response.status_code == 200:
        apps = response.json().get('apps', [])
        print(f"\n📱 Apps in {workspace_name}:")
        print("="*70)
        for app in apps:
            print(f"  • {app['name']}")
            print(f"    URL: {app.get('url', 'N/A')}")
            print(f"    Status: {app.get('app_status', {}).get('state', 'N/A')}")
            print()
        print(f"Total: {len(apps)} apps")
    else:
        print(f"❌ Failed to list apps: {response.status_code}")
        print(response.text)

def get_status(workspace_name):
    """Get app status"""
    config = load_config(workspace_name)
    if not config:
        return
    
    headers = {
        "Authorization": f"Bearer {config['databricks_token']}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(
        f"{config['databricks_host']}/api/2.0/apps/{config['app_name']}",
        headers=headers
    )
    
    if response.status_code == 200:
        app = response.json()
        print(f"\n📊 Status of {config['app_name']} in {workspace_name}:")
        print("="*70)
        print(f"  URL: {app.get('url', 'N/A')}")
        print(f"  Compute: {app.get('compute_status', {}).get('state', 'N/A')}")
        print(f"  App Status: {app.get('app_status', {}).get('state', 'N/A')}")
        print(f"  Message: {app.get('app_status', {}).get('message', 'N/A')}")
        print("="*70)
    elif response.status_code == 404:
        print(f"\n❌ App '{config['app_name']}' not found in {workspace_name}")
    else:
        print(f"❌ Failed to get status: {response.status_code}")
        print(response.text)

def delete_app(workspace_name):
    """Delete app from workspace"""
    config = load_config(workspace_name)
    if not config:
        return
    
    print(f"\n⚠️  About to delete '{config['app_name']}' from {workspace_name}")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() != 'yes':
        print("❌ Deletion cancelled")
        return
    
    headers = {
        "Authorization": f"Bearer {config['databricks_token']}",
        "Content-Type": "application/json"
    }
    
    response = requests.delete(
        f"{config['databricks_host']}/api/2.0/apps/{config['app_name']}",
        headers=headers
    )
    
    if response.status_code == 200:
        print(f"✅ App '{config['app_name']}' is being deleted from {workspace_name}")
        print("   This may take a minute to complete.")
    else:
        print(f"❌ Failed to delete app: {response.status_code}")
        print(response.text)

def stop_app(workspace_name):
    """Stop app"""
    config = load_config(workspace_name)
    if not config:
        return
    
    headers = {
        "Authorization": f"Bearer {config['databricks_token']}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{config['databricks_host']}/api/2.0/apps/{config['app_name']}/stop",
        headers=headers
    )
    
    if response.status_code == 200:
        print(f"✅ App '{config['app_name']}' is stopping")
    else:
        print(f"❌ Failed to stop app: {response.status_code}")
        print(response.text)

def start_app(workspace_name):
    """Start app"""
    config = load_config(workspace_name)
    if not config:
        return
    
    headers = {
        "Authorization": f"Bearer {config['databricks_token']}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{config['databricks_host']}/api/2.0/apps/{config['app_name']}/start",
        headers=headers
    )
    
    if response.status_code == 200:
        print(f"✅ App '{config['app_name']}' is starting")
    else:
        print(f"❌ Failed to start app: {response.status_code}")
        print(response.text)

def show_usage():
    """Show usage information"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║          Databricks Apps Management Utility                  ║
╚══════════════════════════════════════════════════════════════╝

Usage:
    python3 manage_apps.py <command> <workspace>

Commands:
    list       List all apps in workspace
    status     Show status of your app
    delete     Delete app from workspace
    stop       Stop app (keeps it but stops compute)
    start      Start app
    
Workspaces:
    field-eng  Field Engineering workspace
    buildathon Buildathon workspace

Examples:
    python3 manage_apps.py status buildathon
    python3 manage_apps.py list buildathon
    python3 manage_apps.py stop buildathon
    python3 manage_apps.py delete field-eng
""")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        show_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    workspace = sys.argv[2].lower()
    
    commands = {
        'list': list_apps,
        'status': get_status,
        'delete': delete_app,
        'stop': stop_app,
        'start': start_app
    }
    
    if command not in commands:
        print(f"❌ Unknown command: {command}")
        show_usage()
        sys.exit(1)
    
    commands[command](workspace)

