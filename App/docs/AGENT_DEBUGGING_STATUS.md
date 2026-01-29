# 🔍 Multi-Agent Supervisor Debugging Status

**Date:** January 7, 2026  
**Status:** 🔧 In Progress

---

## Current Situation

### ✅ What's Working

1. **Backend Proxy Setup** - Flask server running on port 8000
2. **CORS Issue Resolved** - Proxy architecture implemented
3. **Authentication** - Token properly loaded from environment
4. **Request Routing** - Frontend → Vite → Flask → Databricks
5. **Connection Established** - Requests reaching Databricks endpoint

### ❌ Current Issue

**Symptom:** Request timeout after 60 seconds

```json
{
  "error": "Read timed out. (read timeout=60)"
}
```

### 🔍 Investigation

#### Endpoint Details
- **Name:** `mas-5a566f25-endpoint`
- **Display Name:** "Medtech dash LDP dash multi agent dash supervisor"
- **Workspace:** `fe-vm-industry-solutions-buildathon.cloud.databricks.com`
- **Status:** User confirmed it works in Databricks playground

#### Payload Format Attempts

**Attempt 1: Using `messages` field**
```json
{
  "messages": [
    {"role": "user", "content": "What causes sensor drift?"}
  ]
}
```
**Result:** ❌ `BAD_REQUEST - Model is missing inputs ['input']`

**Attempt 2: Using `input` field**
```json
{
  "input": [
    {"role": "user", "content": "What causes sensor drift?"}
  ]
}
```
**Result:** ⏱️ Timeout after 60 seconds

---

## Next Steps

### 1. Verify Playground Request Format

**Action Needed:** Test in Databricks playground and inspect the actual request:

1. Go to Databricks workspace
2. Navigate to **Serving → Endpoints**
3. Click on `mas-5a566f25-endpoint`
4. Click **"Query Endpoint"** or **"Playground"** tab
5. Send a test message
6. Open browser DevTools (F12) → Network tab
7. Find the request to `/invocations`
8. Copy the **exact payload** used

### 2. Check Endpoint Schema

The error message showed expected schema:
```
['context': {conversation_id: string (optional), user_id: string (optional)} (optional),
 'custom_inputs': Map(str -> Any) (optional),
 'input': Array(Any) (required),
 'max_output_tokens': long (optional),
 'metadata': Map(str -> DataType.string) (optional),
 ...
]
```

Possible formats to try:
```json
// Option A: Simple text input
{
  "input": "What causes sensor drift?"
}

// Option B: Array of strings
{
  "input": ["What causes sensor drift?"]
}

// Option C: Structured conversation
{
  "input": [
    {"content": "What causes sensor drift?"}
  ]
}

// Option D: With context
{
  "input": "What causes sensor drift?",
  "context": {
    "conversation_id": "test-123"
  }
}
```

### 3. Check Endpoint Status

Verify in Databricks UI:
- [ ] Endpoint state is "Ready"
- [ ] No recent errors in endpoint logs
- [ ] Compute is active
- [ ] No rate limiting

### 4. Test Direct API Call

Try calling the endpoint directly with curl (not through proxy):

```bash
curl -X POST \
  https://fe-vm-industry-solutions-buildathon.cloud.databricks.com/serving-endpoints/mas-5a566f25-endpoint/invocations \
  -H "Authorization: Bearer [REDACTED_TOKEN]" \
  -H "Content-Type: application/json" \
  -d '{"input": "test"}'
```

---

## Technical Details

### Files Modified

| File | Status | Purpose |
|------|--------|---------|
| `databricks/app.py` | ✅ Updated | Backend proxy with `input` field |
| `src/api/databricksAgent.js` | ✅ Updated | Smart routing + logging |
| `vite.config.js` | ✅ Updated | Dev proxy config |
| `run_backend.sh` | ✅ Created | Backend startup |
| `.env.local` | ✅ Created | Credentials |

### Current Backend Code

```python
payload = {
    'input': messages  # Changed from 'messages' to 'input'
}

response = requests.post(
    endpoint_url,
    headers={
        'Authorization': f'Bearer {DATABRICKS_TOKEN}',
        'Content-Type': 'application/json'
    },
    json=payload,
    timeout=60
)
```

---

## Questions for User

1. **What format do you use in the playground?**
   - Please share the exact JSON payload
   - Screenshot or copy from Network tab

2. **How does the conversation history work?**
   - Does each request include full history?
   - Or does the endpoint maintain session state?

3. **Are there any special parameters needed?**
   - Context IDs?
   - User IDs?
   - Custom inputs?

---

## Potential Solutions

### Solution A: Match Playground Format Exactly

Once we know the exact format from the playground, update `databricks/app.py`:

```python
# Example if playground uses simple string
payload = {
    'input': messages[-1]['content']  # Just the last message
}

# OR if it needs conversation history differently
payload = {
    'input': ' '.join([m['content'] for m in messages])
}
```

### Solution B: Add Required Context

```python
payload = {
    'input': messages,
    'context': {
        'conversation_id': str(uuid.uuid4()),
        'user_id': 'dashboard_user'
    }
}
```

### Solution C: Simplify Message Format

```python
# Convert from role/content to just content
payload = {
    'input': [msg['content'] for msg in messages]
}
```

---

## Testing Commands

```bash
# Test backend directly
curl -X POST http://localhost:8000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}'

# Check backend logs
cat /Users/justin.ward/.cursor/projects/Users-justin-ward-Desktop-code-buildathon/terminals/4.txt

# Restart backend
lsof -ti:8000 | xargs kill -9
./run_backend.sh

# Check if backend is running
curl http://localhost:8000/
```

---

## Next Action

**Waiting for:** User to provide the exact request format used in the Databricks playground.

Once we have that, we can:
1. Update the backend payload format
2. Test and verify
3. Deploy to production

---

**Status:** ⏸️ Paused - Need playground request format from user

