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
APP_NAME = "glucostream-dashboard"

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("="*70)
print("🚀 DEPLOYING SOURCE CODE TO GLUCOSTREAM DASHBOARD")
print("="*70)

# Use the app's default source path or create one
workspace_path = f"/Workspace/Users/justin.ward@databricks.com/.bundle/{APP_NAME}/files"

print(f"\n📂 Target workspace path: {workspace_path}")

# Step 1: Create workspace directories
print("\n1️⃣  Creating workspace directories...")

def create_workspace_dir(path):
    """Create a workspace directory"""
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/mkdirs",
        headers=headers,
        json={"path": path}
    )
    return response

# Create base directories
for dir_path in [
    workspace_path,
    f"{workspace_path}/dist",
    f"{workspace_path}/dist/assets"
]:
    response = create_workspace_dir(dir_path)
    status = "✅" if response.status_code == 200 else "⚠️"
    print(f"   {status} {dir_path}: {response.status_code}")

# Step 2: Upload files
print("\n2️⃣  Uploading application files...")

def upload_file(local_path, workspace_path):
    """Upload a file to workspace"""
    with open(local_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json={
            "path": workspace_path,
            "content": content,
            "overwrite": True,
            "format": "AUTO"
        }
    )
    return response

# Upload app.py
print("\n   📄 Uploading app.py...")
response = upload_file("app.py", f"{workspace_path}/app.py")
print(f"      Status: {response.status_code}")
if response.status_code != 200:
    print(f"      Error: {response.text}")

# Upload app.yaml
print("\n   📄 Uploading app.yaml...")
response = upload_file("app.yaml", f"{workspace_path}/app.yaml")
print(f"      Status: {response.status_code}")
if response.status_code != 200:
    print(f"      Error: {response.text}")

# Upload dist files
print("\n   📦 Uploading dist/ folder...")
uploaded_count = 0
for file_path in Path("dist").rglob("*"):
    if file_path.is_file():
        rel_path = file_path.relative_to("dist")
        ws_file_path = f"{workspace_path}/dist/{rel_path}".replace("\\", "/")
        
        response = upload_file(str(file_path), ws_file_path)
        if response.status_code == 200:
            uploaded_count += 1
            print(f"      ✅ {rel_path}")
        else:
            print(f"      ❌ {rel_path}: {response.status_code}")

print(f"\n   📊 Uploaded {uploaded_count} files")

# Step 3: Update app with source code path
print("\n3️⃣  Linking source code to app...")

update_response = requests.patch(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers,
    json={"source_code_path": workspace_path}
)

print(f"   Status: {update_response.status_code}")
if update_response.status_code == 200:
    print(f"   ✅ Source code path updated!")
else:
    print(f"   Response: {update_response.text}")

# Step 4: Trigger deployment
print("\n4️⃣  Triggering app deployment...")

deploy_response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}/deployments",
    headers=headers,
    json={"source_code_path": workspace_path}
)

print(f"   Status: {deploy_response.status_code}")
if deploy_response.status_code in [200, 201]:
    print(f"   ✅ Deployment started!")
    deploy_data = deploy_response.json()
    print(f"   Deployment ID: {deploy_data.get('deployment_id', 'N/A')}")
else:
    print(f"   Response: {deploy_response.text}")

# Step 5: Check final status
print("\n5️⃣  Checking app status...")

status_response = requests.get(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers
)

if status_response.status_code == 200:
    app_info = status_response.json()
    print(f"\n   📊 App Status:")
    print(f"      Name: {app_info.get('name')}")
    print(f"      URL: {app_info.get('url')}")
    print(f"      Compute: {app_info.get('compute_status', {}).get('state')}")
    print(f"      App Status: {app_info.get('app_status', {}).get('state')}")
    print(f"      Source Path: {app_info.get('source_code_path', 'Not set')}")

print("\n" + "="*70)
print("✅ DEPLOYMENT COMPLETE!")
print("="*70)
print(f"\n🌐 Your app URL:")
print(f"   {app_info.get('url')}")
print(f"\n⏳ The app may take 1-2 minutes to start up.")
print(f"   Visit the URL above or check:")
print(f"   {DATABRICKS_HOST}/#apps/{APP_NAME}")
print(f"\n💡 If the app shows an error initially, wait a moment and refresh.")
print("="*70)

