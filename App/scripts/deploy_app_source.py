#!/usr/bin/env python3

import requests
import json
import zipfile
import os
from pathlib import Path
import base64

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
APP_NAME = "glucostream-dashboard"

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("="*60)
print("Deploying Source Code to Databricks App")
print("="*60)

# Step 1: Create app.py for serving static files
print("\n📝 Step 1: Creating Flask server...")

app_py_content = '''from flask import Flask, send_from_directory, send_file
import os

app = Flask(__name__, static_folder='dist')

@app.route('/')
def index():
    return send_file('dist/index.html')

@app.route('/<path:path>')
def serve(path):
    if path.startswith('assets/'):
        return send_from_directory('dist', path)
    return send_file('dist/index.html')  # For React Router

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
'''

with open('app.py', 'w') as f:
    f.write(app_py_content)

print("   ✅ Created app.py")

# Step 2: Update app.yaml
print("\n📝 Step 2: Creating app.yaml...")

app_yaml_content = '''command: ["python", "app.py"]
'''

with open('app.yaml', 'w') as f:
    f.write(app_yaml_content)

print("   ✅ Created app.yaml")

# Step 3: Upload to workspace
print(f"\n📤 Step 3: Uploading to workspace...")

def upload_workspace_directory(local_dir, workspace_base):
    """Upload directory contents to workspace"""
    uploaded = []
    
    for root, dirs, files in os.walk(local_dir):
        for file in files:
            local_path = os.path.join(root, file)
            rel_path = os.path.relpath(local_path, local_dir)
            workspace_path = f"{workspace_base}/{rel_path}".replace('\\', '/')
            
            # Read and encode file
            with open(local_path, 'rb') as f:
                content = base64.b64encode(f.read()).decode()
            
            # Upload
            data = {
                "path": workspace_path,
                "content": content,
                "overwrite": True,
                "format": "AUTO"
            }
            
            response = requests.post(
                f"{DATABRICKS_HOST}/api/2.0/workspace/import",
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                uploaded.append(rel_path)
                print(f"   ✅ {rel_path}")
            else:
                print(f"   ❌ {rel_path}: {response.status_code}")
    
    return uploaded

# Upload app files
workspace_path = f"/Workspace/Users/justin.ward@databricks.com/apps/{APP_NAME}"

# Upload app.py and app.yaml
for filename in ['app.py', 'app.yaml']:
    with open(filename, 'rb') as f:
        content = base64.b64encode(f.read()).decode()
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json={
            "path": f"{workspace_path}/{filename}",
            "content": content,
            "overwrite": True,
            "format": "AUTO"
        }
    )
    print(f"   • {filename}: {response.status_code}")

# Upload dist folder
print("\n   Uploading dist/ folder...")
upload_workspace_directory('dist', f"{workspace_path}/dist")

# Step 4: Update app deployment
print(f"\n🔄 Step 4: Updating app deployment...")

update_data = {
    "source_code_path": workspace_path
}

update_response = requests.patch(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers,
    json=update_data
)

print(f"   Status: {update_response.status_code}")

if update_response.status_code == 200:
    print("   ✅ App updated with source code!")
else:
    print(f"   Response: {update_response.text}")

# Step 5: Start/Deploy the app
print(f"\n▶️  Step 5: Starting app deployment...")

deploy_response = requests.post(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}/deployments",
    headers=headers,
    json={"source_code_path": workspace_path}
)

print(f"   Status: {deploy_response.status_code}")

if deploy_response.status_code in [200, 201]:
    print("   ✅ Deployment triggered!")
else:
    print(f"   Response: {deploy_response.text}")

# Final status check
print(f"\n📊 Final Status Check...")
status_response = requests.get(
    f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
    headers=headers
)

if status_response.status_code == 200:
    app_info = status_response.json()
    print(f"\n   App Name: {app_info.get('name')}")
    print(f"   URL: {app_info.get('url')}")
    print(f"   Compute Status: {app_info.get('compute_status', {}).get('state')}")
    print(f"   App Status: {app_info.get('app_status', {}).get('state')}")

print("\n" + "="*60)
print("🎉 DEPLOYMENT SUBMITTED!")
print("="*60)
print(f"\n🌐 Your app URL:")
print(f"   {app_info.get('url')}")
print(f"\n📱 Or access via Databricks UI:")
print(f"   {DATABRICKS_HOST}/#apps")
print(f"\n⏳ The app may take 2-3 minutes to start...")
print("   Refresh the URL to see when it's ready!")

