from flask import Flask, send_from_directory, request, jsonify
import os
import requests

app = Flask(__name__)

# Static config (safe to read at startup).
# CATALOG_NAME + SCHEMA_NAME MUST be set in App/databricks/app.yaml (per-target env).
# No fallback defaults — fail loudly at startup if missing so we don't silently
# point at the wrong workspace.
ENDPOINT_NAME = os.getenv('ENDPOINT_NAME', '')
GENIE_SPACE_ID = os.getenv('GENIE_SPACE_ID', '')
CATALOG_NAME  = os.getenv('CATALOG_NAME', '')
SCHEMA_NAME   = os.getenv('SCHEMA_NAME',  '')
if not CATALOG_NAME or not SCHEMA_NAME:
    raise RuntimeError(
        f"CATALOG_NAME and SCHEMA_NAME must be set as env vars in app.yaml. "
        f"Got CATALOG_NAME={CATALOG_NAME!r}, SCHEMA_NAME={SCHEMA_NAME!r}"
    )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'static')

print(f"[STARTUP] BASE_DIR: {BASE_DIR}")
print(f"[STARTUP] STATIC_DIR: {DIST_DIR}")
print(f"[STARTUP] STATIC_DIR exists: {os.path.exists(DIST_DIR)}")
if os.path.exists(DIST_DIR):
    print(f"[STARTUP] STATIC contents: {os.listdir(DIST_DIR)}")

# Log all Databricks env vars at startup for diagnosis
db_vars = {k: v for k, v in os.environ.items() if k.startswith('DATABRICKS')}
print(f"[STARTUP] Databricks env vars present: {list(db_vars.keys())}")
print(f"[STARTUP] DATABRICKS_TOKEN set: {bool(os.getenv('DATABRICKS_TOKEN'))}")
print(f"[STARTUP] DATABRICKS_HOST: {os.getenv('DATABRICKS_HOST', '(not set)')}")

import time as _time
_token_cache = {'token': '', 'expires_at': 0}

def get_auth():
    """Read auth credentials per-request, caching M2M token for 50 minutes."""
    host = os.getenv('DATABRICKS_HOST', '')
    if host and not host.startswith('https://'):
        host = f'https://{host}'
    token = os.getenv('DATABRICKS_TOKEN', '')
    if not token:
        now = _time.time()
        if _token_cache['token'] and now < _token_cache['expires_at']:
            return host, _token_cache['token']
        client_id = os.getenv('DATABRICKS_CLIENT_ID', '')
        client_secret = os.getenv('DATABRICKS_CLIENT_SECRET', '')
        if client_id and client_secret:
            print(f"[AUTH] Fetching M2M OAuth token (client_id={client_id[:8]}...)")
            resp = requests.post(
                f"{host}/oidc/v1/token",
                data={
                    'grant_type': 'client_credentials',
                    'scope': 'all-apis',
                    'client_id': client_id,
                    'client_secret': client_secret,
                },
                timeout=30,
            )
            if resp.ok:
                token = resp.json().get('access_token', '')
                _token_cache['token'] = token
                _token_cache['expires_at'] = now + 3000  # cache 50 min
            else:
                print(f"[AUTH] M2M token exchange failed: {resp.status_code} {resp.text[:200]}")
        else:
            print(f"[AUTH] No credentials available")
    return host, token

@app.route('/api/sql/query', methods=['POST'])
def execute_sql():
    """Execute SQL queries via Databricks Statement Execution API.

    Uses an explicit `warehouse_id` (read from WAREHOUSE_ID env var, populated
    by `scripts/render_app_yaml.py` from the bundle-managed sql_warehouses
    resource). This routes SQL to the bundle's own warehouse, not whichever
    warehouse the App SP happens to have access to.

    Response is wrapped in `{result: {structuredContent: {...}}}` to preserve
    the React-side contract (App/src/api/databricksSQL.js expects this shape).
    The `result.data_array` rows are ALSO transformed from Statement Execution's
    flat-array shape (`[["v1", "v2"]]`) into MCP's nested-object shape
    (`[{values: [{string_value: "v1"}, ...]}]`) so React parsers built against
    MCP still work unchanged. See in-line note in the response-handling block.
    """
    try:
        DATABRICKS_HOST, DATABRICKS_TOKEN = get_auth()
        data = request.get_json()
        sql_query = data.get('query', '')

        if not sql_query:
            return jsonify({'error': 'No SQL query provided'}), 400
        if not DATABRICKS_TOKEN:
            return jsonify({'error': 'DATABRICKS_TOKEN not set'}), 500

        warehouse_id = os.environ.get('WAREHOUSE_ID', '').strip()
        if not warehouse_id:
            return jsonify({
                'error': 'WAREHOUSE_ID env var not set — run scripts/render_app_yaml.py + redeploy'
            }), 500

        # NOTE: We deliberately do NOT do any catalog/schema substitution here.
        # The React side fetches catalog/schema from /api/config and builds queries
        # with ${catalog}.${schema} template literals — fully resolved client-side
        # before the POST. Keeping the SQL pass-through preserves a single source
        # of truth for catalog/schema (the app.yaml env vars surfaced by /api/config).

        response = requests.post(
            f"{DATABRICKS_HOST}/api/2.0/sql/statements",
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json',
            },
            json={
                'warehouse_id': warehouse_id,
                'statement': sql_query,
                'wait_timeout': '30s',
            },
            timeout=120,
        )

        if response.ok:
            stmt_resp = response.json()
            sql_state = stmt_resp.get('status', {}).get('state', 'UNKNOWN')
            is_error = sql_state not in ('SUCCEEDED', 'PENDING', 'RUNNING')
            print(f"[SQL] query='{sql_query[:80]}' state={sql_state} warehouse={warehouse_id}")
            # Transform Statement Execution API row shape into MCP-compatible row shape
            # so React parsers in App/src/api/databricksSQL.js (built when /api/sql/query
            # routed through MCP) keep working unchanged.
            #
            # Statement Execution returns: result.data_array = [["1000"], ["2000"]]
            # MCP returned:                result.data_array = [{values: [{string_value: "1000"}]}, ...]
            # React expects MCP shape (firstRow.values[i].string_value).
            #
            # Required because the MCP → Statement Execution refactor changed
            # the server response shape, but the React client still expects
            # the MCP shape.
            result_block = stmt_resp.get('result') or {}
            if 'data_array' in result_block and result_block['data_array']:
                # Only transform if it's the Statement Execution flat-row format
                first = result_block['data_array'][0] if result_block['data_array'] else None
                if isinstance(first, list):
                    result_block['data_array'] = [
                        {'values': [{'string_value': str(cell) if cell is not None else ''}
                                    for cell in row]}
                        for row in result_block['data_array']
                    ]
            return jsonify({
                'result': {
                    'isError': is_error,
                    'structuredContent': stmt_resp,
                }
            }), 200
        else:
            print(f"[SQL] HTTP error {response.status_code}: {response.text[:300]}")
            return jsonify({
                'error': f'Statement Execution API error: {response.status_code}',
                'details': response.text,
            }), response.status_code

    except Exception as e:
        import traceback
        print(f"[SQL] Exception: {e}\n{traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/genie/query', methods=['POST'])
def query_genie():
    """Query CGM Genie room for natural language queries."""
    import time
    DATABRICKS_HOST, DATABRICKS_TOKEN = get_auth()
    print(f"[GENIE] Received request")
    try:
        data = request.get_json()
        print(f"[GENIE] Request data: {data}")
        
        question = data.get('question', '')
        conversation_id = data.get('conversation_id', None)
        
        if not question:
            print(f"[GENIE] No question provided")
            return jsonify({'error': 'No question provided'}), 400
        
        if not DATABRICKS_TOKEN:
            print(f"[GENIE] DATABRICKS_TOKEN not set")
            return jsonify({'error': 'DATABRICKS_TOKEN not set'}), 500
        
        if not GENIE_SPACE_ID:
            return jsonify({'error': 'GENIE_SPACE_ID environment variable not set'}), 500
        space_id = GENIE_SPACE_ID
        
        # Start or continue conversation
        if conversation_id:
            # Continue existing conversation
            genie_url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages"
            print(f"[GENIE] Continuing conversation: {conversation_id}")
        else:
            # Start new conversation
            genie_url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces/{space_id}/start-conversation"
            print(f"[GENIE] Starting new conversation")
        
        payload = {
            'content': question
        }
        
        print(f"[GENIE] Calling: {genie_url}")
        print(f"[GENIE] Payload: {payload}")
        
        # Submit the question
        response = requests.post(
            genie_url,
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=120
        )
        
        print(f"[GENIE] Initial response status: {response.status_code}")
        
        if not response.ok:
            print(f"[GENIE] Error response: {response.text}")
            return jsonify({
                'error': f'Genie API error: {response.status_code}',
                'details': response.text
            }), response.status_code
        
        result = response.json()
        new_conversation_id = result.get('conversation_id')
        message_id = result.get('message_id')
        
        print(f"[GENIE] Message submitted. Conversation: {new_conversation_id}, Message: {message_id}")
        
        # Poll for the completed response
        max_attempts = 60  # 60 seconds max
        poll_interval = 1  # 1 second between polls
        
        for attempt in range(max_attempts):
            time.sleep(poll_interval)
            
            # Get the message status
            message_url = f"{DATABRICKS_HOST}/api/2.0/genie/spaces/{space_id}/conversations/{new_conversation_id}/messages/{message_id}"
            
            print(f"[GENIE] Polling attempt {attempt + 1}/{max_attempts}")
            
            message_response = requests.get(
                message_url,
                headers={
                    'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                    'Content-Type': 'application/json'
                },
                timeout=30
            )
            
            if message_response.ok:
                message_data = message_response.json()
                status = message_data.get('status', 'UNKNOWN')
                
                print(f"[GENIE] Status: {status}")
                
                if status == 'COMPLETED':
                    print(f"[GENIE] Query completed successfully!")
                    
                    # Fetch the actual query results if available
                    if message_data.get('attachments'):
                        for attachment in message_data.get('attachments', []):
                            if 'query' in attachment:
                                statement_id = attachment['query'].get('statement_id')
                                if statement_id:
                                    print(f"[GENIE] Fetching query results for statement: {statement_id}")
                                    
                                    # Get the query results
                                    results_url = f"{DATABRICKS_HOST}/api/2.0/sql/statements/{statement_id}"
                                    results_response = requests.get(
                                        results_url,
                                        headers={
                                            'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                                            'Content-Type': 'application/json'
                                        },
                                        timeout=30
                                    )
                                    
                                    if results_response.ok:
                                        results_data = results_response.json()
                                        print(f"[GENIE] Got query results!")
                                        # Add the full query results to the attachment
                                        attachment['query']['statement_response'] = results_data
                    
                    return jsonify(message_data), 200
                elif status == 'FAILED':
                    print(f"[GENIE] Query failed")
                    return jsonify({
                        'error': 'Genie query failed',
                        'details': message_data
                    }), 500
                # Continue polling if status is SUBMITTED, EXECUTING, etc.
            else:
                print(f"[GENIE] Error polling message: {message_response.status_code}")
        
        # Timeout
        print(f"[GENIE] Timeout waiting for response")
        return jsonify({
            'error': 'Query timeout',
            'details': 'The query is taking longer than expected. Please try again.',
            'conversation_id': new_conversation_id,
            'message_id': message_id
        }), 504
            
    except Exception as e:
        print(f"[GENIE] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/agent/query', methods=['POST'])
def query_agent():
    """
    Proxy endpoint for querying the Databricks multi-agent supervisor.
    This avoids CORS issues when running locally.
    """
    try:
        DATABRICKS_HOST, DATABRICKS_TOKEN = get_auth()
        # Get request data from frontend
        data = request.get_json()
        messages = data.get('messages', [])
        conversation_id = data.get('conversation_id')
        
        print(f"[AGENT] Received query with {len(messages)} messages")
        
        if not DATABRICKS_TOKEN:
            return jsonify({
                'error': 'DATABRICKS_TOKEN environment variable not set'
            }), 500

        if not ENDPOINT_NAME:
            return jsonify({
                'error': 'ENDPOINT_NAME environment variable not set'
            }), 500

        # Construct the Databricks endpoint URL
        endpoint_url = f"{DATABRICKS_HOST}/serving-endpoints/{ENDPOINT_NAME}/invocations"
        
        # Prepare the payload to match Databricks playground format
        # Based on: https://github.com/databricks/app-templates
        payload = {
            'input': messages,
            'context': {
                'conversation_id': conversation_id or 'dashboard-session',
                'user_id': 'dashboard_user'
            },
            'databricks_options': {
                'return_trace': False
            },
            'stream': False  # We'll handle non-streaming for now
        }
        
        print(f"[AGENT] Calling endpoint: {endpoint_url}")
        
        # Make request to Databricks
        # Increased timeout to 10 minutes (600 seconds) for complex agent queries
        response = requests.post(
            endpoint_url,
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=600
        )
        
        print(f"[AGENT] Response status: {response.status_code}")
        print(f"[AGENT] Response headers: {response.headers}")
        print(f"[AGENT] Response content-type: {response.headers.get('content-type', 'unknown')}")
        
        # Return the response from Databricks
        if response.ok:
            # Check if response has content
            if not response.text:
                print(f"[AGENT] Error: Empty response body")
                return jsonify({
                    'error': 'Empty response from Databricks endpoint',
                    'details': 'The endpoint returned a 200 status but no content'
                }), 500
            
            # Try to parse JSON
            try:
                response_data = response.json()
                print(f"[AGENT] Response data keys: {response_data.keys() if isinstance(response_data, dict) else type(response_data)}")
            except Exception as json_error:
                print(f"[AGENT] JSON parse error: {str(json_error)}")
                print(f"[AGENT] Response text (first 500 chars): {response.text[:500]}")
                return jsonify({
                    'error': 'Invalid JSON response from Databricks endpoint',
                    'details': f'Could not parse response: {str(json_error)}',
                    'response_preview': response.text[:200]
                }), 500
            
            # Extract the final answer from the MAS response.
            # The output array contains intermediate steps (planning, tool calls)
            # followed by the final synthesized message. We want the LAST message-type
            # item, which is the agent's final answer — not the first "I'll query..."
            if 'output' in response_data and len(response_data['output']) > 0:
                outputs = response_data['output']
                print(f"[AGENT] output items: {len(outputs)}, types: {[o.get('type') for o in outputs]}")

                # Find the last item that is a message with output_text content
                text_content = None
                for item in reversed(outputs):
                    if item.get('type') == 'message':
                        for c in item.get('content', []):
                            if c.get('type') == 'output_text' and c.get('text', '').strip():
                                text_content = c['text']
                                break
                    if text_content:
                        break

                # Fallback: last item regardless of type
                if not text_content:
                    last = outputs[-1]
                    content = last.get('content', [])
                    if content:
                        text_content = content[-1].get('text', '') or content[0].get('text', '')

                if text_content:
                    print(f"[AGENT] Final response extracted (length: {len(text_content)})")
                    return jsonify({
                        'response': text_content,
                        'raw': response_data
                    }), 200
            
            # Fallback: return the raw response if format is different
            print(f"[AGENT] Returning raw response (unexpected format)")
            return jsonify(response_data), 200
        else:
            error_text = response.text
            print(f"[AGENT] Error status: {response.status_code}")
            print(f"[AGENT] Error response: {error_text[:500]}")
            return jsonify({
                'error': f'Databricks API error: {response.status_code}',
                'details': error_text
            }), response.status_code
            
    except Exception as e:
        print(f"[AGENT] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'error': str(e)
        }), 500

_baseline_provenance_cache = {'value': None, 'fetched_at': 0, 'ttl': 60}  # 60-second TTL

def _get_baseline_provenance():
    """Query the `baseline_provenance` table (written by validate_baseline_source.py
    at the head of every pipeline run) so /api/config can return mode-accurate data.
    60s TTL cache — fresh enough for runtime tracking, cheap enough to not hammer DBSQL.
    Graceful fallback to 'from_source' (the bundle var default) if the table
    doesn't exist yet (first deploy before any pipeline run)."""
    now = _time.time()
    if _baseline_provenance_cache['value'] and now < _baseline_provenance_cache['fetched_at'] + _baseline_provenance_cache['ttl']:
        return _baseline_provenance_cache['value']
    DATABRICKS_HOST, DATABRICKS_TOKEN = get_auth()
    if not DATABRICKS_TOKEN:
        return {'baseline_source': 'from_source', 'source_detail': '(provenance unknown — auth unavailable)'}
    try:
        resp = requests.post(
            f"{DATABRICKS_HOST}/api/2.0/mcp/sql",
            headers={'Authorization': f'Bearer {DATABRICKS_TOKEN}', 'Content-Type': 'application/json'},
            json={
                'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
                'params': {'name': 'execute_sql_read_only', 'arguments': {
                    'query': f"SELECT baseline_source, source_detail FROM {CATALOG_NAME}.{SCHEMA_NAME}.baseline_provenance"
                }},
            },
            timeout=10,
        )
        if resp.ok:
            data = resp.json().get('result', {}).get('structuredContent', {}).get('result', {}).get('data_array', [])
            if data and data[0].get('values') and len(data[0]['values']) >= 2:
                value = {
                    'baseline_source': data[0]['values'][0].get('string_value', 'from_source'),
                    'source_detail':   data[0]['values'][1].get('string_value', ''),
                }
                _baseline_provenance_cache['value'] = value
                _baseline_provenance_cache['fetched_at'] = now
                return value
    except Exception as _e:
        print(f"[PROVENANCE] query failed, falling back to default: {_e}")
    fallback = {'baseline_source': 'from_source', 'source_detail': '(provenance table not yet written by pipeline)'}
    _baseline_provenance_cache['value'] = fallback
    _baseline_provenance_cache['fetched_at'] = now
    return fallback

@app.route('/api/config')
def get_config():
    """Expose non-secret config to the frontend. Includes baseline_source provenance
    queried from the data layer (not env), so prose on the Metrics Explained page
    accurately reflects what was last ingested by the pipeline."""
    provenance = _get_baseline_provenance()
    return jsonify({
        'catalog': CATALOG_NAME,
        'schema': SCHEMA_NAME,
        'genie_space_id': GENIE_SPACE_ID,
        'baseline_source': provenance['baseline_source'],
        'baseline_source_detail': provenance['source_detail'],
        # workspace_host lets the React UI build runtime links into the
        # deploying workspace (e.g. the Jobs UI from MetricsExplained) without
        # hardcoding a specific tenant in JSX or the committed static bundle.
        'workspace_host': os.getenv('DATABRICKS_HOST', ''),
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'base_dir': BASE_DIR,
        'dist_dir': DIST_DIR,
        'dist_exists': os.path.exists(DIST_DIR),
        'dist_contents': os.listdir(DIST_DIR) if os.path.exists(DIST_DIR) else []
    })

@app.route('/api/genie/test', methods=['GET', 'POST'])
def test_genie():
    """Test endpoint to verify Genie routing works"""
    print(f"[GENIE TEST] Endpoint hit! Method: {request.method}")
    return jsonify({
        'status': 'ok',
        'message': 'Genie API endpoint is reachable',
        'method': request.method
    })

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve asset files (JS, CSS, images)"""
    assets_dir = os.path.join(DIST_DIR, 'assets')
    print(f"[DEBUG] Serving asset: {filename} from {assets_dir}")
    return send_from_directory(assets_dir, filename)

@app.route('/uc-assets/<path:filename>')
def serve_uc_asset(filename):
    """Serve PNG/JPG assets directly from UC Volume at runtime.

    Path is interpreted relative to /Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/.
    Eliminates the need to `fs cp` notebook-generated PNGs into the repo before
    vite build — the App fetches them live from UC Volume. Pipeline reruns
    overwrite the UC Volume file; this route serves the latest with no-cache.

    Example: <img src="/uc-assets/incident_inference_assets/distribution_comparison_4panel.png">
    Resolves to: /Volumes/${CATALOG_NAME}/${SCHEMA_NAME}/pipeline_data/incident_inference_assets/distribution_comparison_4panel.png
    """
    host, token = get_auth()
    if not token:
        return jsonify({'error': 'DATABRICKS_TOKEN not available'}), 500
    full_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/{filename}"
    url = f"{host}/api/2.0/fs/files{full_path}"
    print(f"[UC-ASSET] Fetching {full_path}")
    resp = requests.get(url, headers={'Authorization': f'Bearer {token}'}, timeout=30)
    if resp.status_code != 200:
        print(f"[UC-ASSET] Failed: {resp.status_code} {resp.text[:200]}")
        return jsonify({'error': f'UC asset not found: {full_path}', 'status': resp.status_code}), resp.status_code
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    mime = {
        'png':  'image/png',
        'jpg':  'image/jpeg',
        'jpeg': 'image/jpeg',
        'svg':  'image/svg+xml',
        'webp': 'image/webp',
    }.get(ext, 'application/octet-stream')
    return resp.content, 200, {'Content-Type': mime, 'Cache-Control': 'no-cache'}

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """Serve the SPA - index.html for all routes except assets and API"""
    # Skip API routes - they should be handled by their specific handlers
    if path and path.startswith('api/'):
        print(f"[DEBUG] API route hit catch-all (shouldn't happen): {path}")
        return jsonify({'error': 'API endpoint not found'}), 404
    
    # If it's a file that exists, serve it
    if path:
        file_path = os.path.join(DIST_DIR, path)
        if os.path.isfile(file_path):
            print(f"[DEBUG] Serving file: {path}")
            return send_from_directory(DIST_DIR, path)
    
    # Otherwise serve index.html for SPA routing
    index_path = os.path.join(DIST_DIR, 'index.html')
    print(f"[DEBUG] Serving index.html for path: {path}")
    return send_from_directory(DIST_DIR, 'index.html')

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8080))
    print(f"[STARTUP] Starting Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
