# Local Incident Charts Fix

## Issue Identified

The Recent Incident Analysis charts were not loading locally, but were working in the deployed Databricks environment.

## Root Cause

**Vite proxy configuration mismatch:**
- Vite dev server was configured to proxy `/api` requests to `http://localhost:8080`
- Flask backend was actually running on `http://localhost:8000`
- This caused all API requests from the frontend to fail with connection errors

## Solution

Updated `vite.config.js` to point to the correct Flask backend port:

```javascript
// Before (incorrect)
proxy: {
  '/api': {
    target: 'http://localhost:8080',  // ❌ Wrong port
    changeOrigin: true,
  }
}

// After (correct)
proxy: {
  '/api': {
    target: 'http://localhost:8000',  // ✅ Correct port
    changeOrigin: true,
  }
}
```

## Why It Worked in Databricks

In the deployed Databricks Apps environment:
- The Flask app serves both the static files AND the API endpoints
- No proxy is needed - the frontend and backend are on the same origin
- All `/api/*` requests go directly to the Flask app without any proxy configuration

## Verification

Tested that the Flask backend is accessible:
```bash
curl -X POST http://localhost:8000/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT COUNT(*) FROM hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105"}'
```

Result: ✅ Returns 1,989,685 rows

## Files Changed

1. **`vite.config.js`** - Updated proxy target from port 8080 to 8000
2. **`src/pages/MetricsExplained.jsx`** - Added comprehensive documentation for Recent Incident Analysis

## Testing

After this fix:
1. Restart Vite dev server (if needed): `npm run dev`
2. Navigate to http://localhost:5173
3. Recent Incident Analysis charts should now load
4. Check browser console for successful API calls

## Additional Notes

- Flask backend runs on port 8000 (confirmed via `lsof -i :8000`)
- Vite dev server runs on port 5173
- The proxy configuration is only used in local development
- Production/Databricks deployment doesn't use the proxy at all
