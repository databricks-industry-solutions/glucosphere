#!/usr/bin/env python3
import os

import requests
import json

# New Azure Databricks workspace
DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("="*60)
print("Testing Azure Databricks Workspace")
print("="*60)

# Test connection
print("\n1. Testing connection...")
response = requests.get(f"{DATABRICKS_HOST}/api/2.0/clusters/list", headers=headers)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    print("   ✅ Connected successfully!")
else:
    print(f"   ❌ Connection failed: {response.text}")
    exit(1)

# Check for Apps API
print("\n2. Checking Databricks Apps API...")
apps_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/apps", headers=headers)
print(f"   Status: {apps_response.status_code}")

if apps_response.status_code == 200:
    print("   ✅ Apps API is available!")
    apps = apps_response.json()
    print(f"   Existing apps: {len(apps.get('apps', []))}")
elif apps_response.status_code == 404:
    print("   ℹ️  Apps API endpoint not found - trying preview endpoint...")
    apps_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/preview/apps", headers=headers)
    if apps_response.status_code == 200:
        print("   ✅ Preview Apps API is available!")
    else:
        print(f"   ❌ Apps API not available (status: {apps_response.status_code})")
else:
    print(f"   Status: {apps_response.status_code}")
    print(f"   Response: {apps_response.text[:200]}")

# Check DBFS access
print("\n3. Checking DBFS access...")
dbfs_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/dbfs/list?path=/", headers=headers)
print(f"   Status: {dbfs_response.status_code}")

if dbfs_response.status_code == 200:
    print("   ✅ DBFS access granted!")
else:
    print(f"   ⚠️  DBFS may be restricted: {dbfs_response.status_code}")

# Check workspace access
print("\n4. Checking Workspace access...")
ws_response = requests.get(f"{DATABRICKS_HOST}/api/2.0/workspace/list?path=/", headers=headers)
print(f"   Status: {ws_response.status_code}")

if ws_response.status_code == 200:
    print("   ✅ Workspace access granted!")
else:
    print(f"   ⚠️  Workspace access limited: {ws_response.status_code}")

print("\n" + "="*60)
print("WORKSPACE CAPABILITIES SUMMARY")
print("="*60)

