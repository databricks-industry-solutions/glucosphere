#!/usr/bin/env python3
"""
Upload the built React app to Databricks FileStore
"""

import requests
import base64
import os
from pathlib import Path

DATABRICKS_HOST = os.environ.get("DATABRICKS_HOST", "https://<your-workspace-host>")
DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN")
if not DATABRICKS_TOKEN:
    raise SystemExit("Missing DATABRICKS_TOKEN. Set it in App/.env or your environment.")
headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
}

def upload_file_to_dbfs(local_path, dbfs_path):
    """Upload a file to DBFS"""
    with open(local_path, 'rb') as f:
        content = f.read()
    
    content_b64 = base64.b64encode(content).decode()
    
    # Create/overwrite file
    data = {
        "path": dbfs_path,
        "contents": content_b64,
        "overwrite": True
    }
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/dbfs/put",
        headers=headers,
        json=data
    )
    
    return response

def upload_directory(local_dir, dbfs_base):
    """Recursively upload a directory to DBFS"""
    local_path = Path(local_dir)
    uploaded = []
    failed = []
    
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Calculate relative path
            rel_path = file_path.relative_to(local_path)
            dbfs_path = f"{dbfs_base}/{rel_path}".replace('\\', '/')
            
            print(f"Uploading: {rel_path} → {dbfs_path}")
            
            response = upload_file_to_dbfs(str(file_path), dbfs_path)
            
            if response.status_code == 200:
                uploaded.append(str(rel_path))
                print(f"  ✅ Success")
            else:
                failed.append(str(rel_path))
                print(f"  ❌ Failed: {response.status_code} - {response.text}")
    
    return uploaded, failed

if __name__ == "__main__":
    print("="*60)
    print("Uploading GlucoStream Dashboard to Databricks")
    print("="*60)
    
    dist_folder = "dist"
    dbfs_path = "/FileStore/glucostream"
    
    if not os.path.exists(dist_folder):
        print(f"\n❌ Error: {dist_folder} folder not found!")
        print("Please run 'npm run build' first.")
        exit(1)
    
    print(f"\nUploading from: {dist_folder}")
    print(f"Uploading to: {dbfs_path}")
    print()
    
    uploaded, failed = upload_directory(dist_folder, dbfs_path)
    
    print("\n" + "="*60)
    print("UPLOAD SUMMARY")
    print("="*60)
    print(f"✅ Successfully uploaded: {len(uploaded)} files")
    if failed:
        print(f"❌ Failed: {len(failed)} files")
        for f in failed:
            print(f"   - {f}")
    
    if len(uploaded) > 0 and len(failed) == 0:
        print("\n🎉 SUCCESS! Your app is now deployed!")
        print(f"\n📱 Access your app at:")
        print(f"{DATABRICKS_HOST}/files/glucostream/index.html")
        print(f"\n📋 Alternative access:")
        print(f"1. Go to your Databricks workspace")
        print(f"2. Navigate to: Data → FileStore → glucostream")
        print(f"3. Click on index.html")
    else:
        print("\n⚠️  Some files failed to upload. Check the errors above.")

