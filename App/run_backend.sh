#!/bin/bash

# Run Flask backend for local development
# This backend acts as a proxy to avoid CORS issues

echo "🚀 Starting Flask Backend (Port 8000)..."
echo ""
echo "This backend proxies requests to the Databricks multi-agent supervisor"
echo "to avoid CORS issues during local development."
echo ""

# Check if .env.local exists for environment variables
if [ -f .env.local ]; then
    echo "✅ Loading environment variables from .env.local"
    export $(cat .env.local | grep -v '^#' | xargs)
else
    echo "⚠️  Warning: .env.local not found"
    echo "   Create .env.local with:"
    echo "   DATABRICKS_HOST=your_workspace_url"
    echo "   DATABRICKS_TOKEN=your_token"
    echo ""
fi

# Check if token is set
if [ -z "$DATABRICKS_TOKEN" ]; then
    echo "❌ Error: DATABRICKS_TOKEN environment variable not set"
    echo ""
    echo "Please create a .env.local file with:"
    echo "DATABRICKS_HOST=https://your-workspace.cloud.databricks.com"
    echo "DATABRICKS_TOKEN=dapi..."
    echo ""
    exit 1
fi

echo "🔧 Configuration:"
echo "   Host: ${DATABRICKS_HOST}"
echo "   Token: ${DATABRICKS_TOKEN:0:15}..."
echo ""

cd databricks
python3 app.py

