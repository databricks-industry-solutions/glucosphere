# 🤖 Multi-Agent Supervisor Troubleshooting Guide

## Overview

The Device Support Dashboard includes an AI chat interface powered by a Databricks Multi-Agent Supervisor. This guide explains how the integration works and how to troubleshoot common issues.

---

## 🏗️ Architecture

### Local Development
```
Browser (localhost:5173)
    ↓ /api/agent/query
Vite Dev Server (proxy)
    ↓
Flask Backend (localhost:8000)
    ↓ [with auth token]
Databricks Multi-Agent Supervisor Endpoint
```

### Production (Databricks Apps)
```
Browser
    ↓ /api/agent/query
Flask App (Databricks)
    ↓ [with auth token]
Databricks Multi-Agent Supervisor Endpoint
```

---

## 🚀 Setup Instructions

### Prerequisites

1. **Databricks Multi-Agent Supervisor Endpoint**
   - Endpoint name: `mas-5a566f25-endpoint`
   - Must be deployed in the same workspace
   - Endpoint must be active and serving

2. **Environment Variables**
   Create `.env.local` in the project root:
   ```bash
   DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
   DATABRICKS_TOKEN=dapi...your_token_here
   VITE_DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
   VITE_DATABRICKS_TOKEN=dapi...your_token_here
   ```

### Running Locally

**Terminal 1 - Frontend:**
```bash
npm run dev
# Runs on http://localhost:5173
```

**Terminal 2 - Backend:**
```bash
./run_backend.sh
# Runs on http://localhost:8000
```

The frontend will automatically proxy `/api/*` requests to the backend.

---

## 🔍 How It Works

### 1. **Frontend Request** (`src/api/databricksAgent.js`)
   - Detects if running on localhost
   - Routes requests through `/api/agent/query` proxy
   - Sends conversation history in the request

### 2. **Backend Proxy** (`databricks/app.py`)
   - Receives request from frontend
   - Adds authentication token (from env vars)
   - Forwards to Databricks endpoint
   - Returns response to frontend

### 3. **Frontend Display** (`src/components/AgentChatInterface.jsx`)
   - Displays messages in chat interface
   - Handles loading states and errors
   - Parses agent responses

---

## ❌ Common Issues

### Issue: "Failed to fetch" Error

**Symptom:** Chat shows "Failed to fetch: This is likely a CORS or network issue"

**Causes:**
1. Backend not running
2. Environment variables not set
3. Token expired or invalid
4. Endpoint not active

**Solution:**
```bash
# 1. Check if backend is running
curl http://localhost:8000/api/agent/query

# 2. Verify environment variables
cat .env.local

# 3. Check backend logs
# Look for errors in the terminal running ./run_backend.sh

# 4. Test endpoint directly in Databricks playground
```

### Issue: Backend Won't Start

**Symptom:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
```bash
pip3 install flask requests
```

### Issue: "DATABRICKS_TOKEN environment variable not set"

**Symptom:** Backend starts but API calls fail with 500 error

**Solution:**
```bash
# Create .env.local with your token
echo "DATABRICKS_HOST=https://your-workspace.cloud.databricks.com" > .env.local
echo "DATABRICKS_TOKEN=dapi..." >> .env.local

# Restart backend
./run_backend.sh
```

### Issue: "401 Unauthorized" or "403 Forbidden"

**Symptom:** API calls return authentication errors

**Causes:**
1. Token expired
2. Token doesn't have access to the endpoint
3. Wrong workspace URL

**Solution:**
```bash
# 1. Generate new token in Databricks
#    User Settings → Access Tokens → Generate New Token

# 2. Update .env.local with new token

# 3. Verify endpoint permissions in Databricks:
#    - Go to Serving → Endpoints
#    - Click on mas-5a566f25-endpoint
#    - Check "Permissions" tab
#    - Ensure your user has "Can Query" permission
```

### Issue: Endpoint Not Responding

**Symptom:** Requests timeout or take very long

**Causes:**
1. Endpoint is stopped or starting
2. Model serving compute is inactive
3. High load on endpoint

**Solution:**
1. Check endpoint status in Databricks:
   - Go to **Serving → Endpoints**
   - Find `mas-5a566f25-endpoint`
   - Status should be **"Ready"**

2. Test in playground:
   - Click "Query Endpoint" in Databricks UI
   - Send test message
   - Verify response

3. Check logs:
   - View endpoint logs in Databricks
   - Look for errors or timeouts

---

## 🧪 Testing

### Test Backend Directly

```bash
# Test with curl
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

### Test in Browser Console

```javascript
// Open browser console (F12) and run:
fetch('/api/agent/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [{ role: 'user', content: 'Test message' }]
  })
})
.then(r => r.json())
.then(console.log)
```

### Test Endpoint in Databricks

1. Go to **Serving → Endpoints**
2. Click on `mas-5a566f25-endpoint`
3. Click **"Query Endpoint"** tab
4. Enter test message
5. Verify response

---

## 📝 Configuration Details

### Endpoint Configuration

- **Name:** `mas-5a566f25-endpoint`
- **Type:** Multi-Agent Supervisor
- **Display Name:** "Medtech dash LDP dash multi agent dash supervisor"
- **Request Format:**
  ```json
  {
    "messages": [
      {"role": "user", "content": "your message here"}
    ]
  }
  ```

### Response Format

Expected response structure:
```json
{
  "choices": [
    {
      "message": {
        "content": "Agent response here"
      }
    }
  ]
}
```

Or alternate format:
```json
{
  "response": "Agent response here"
}
```

---

## 🔐 Security Notes

1. **Never commit `.env.local`** - It contains sensitive tokens
2. **Tokens expire** - Regenerate periodically
3. **Minimum permissions** - Token only needs "Can Query" on endpoint
4. **Production deployment** - Uses Databricks App's secure environment

---

## 📚 Related Files

- `src/api/databricksAgent.js` - API client
- `src/components/AgentChatInterface.jsx` - Chat UI component
- `databricks/app.py` - Backend proxy server
- `vite.config.js` - Development proxy configuration
- `run_backend.sh` - Backend startup script

---

## 🆘 Still Having Issues?

1. **Check browser console** (F12 → Console tab)
2. **Check backend logs** (terminal running Flask)
3. **Check Vite logs** (terminal running npm run dev)
4. **Test endpoint in Databricks UI**
5. **Verify token and permissions**

---

**Last Updated:** January 2026

