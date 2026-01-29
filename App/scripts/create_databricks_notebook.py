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
}

def create_notebook_from_content(path, content, language="PYTHON"):
    """Create or overwrite a notebook in Databricks workspace"""
    content_b64 = base64.b64encode(content.encode()).decode()
    
    data = {
        "path": path,
        "content": content_b64,
        "language": language,
        "overwrite": True,
        "format": "SOURCE"
    }
    
    response = requests.post(
        f"{DATABRICKS_HOST}/api/2.0/workspace/import",
        headers=headers,
        json=data
    )
    
    return response

# Create the notebook content
notebook_content = '''# Databricks notebook source
# MAGIC %md
# MAGIC # GlucoStream Intelligence Dashboard
# MAGIC 
# MAGIC This notebook serves the React application. 
# MAGIC 
# MAGIC **Instructions:**
# MAGIC 1. Upload the `dist/` folder contents to DBFS at `/FileStore/glucostream/`
# MAGIC 2. Run this notebook
# MAGIC 3. Access the app via the Databricks Files UI or driver proxy

# COMMAND ----------

# MAGIC %sh
# MAGIC # Create directory if it doesn't exist
# MAGIC mkdir -p /dbfs/FileStore/glucostream/

# COMMAND ----------

# MAGIC %md
# MAGIC ## Option 1: Simple HTML Display (Works immediately)

# COMMAND ----------

displayHTML("""
<div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
    <h2>📊 GlucoStream Dashboard</h2>
    <p>Your app has been built and is ready!</p>
    <p><strong>Access Methods:</strong></p>
    <ol>
        <li><strong>Download files and open locally:</strong><br/>
            The built files are in the <code>dist/</code> folder. Download <code>index.html</code> and the <code>assets</code> folder.
        </li>
        <li><strong>Upload to DBFS and serve:</strong><br/>
            Upload contents to <code>/FileStore/glucostream/</code> in DBFS, then access via:<br/>
            <code>https://dbc-daad7993-4a57.cloud.databricks.com/files/glucostream/index.html</code>
        </li>
        <li><strong>Use Databricks SQL Dashboard:</strong><br/>
            Create a SQL dashboard and embed the HTML content
        </li>
    </ol>
    <hr/>
    <p style="margin-top: 20px;"><strong>Alternative: Deploy to Free Services</strong></p>
    <ul>
        <li><a href="https://vercel.com" target="_blank">Vercel</a> (Recommended - one-click deploy)</li>
        <li><a href="https://netlify.com" target="_blank">Netlify</a></li>
        <li><a href="https://pages.github.com" target="_blank">GitHub Pages</a></li>
    </ul>
</div>
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Option 2: Flask Server (If you upload files to DBFS)

# COMMAND ----------

# MAGIC %pip install flask

# COMMAND ----------

from flask import Flask, send_file, send_from_directory
import os

# Initialize Flask app
app = Flask(__name__)

STATIC_FOLDER = "/dbfs/FileStore/glucostream"

@app.route('/')
def home():
    index_path = os.path.join(STATIC_FOLDER, 'index.html')
    if os.path.exists(index_path):
        return send_file(index_path)
    else:
        return f"""
        <h1>Upload Required</h1>
        <p>Please upload your dist/ folder contents to <code>/FileStore/glucostream/</code> in DBFS</p>
        <p>Files should be uploaded to: <code>/dbfs/FileStore/glucostream/</code></p>
        """, 404

@app.route('/<path:path>')
def serve_file(path):
    file_path = os.path.join(STATIC_FOLDER, path)
    if os.path.exists(file_path):
        return send_file(file_path)
    return "File not found", 404

# Note: In Databricks, you'll need to run this in a job or cluster
# For local development, uncomment:
# if __name__ == '__main__':
#     app.run(host='0.0.0.0', port=8080)

displayHTML("""
<div style="padding: 15px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 4px;">
    <strong>⚠️ Note:</strong> To run the Flask server in Databricks, you need to:
    <ol>
        <li>Upload files to DBFS: <code>/FileStore/glucostream/</code></li>
        <li>Run this notebook on a cluster</li>
        <li>Access via the cluster's driver proxy URL</li>
    </ol>
    <p>For easier deployment, consider using Vercel or Netlify for free hosting!</p>
</div>
""")
'''

print("Creating deployment notebook...")
response = create_notebook_from_content(
    "/Users/justin.ward@databricks.com/GlucoStream_Dashboard",
    notebook_content,
    "PYTHON"
)

if response.status_code == 200:
    print("✅ Deployment notebook created successfully!")
    print(f"\n📓 Access it at:")
    print(f"{DATABRICKS_HOST}/#notebook/{response.json().get('object_id', 'unknown')}")
    print(f"\nOr navigate to:")
    print(f"Workspace → Users → justin.ward@databricks.com → GlucoStream_Dashboard")
else:
    print(f"❌ Failed to create notebook: {response.status_code}")
    print(response.text)
    
    # Try with Shared folder instead
    print("\nTrying Shared folder...")
    response = create_notebook_from_content(
        "/Shared/GlucoStream_Dashboard",
        notebook_content,
        "PYTHON"
    )
    
    if response.status_code == 200:
        print("✅ Deployment notebook created in Shared folder!")
        print(f"\n📓 Access it at: Workspace → Shared → GlucoStream_Dashboard")
    else:
        print(f"❌ Also failed: {response.text}")

print("\n" + "="*60)
print("NEXT STEPS:")
print("="*60)
print("\n1. ✅ Your app is built and ready in the 'dist/' folder")
print("\n2. 📤 EASIEST OPTION - Upload to Databricks Files:")
print("   a. In Databricks UI, go to: Data → Add → Upload Files")
print("   b. Create folder: FileStore/glucostream/")
print("   c. Upload all files from dist/ folder")
print("   d. Access at:")
print(f"      {DATABRICKS_HOST}/files/glucostream/index.html")
print("\n3. 🚀 RECOMMENDED - Deploy to Vercel (Free & Easy):")
print("   a. Sign up at https://vercel.com")
print("   b. Run: npm install -g vercel")
print("   c. Run: vercel --prod")
print("   d. Your app will be live in seconds!")
print("\n4. 📓 Or use the notebook we just created in your workspace")

