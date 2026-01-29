from flask import Flask, send_from_directory, request, jsonify
import os
import requests

app = Flask(__name__)

# Databricks configuration
DATABRICKS_HOST = os.getenv('DATABRICKS_HOST', 'https://fe-vm-industry-solutions-buildathon.cloud.databricks.com')
DATABRICKS_TOKEN = os.getenv('DATABRICKS_TOKEN', '')
ENDPOINT_NAME = 'mas-5a566f25-endpoint'

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist')

print(f"[STARTUP] BASE_DIR: {BASE_DIR}")
print(f"[STARTUP] DIST_DIR: {DIST_DIR}")
print(f"[STARTUP] DIST_DIR exists: {os.path.exists(DIST_DIR)}")
if os.path.exists(DIST_DIR):
    print(f"[STARTUP] DIST contents: {os.listdir(DIST_DIR)}")

@app.route('/api/sql/query', methods=['POST'])
def execute_sql():
    """Execute SQL queries via Databricks DBSQL MCP server."""
    try:
        data = request.get_json()
        sql_query = data.get('query', '')
        
        if not sql_query:
            return jsonify({'error': 'No SQL query provided'}), 400
        
        if not DATABRICKS_TOKEN:
            return jsonify({'error': 'DATABRICKS_TOKEN not set'}), 500
        
        mcp_sql_url = f"{DATABRICKS_HOST}/api/2.0/mcp/sql"
        
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'execute_sql_read_only',
                'arguments': {'query': sql_query}
            }
        }
        
        response = requests.post(
            mcp_sql_url,
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=120
        )
        
        if response.ok:
            return jsonify(response.json()), 200
        else:
            return jsonify({
                'error': f'DBSQL MCP error: {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Serve asset files (JS, CSS, images)"""
    assets_dir = os.path.join(DIST_DIR, 'assets')
    print(f"[DEBUG] Serving asset: {filename} from {assets_dir}")
    return send_from_directory(assets_dir, filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    """Serve the SPA - index.html for all routes except assets and API"""
    # If it's a file that exists, serve it
    if path and not path.startswith('api/'):
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
