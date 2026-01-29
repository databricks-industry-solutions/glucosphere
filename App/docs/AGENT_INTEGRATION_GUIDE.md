# 🤖 Multi-Agent Supervisor Integration Guide

## Overview

Your Device Support Dashboard now includes an AI-powered chat interface powered by a Databricks Multi-Agent Supervisor!

---

## 🎯 What Was Added

### **AI Chat Interface**
- Located in the "Device Troubleshooting Intelligence" section
- Real-time conversation with the multi-agent supervisor
- Context-aware responses based on device issues
- Conversation history maintained during session

### **New Files Created:**

1. **`src/components/AgentChatInterface.jsx`**
   - React component for the chat UI
   - Handles messages, loading states, errors
   - Suggested queries for quick access

2. **`src/api/databricksAgent.js`**
   - API integration with Databricks serving endpoint
   - Handles authentication and request formatting
   - Error handling and response parsing

3. **`.env.local`**
   - Environment variables for configuration
   - Contains Databricks token (gitignored)

---

## 🔧 Configuration

### **Endpoint Details:**
- **Endpoint Name:** `mas-5a566f25-endpoint`
- **Full Name:** Medtech dash LDP dash multi agent dash supervisor
- **Workspace:** https://fe-vm-industry-solutions-buildathon.cloud.databricks.com
- **API URL:** `{workspace}/serving-endpoints/{endpoint_name}/invocations`

### **Authentication:**
- Uses Bearer token authentication
- Token stored in `.env.local` file
- Token: `[REDACTED_TOKEN]`

---

## 🚀 Local Development

### **1. Install Dependencies** (if not already done):
```bash
npm install
```

### **2. Verify Environment Variables:**
Check that `.env.local` exists with:
```env
VITE_DATABRICKS_TOKEN=[REDACTED_TOKEN]
```

### **3. Start Development Server:**
```bash
npm run dev
```

### **4. Test the Chat:**
1. Navigate to Device Support Dashboard
2. Scroll to "Device Troubleshooting Intelligence" section
3. Try the suggested queries or type your own

---

## 💡 How It Works

### **Request Flow:**

```
User Message 
    ↓
AgentChatInterface Component
    ↓
databricksAgent.js API Call
    ↓
POST to Databricks Serving Endpoint
    ↓
Multi-Agent Supervisor Processing
    ↓
Response Back to Chat
```

### **API Request Format:**
```javascript
{
  "messages": [
    {
      "role": "user",
      "content": "User's message here"
    }
  ]
}
```

### **Expected Response Format:**
```javascript
{
  "choices": [
    {
      "message": {
        "content": "Agent's response here"
      }
    }
  ]
}
```

Or:
```javascript
{
  "response": "Agent's response here"
}
```

---

## 🧪 Testing

### **Test Queries:**
Try these to verify the integration:

1. **"Sensor drift in cold temperatures"**
   - Tests device troubleshooting knowledge

2. **"Calibration error troubleshooting"**
   - Tests step-by-step guidance

3. **"Adhesive failure solutions"**
   - Tests problem-solving abilities

4. **"Battery drain issues"**
   - Tests diagnostic capabilities

---

## 🐛 Troubleshooting

### **Common Issues:**

#### **1. "Connection Error"**
- **Cause:** Token might be invalid or endpoint not accessible
- **Fix:** Check token in `.env.local`
- **Verify:** Test endpoint directly:
  ```bash
  curl -X POST \
    "https://fe-vm-industry-solutions-buildathon.cloud.databricks.com/serving-endpoints/mas-5a566f25-endpoint/invocations" \
    -H "Authorization: Bearer [REDACTED_TOKEN]" \
    -H "Content-Type: application/json" \
    -d '{"messages":[{"role":"user","content":"test"}]}'
  ```

#### **2. "CORS Error"**
- **Cause:** Browser blocking cross-origin requests
- **Fix:** This should work when deployed to Databricks Apps (same origin)
- **Workaround for local:** May need proxy configuration

#### **3. "Endpoint not found"**
- **Cause:** Endpoint name might be different
- **Fix:** Verify endpoint name in Databricks workspace
- **Update:** Change in `src/api/databricksAgent.js`

---

## 📝 Customization

### **Change Endpoint:**
Edit `src/api/databricksAgent.js`:
```javascript
const DATABRICKS_CONFIG = {
  workspace_url: 'your-workspace-url',
  endpoint_name: 'your-endpoint-name',
  token: import.meta.env.VITE_DATABRICKS_TOKEN
};
```

### **Modify Chat Appearance:**
Edit `src/components/AgentChatInterface.jsx`:
- Change colors in className strings
- Adjust message styling
- Add custom features

### **Add Context:**
Modify the API call to include device context:
```javascript
const response = await callMultiAgentSupervisor(
  userMessage, 
  conversationHistory,
  {
    deviceId: selectedDevice.id,
    deviceModel: selectedDevice.model
  }
);
```

---

## 🚀 Deployment

### **For Local Testing:**
```bash
npm run dev
# Chat will work with direct API calls
```

### **For Databricks Apps:**
```bash
npm run build
python3 deploy.py buildathon
# Chat will work seamlessly (same origin)
```

### **Environment Variables in Production:**
The Databricks token is included in the build. For better security in production:
1. Move authentication to backend
2. Use Databricks workspace authentication
3. Implement token refresh mechanism

---

## 🔒 Security Notes

### **Current Setup (Development):**
- ✅ Token in `.env.local` (gitignored)
- ✅ Not committed to repository
- ⚠️  Token embedded in build for simplicity

### **Production Recommendations:**
1. **Backend Proxy:** Route API calls through your backend
2. **Workspace Auth:** Use Databricks workspace authentication
3. **Token Refresh:** Implement token rotation
4. **Rate Limiting:** Add rate limiting to prevent abuse

---

## 📊 Features

### **Current Features:**
- ✅ Real-time chat interface
- ✅ Conversation history
- ✅ Loading states
- ✅ Error handling
- ✅ Suggested queries
- ✅ Timestamp display
- ✅ Auto-scroll to latest message

### **Possible Enhancements:**
- 📋 Copy message to clipboard
- 💾 Save conversation history
- 📤 Export chat transcript
- 🔍 Search within conversation
- 📎 Attach device data to messages
- 🎯 Quick action buttons from responses

---

## 🎊 Success!

Your Device Support Dashboard now has AI-powered troubleshooting! The chat interface will help users get instant answers about device issues using your multi-agent supervisor.

**Test it now:**
```bash
npm run dev
```

Then navigate to Device Support Dashboard → Device Troubleshooting Intelligence section!

