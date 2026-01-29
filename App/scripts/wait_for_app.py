#!/usr/bin/env python3
import os

import requests
import time
import json

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
APP_NAME = "glucostream-dashboard"

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

print("Waiting for app to be ready for deployment...")
print("(This can take 2-5 minutes)")

max_attempts = 20
attempt = 0

while attempt < max_attempts:
    attempt += 1
    response = requests.get(
        f"{DATABRICKS_HOST}/api/2.0/apps/{APP_NAME}",
        headers=headers
    )
    
    if response.status_code == 200:
        app_data = response.json()
        compute_state = app_data.get('compute_status', {}).get('state')
        app_state = app_data.get('app_status', {}).get('state')
        
        print(f"[{attempt}/{max_attempts}] Compute: {compute_state}, App: {app_state}")
        
        if compute_state in ['ACTIVE', 'STOPPED']:
            print(f"\n✅ App is ready for deployment!")
            print(f"   Default source path: {app_data.get('default_source_code_path', 'Not set')}")
            print(f"   URL: {app_data.get('url')}")
            
            # Show full app info
            print(f"\n📋 Full App Configuration:")
            print(json.dumps(app_data, indent=2))
            break
        
        time.sleep(15)
    else:
        print(f"Error checking status: {response.status_code}")
        break

else:
    print(f"\n⏰ Timeout waiting for app to be ready")
    print(f"   Check status manually at:")
    print(f"   {DATABRICKS_HOST}/#apps")

