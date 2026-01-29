#!/usr/bin/env python3

import requests
import json
import base64
import os
from pathlib import Path

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

APP_NAME = "glucostream-dashboard"

print("="*60)
print("Deploying GlucoStream Dashboard to Databricks Apps")
print("="*60)

# Step 1: Upload files to workspace
print("\n📤 Step 1: Uploading application files to workspace...")

def upload_file_to_workspace(local_path, workspace_path):
    """Upload a file to Databricks workspace"""
    with open(local_path, 'rb') as f:
        content = f.read()
    
    content_b64 = base64.b64encode(content).decode()
    
    data = {
        "path": workspace_path,
        "content": content_b64,
        "overwrite": True,
        "format": "AUTO"
    }
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json=data
    )
    
    return response

# Upload the built files
workspace_base = f"/Workspace/Users/glucostream-app"
dist_folder = "dist"

print(f"   Uploading to: {workspace_base}")

uploaded_files = []
for file_path in Path(dist_folder).rglob('*'):
    if file_path.is_file():
        rel_path = file_path.relative_to(dist_folder)
        ws_path = f"{workspace_base}/{rel_path}".replace('\\', '/')
        
        print(f"   • {rel_path}")
        response = upload_file_to_workspace(str(file_path), ws_path)
        
        if response.status_code == 200:
            uploaded_files.append(ws_path)

print(f"   ✅ Uploaded {len(uploaded_files)} files")

# Step 2: Create app configuration
print("\n🚀 Step 2: Creating Databricks App...")

# Create the app YAML configuration
app_yaml_content = """
name: glucostream-dashboard
resources:
  - name: frontend
    description: React-based glucose monitoring dashboard
    properties:
      port: 8080
"""

# Upload app.yaml
app_yaml_ws_path = f"{workspace_base}/app.yaml"
with open("app.yaml", "w") as f:
    f.write(app_yaml_content)

response = upload_file_to_workspace("app.yaml", app_yaml_ws_path)
print(f"   App config uploaded: {response.status_code}")

# Step 3: Check if app already exists
print("\n🔍 Step 3: Checking existing apps...")

list_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/apps", headers=headers)
existing_apps = list_response.json().get('apps', [])
existing_app = None

for app in existing_apps:
    if app.get('name') == APP_NAME:
        existing_app = app
        break

if existing_app:
    print(f"   ⚠️  App '{APP_NAME}' already exists")
    print(f"   App URL: {existing_app.get('url', 'N/A')}")
    print("\n   Do you want to update it? (The script will continue)")
    app_name_to_use = f"{APP_NAME}-glucostream-{os.urandom(4).hex()}"
    print(f"   Creating with unique name: {app_name_to_use}")
else:
    app_name_to_use = APP_NAME

# Step 4: Create the app
print(f"\n✨ Step 4: Creating Databricks App '{app_name_to_use}'...")

app_config = {
    "name": app_name_to_use,
    "description": "GlucoStream Intelligence Dashboard - Continuous Glucose Monitoring Platform with role-based dashboards for care management, clinicians, and device support teams."
}

create_response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/apps",
    headers=headers,
    json=app_config
)

print(f"   Response: {create_response.status_code}")

if create_response.status_code in [200, 201]:
    app_data = create_response.json()
    print(f"   ✅ App created successfully!")
    print(f"\n   App details:")
    print(f"   • Name: {app_data.get('name', app_name_to_use)}")
    print(f"   • Service Principal: {app_data.get('service_principal_id', 'N/A')}")
    
    # Try to get the app URL
    app_url = app_data.get('url') or app_data.get('compute', {}).get('url')
    
    if app_url:
        print(f"   • URL: {app_url}")
    else:
        # Get the app details
        get_response = requests.get(
            f"{DATABRICKS_HOST}/api/2.0/apps/{app_name_to_use}",
            headers=headers
        )
        if get_response.status_code == 200:
            app_details = get_response.json()
            print(f"\n   App Details: {json.dumps(app_details, indent=2)}")
    
elif create_response.status_code == 409:
    print(f"   ℹ️  App already exists")
    print(f"   Response: {create_response.text}")
else:
    print(f"   ❌ Failed to create app")
    print(f"   Response: {create_response.text}")

print("\n" + "="*60)
print("DEPLOYMENT COMPLETE!")
print("="*60)
print(f"\n📱 Access your app in Databricks:")
print(f"   1. Go to: {DATABRICKS_HOST}")
print(f"   2. Navigate to: Apps")
print(f"   3. Find: {app_name_to_use}")
print(f"\nOr view all apps:")
print(f"   {DATABRICKS_HOST}/#apps")

