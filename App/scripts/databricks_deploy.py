#!/usr/bin/env python3
"""
Databricks Apps Deployment Script
Deploys a React/Static web app to Databricks Apps platform

Usage:
    python databricks_deploy.py

Configuration:
    Edit databricks_config.json with your workspace details
"""

import requests
import json
import base64
import os
import sys
from pathlib import Path

# Load configuration
def load_config():
    """Load Databricks configuration from file"""
    # Determine the config path (handle both direct call and call from deploy.py)
    config_file = "config/databricks_config.json"
    if not os.path.exists(config_file):
        config_file = "../config/databricks_config.json"
    
    if not os.path.exists(config_file):
        print(f"❌ Config file not found: {config_file}")
        print("   Create it using config/databricks_config.example.json as template")
        sys.exit(1)
    
    with open(config_file, 'r') as f:
        return json.load(f)

config = load_config()

DATABRICKS_HOST = config['databricks_host']
DATABRICKS_TOKEN = config['databricks_token']
APP_NAME = config['app_name']
WORKSPACE_PATH = config.get('workspace_path', 
    f"/Workspace/Users/{config.get('username', 'user')}/.bundle/{APP_NAME}/files")
BUILD_DIR = config.get('build_dir', 'dist')

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

def create_workspace_dir(path):
    """Create a workspace directory"""
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/mkdirs",
        headers=headers,
        json={"path": path}
    )
    return response

def upload_file(local_path, workspace_path):
    """Upload a file to Databricks workspace"""
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

def check_app_exists():
    """Check if app already exists"""
    response = requests.get(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
        headers=headers
    )
    return response.status_code == 200

def create_app():
    """Create a new Databricks App"""
    app_config = {
        "name": APP_NAME,
        "description": config.get('app_description', 'Web application deployed via Databricks Apps')
    }
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/apps",
        headers=headers,
        json=app_config
    )
    return response

def wait_for_compute():
    """Wait for compute to be ACTIVE"""
    import time
    max_attempts = 40
    
    for attempt in range(max_attempts):
        response = requests.get(
            f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
            headers=headers
        )
        
        if response.status_code == 200:
            app_data = response.json()
            compute_state = app_data.get('compute_status', {}).get('state')
            
            if compute_state == 'ACTIVE':
                return True
            elif compute_state in ['FAILED', 'TERMINATED']:
                return False
            
            if attempt % 4 == 0:  # Print every minute
                print(f"   ⏳ Waiting for compute ({compute_state})...")
        
        time.sleep(15)
    
    return False

def deploy():
    """Main deployment function"""
    print("="*70)
    print(f"🚀 DEPLOYING TO DATABRICKS APPS")
    print("="*70)
    print(f"\nApp Name: {APP_NAME}")
    print(f"Host: {DATABRICKS_HOST}")
    print(f"Build Dir: {BUILD_DIR}")
    
    # Step 1: Check/Create App
    print("\n1️⃣  Checking app status...")
    if check_app_exists():
        print(f"   ✅ App '{APP_NAME}' exists")
        
        # Check compute state
        response = requests.get(
            f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
            headers=headers
        )
        app_data = response.json()
        compute_state = app_data.get('compute_status', {}).get('state')
        
        if compute_state != 'ACTIVE':
            print(f"   ⏳ Compute is {compute_state}, waiting for ACTIVE state...")
            if not wait_for_compute():
                print("   ❌ Compute failed to become ACTIVE")
                return False
    else:
        print(f"   Creating new app '{APP_NAME}'...")
        response = create_app()
        
        if response.status_code in [200, 201]:
            print(f"   ✅ App created successfully")
            print(f"   ⏳ Waiting for compute to provision...")
            if not wait_for_compute():
                print("   ❌ Compute failed to start")
                return False
        else:
            print(f"   ❌ Failed to create app: {response.text}")
            return False
    
    # Step 2: Create directories
    print("\n2️⃣  Creating workspace directories...")
    dirs_to_create = [
        WORKSPACE_PATH,
        f"{WORKSPACE_PATH}/{BUILD_DIR}",
    ]
    
    # Add subdirectories if they exist
    if os.path.exists(BUILD_DIR):
        for root, dirs, _ in os.walk(BUILD_DIR):
            for d in dirs:
                rel_path = os.path.relpath(os.path.join(root, d), BUILD_DIR)
                dirs_to_create.append(f"{WORKSPACE_PATH}/{BUILD_DIR}/{rel_path}".replace("\\", "/"))
    
    for dir_path in dirs_to_create:
        response = create_workspace_dir(dir_path)
        if response.status_code == 200:
            print(f"   ✅ {dir_path}")
        else:
            print(f"   ⚠️  {dir_path}: {response.status_code}")
    
    # Step 3: Upload files
    print("\n3️⃣  Uploading application files...")
    
    # Upload app.py (check both databricks/ and root)
    app_py_path = 'databricks/app.py' if os.path.exists('databricks/app.py') else 'app.py'
    if os.path.exists(app_py_path):
        print("   📄 Uploading app.py...")
        response = upload_file(app_py_path, f"{WORKSPACE_PATH}/app.py")
        print(f"      {'✅' if response.status_code == 200 else '❌'} Status: {response.status_code}")
    
    # Upload app.yaml (check both databricks/ and root)
    app_yaml_path = 'databricks/app.yaml' if os.path.exists('databricks/app.yaml') else 'app.yaml'
    if os.path.exists(app_yaml_path):
        print("   📄 Uploading app.yaml...")
        response = upload_file(app_yaml_path, f"{WORKSPACE_PATH}/app.yaml")
        print(f"      {'✅' if response.status_code == 200 else '❌'} Status: {response.status_code}")
    
    # Upload build directory
    print(f"\n   📦 Uploading {BUILD_DIR}/ folder...")
    uploaded_count = 0
    failed_count = 0
    
    if os.path.exists(BUILD_DIR):
        for file_path in Path(BUILD_DIR).rglob("*"):
            if file_path.is_file():
                rel_path = file_path.relative_to(BUILD_DIR)
                ws_file_path = f"{WORKSPACE_PATH}/{BUILD_DIR}/{rel_path}".replace("\\", "/")
                
                response = upload_file(str(file_path), ws_file_path)
                if response.status_code == 200:
                    uploaded_count += 1
                    print(f"      ✅ {rel_path}")
                else:
                    failed_count += 1
                    print(f"      ❌ {rel_path}: {response.status_code}")
    
    print(f"\n   📊 Uploaded: {uploaded_count} | Failed: {failed_count}")
    
    # Step 4: Link source code
    print("\n4️⃣  Linking source code to app...")
    update_response = requests.patch(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
        headers=headers,
        json={"source_code_path": WORKSPACE_PATH}
    )
    
    if update_response.status_code == 200:
        print(f"   ✅ Source code linked")
    else:
        print(f"   ⚠️  Status: {update_response.status_code}")
        print(f"   Response: {update_response.text}")
    
    # Step 5: Deploy
    print("\n5️⃣  Triggering deployment...")
    deploy_response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}/deployments",
        headers=headers,
        json={"source_code_path": WORKSPACE_PATH}
    )
    
    if deploy_response.status_code in [200, 201]:
        print(f"   ✅ Deployment triggered")
        deploy_data = deploy_response.json()
        print(f"   Deployment ID: {deploy_data.get('deployment_id', 'N/A')}")
    else:
        print(f"   ⚠️  Status: {deploy_response.status_code}")
        print(f"   Response: {deploy_response.text}")
    
    # Step 6: Get final status
    print("\n6️⃣  Getting app status...")
    status_response = requests.get(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
        headers=headers
    )
    
    if status_response.status_code == 200:
        app_info = status_response.json()
        app_url = app_info.get('url', 'N/A')
        
        print("\n" + "="*70)
        print("✅ DEPLOYMENT COMPLETE!")
        print("="*70)
        print(f"\n🌐 App URL: {app_url}")
        print(f"\n📱 Databricks Apps: {DATABRICKS_HOST}/#apps/{APP_NAME}")
        print(f"\n⏳ App may take 1-2 minutes to start.")
        print("="*70)
        
        return True
    
    return False

if __name__ == "__main__":
    try:
        success = deploy()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Deployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Deployment failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

