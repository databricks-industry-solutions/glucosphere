#!/usr/bin/env python3
"""
Deploy Glucosphere app to Databricks Buildathon workspace
"""

import requests
import json
import base64
import os
import sys
from pathlib import Path

# Load configuration
config_path = Path(__file__).parent / "config" / "databricks_config_buildathon.json"
with open(config_path) as f:
    config = json.load(f)

DATABRICKS_HOST = config["databricks_host"]
DATABRICKS_TOKEN = config["databricks_token"]
APP_NAME = config["app_name"]  # glucosphere
USERNAME = config["username"]

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("="*70)
print(f"🚀 DEPLOYING {APP_NAME.upper()} TO DATABRICKS")
print("="*70)
print(f"   Workspace: {DATABRICKS_HOST}")
print(f"   App Name: {APP_NAME}")
print(f"   User: {USERNAME}")
print("="*70)

# Step 1: Check if app exists
print(f"\n1️⃣  Checking if app '{APP_NAME}' exists...")
response = requests.get(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers
)

app_exists = response.status_code == 200
if app_exists:
    print(f"   ⚠️  App '{APP_NAME}' already exists - will update")
else:
    print(f"   ✅ App '{APP_NAME}' does not exist - will create new")

# Step 2: Create workspace directory
workspace_path = f"/Workspace/Users/{USERNAME}/.bundle/{APP_NAME}/files"
print(f"\n2️⃣  Creating workspace directory: {workspace_path}")

response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/workspace/mkdirs",
    headers=headers,
    json={"path": workspace_path}
)
print(f"   Status: {response.status_code}")

# Create subdirectories
for subdir in ["dist", "dist/assets"]:
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/mkdirs",
        headers=headers,
        json={"path": f"{workspace_path}/{subdir}"}
    )

# Step 3: Upload files
print(f"\n3️⃣  Uploading application files...")

def upload_file(local_path, workspace_dest):
    """Upload a file to workspace"""
    with open(local_path, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json={
            "path": workspace_dest,
            "content": content,
            "overwrite": True,
            "format": "AUTO"
        }
    )
    return response

# Upload from databricks directory
databricks_dir = Path(__file__).parent / "databricks"
os.chdir(databricks_dir)

files_to_upload = [
    ("app.py", f"{workspace_path}/app.py"),
    ("app.yaml", f"{workspace_path}/app.yaml"),
    ("requirements.txt", f"{workspace_path}/requirements.txt"),
]

# Add dist files
dist_dir = databricks_dir / "dist"
if dist_dir.exists():
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            local_path = Path(root) / file
            rel_path = local_path.relative_to(databricks_dir)
            workspace_dest = f"{workspace_path}/{rel_path}".replace("\\", "/")
            files_to_upload.append((str(local_path), workspace_dest))

print(f"   Uploading {len(files_to_upload)} files...")
uploaded = 0
for local_path, workspace_dest in files_to_upload:
    if not os.path.exists(local_path):
        print(f"   ⚠️  Skipping {local_path} (not found)")
        continue
    
    response = upload_file(local_path, workspace_dest)
    if response.status_code == 200:
        uploaded += 1
        # Only print key files to reduce noise
        if any(x in local_path for x in ["app.py", "app.yaml", "requirements.txt", "index.html"]):
            print(f"   ✅ {os.path.basename(local_path)}")
    else:
        print(f"   ❌ {local_path}: {response.status_code} - {response.text[:100]}")

print(f"   ✅ Uploaded {uploaded}/{len(files_to_upload)} files")

# Step 4: Create or deploy app
print(f"\n4️⃣  Creating/deploying app '{APP_NAME}'...")

# For Databricks Apps, we can create and deploy in one step
deploy_config = {
    "name": APP_NAME,
    "description": config.get("app_description", "Glucosphere CGM Analytics"),
    "source_code_path": workspace_path
}

if not app_exists:
    # Create new app
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/apps",
        headers=headers,
        json=deploy_config
    )
    action = "created"
else:
    # Update existing app
    response = requests.patch(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
        headers=headers,
        json={"description": config.get("app_description", "Glucosphere CGM Analytics")}
    )
    action = "updated"

if response.status_code in [200, 201]:
    print(f"   ✅ App {action} successfully!")
else:
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:300]}")
    # Continue anyway - app might already exist

# Step 5: Deploy the app
print(f"\n5️⃣  Deploying app '{APP_NAME}'...")

response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}/deployments",
    headers=headers,
    json={
        "source_code_path": workspace_path
    }
)

if response.status_code in [200, 201]:
    print(f"   ✅ Deployment started!")
    deployment_data = response.json()
    deployment_id = deployment_data.get("deployment_id", "unknown")
    print(f"   Deployment ID: {deployment_id}")
else:
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text[:300]}")

# Step 6: Get app URL
print(f"\n6️⃣  Getting app URL...")
response = requests.get(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers
)

if response.status_code == 200:
    app_data = response.json()
    app_url = app_data.get("url")
    if app_url:
        print(f"\n{'='*70}")
        print(f"✅ DEPLOYMENT COMPLETE!")
        print(f"{'='*70}")
        print(f"   App Name: {APP_NAME}")
        print(f"   App URL: {app_url}")
        print(f"{'='*70}")
    else:
        print(f"   ⚠️  App created but URL not yet available")
        print(f"   Check the Databricks Apps UI in a few moments")
else:
    print(f"   Status: {response.status_code}")

print("\n✅ Deployment script completed!")
