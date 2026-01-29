#!/usr/bin/env python3

import requests
import json
import os
import base64
from pathlib import Path

# Configuration
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
APP_NAME = "glucostream-dashboard"

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

# Test connection
print("Testing Databricks connection...")
response = requests.get(f"{DATABRICKS_HOST}/api/2.0/clusters/list", headers=headers)
print(f"Connection test: {response.status_code}")

if response.status_code == 200:
    print("✅ Connected to Databricks successfully!")
else:
    print(f"❌ Connection failed: {response.text}")
    exit(1)

# Check if Apps API is available
print("\nChecking for Databricks Apps support...")
apps_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/preview/apps", headers=headers)

if apps_response.status_code == 200:
    print("✅ Databricks Apps API is available!")
    
    # Create or update app
    app_config = {
        "name": APP_NAME,
        "description": "GlucoStream Intelligence Dashboard - Glucose Monitoring Platform",
        "resources": [
            {
                "name": "frontend",
                "description": "React frontend application",
                "subdomain": APP_NAME
            }
        ]
    }
    
    print(f"\nDeploying app: {APP_NAME}...")
    create_response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/preview/apps",
        headers=headers,
        json=app_config
    )
    
    print(f"Deployment response: {create_response.status_code}")
    print(create_response.text)
    
else:
    print(f"⚠️  Databricks Apps API not available (status: {apps_response.status_code})")
    print("This workspace may not have Databricks Apps enabled.")
    print("\nAlternative: Upload files to workspace and serve via notebook.")

print("\n" + "="*50)
print("DEPLOYMENT OPTIONS:")
print("="*50)
print("\n1. DBFS Upload Method:")
print("   - Upload dist/ folder to DBFS")
print("   - Create a notebook to serve the files")
print("   - Run notebook as a job")
print("\n2. Workspace Files Method:")
print("   - Upload files to workspace")
print("   - Use Python notebook with Flask")
print("\n3. External Hosting (Recommended for production):")
print("   - Deploy to Vercel, Netlify, or AWS S3")
print("   - Much simpler for static React apps")

