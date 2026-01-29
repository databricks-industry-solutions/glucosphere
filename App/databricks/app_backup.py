from flask import Flask, send_from_directory, send_file, request, jsonify
import os
import requests

# Determine the correct path to dist folder
# When deployed on Databricks Apps, dist is in the same directory as app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist')

app = Flask(__name__, static_folder=DIST_DIR, static_url_path='')

# Databricks configuration
DATABRICKS_HOST = os.getenv('DATABRICKS_HOST', 'https://fe-vm-industry-solutions-buildathon.cloud.databricks.com')
DATABRICKS_TOKEN = os.getenv('DATABRICKS_TOKEN', '')
ENDPOINT_NAME = 'mas-5a566f25-endpoint'

@app.route('/api/sql/list-tools', methods=['GET'])
def list_sql_tools():
    """
    List available tools in the DBSQL MCP server.
    """
    try:
        if not DATABRICKS_TOKEN:
            return jsonify({'error': 'DATABRICKS_TOKEN environment variable not set'}), 500
        
        mcp_sql_url = f"{DATABRICKS_HOST}/api/2.0/mcp/sql"
        
        # JSON-RPC request to list tools
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/list'
        }
        
        response = requests.post(
            mcp_sql_url,
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=30
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

@app.route('/api/sql/query', methods=['POST'])
def execute_sql():
    """
    Execute SQL queries via Databricks DBSQL MCP server.
    This uses the managed MCP server for SQL execution.
    """
    try:
        # Get SQL query from request
        data = request.get_json()
        sql_query = data.get('query', '')
        
        if not sql_query:
            return jsonify({'error': 'No SQL query provided'}), 400
        
        if not DATABRICKS_TOKEN:
            return jsonify({'error': 'DATABRICKS_TOKEN environment variable not set'}), 500
        
        # Construct the DBSQL MCP server URL
        # Based on: https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp
        mcp_sql_url = f"{DATABRICKS_HOST}/api/2.0/mcp/sql"
        
        # Prepare the payload for DBSQL MCP server using JSON-RPC format
        # Use execute_sql_read_only for SELECT queries
        payload = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'tools/call',
            'params': {
                'name': 'execute_sql_read_only',
                'arguments': {
                    'query': sql_query
                }
            }
        }
        
        # Make request to Databricks DBSQL MCP server
        response = requests.post(
            mcp_sql_url,
            headers={
                'Authorization': f'Bearer {DATABRICKS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=120
        )
        
        # Return the response
        if response.ok:
            response_data = response.json()
            return jsonify(response_data), 200
        else:
            return jsonify({
                'error': f'DBSQL MCP error: {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/agent/query', methods=['POST'])
def query_agent():
    """
    Proxy endpoint for querying the Databricks multi-agent supervisor.
    This avoids CORS issues when running locally.
    """
    try:
        # Get request data from frontend
        data = request.get_json()
        messages = data.get('messages', [])
        conversation_id = data.get('conversation_id')
        
        if not DATABRICKS_TOKEN:
            return jsonify({
                'error': 'DATABRICKS_TOKEN environment variable not set'
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
        
        # Return the response from Databricks
        if response.ok:
            response_data = response.json()
            
            # Extract the text content from the Databricks response format
            # Response format: {"output": [{"content": [{"text": "...", "type": "output_text"}]}]}
            if 'output' in response_data and len(response_data['output']) > 0:
                output_content = response_data['output'][0].get('content', [])
                if output_content and len(output_content) > 0:
                    # Extract text from the first content item
                    text_content = output_content[0].get('text', '')
                    
                    # Return in a format the frontend expects
                    return jsonify({
                        'response': text_content,
                        'raw': response_data  # Include raw response for debugging
                    }), 200
            
            # Fallback: return the raw response if format is different
            return jsonify(response_data), 200
        else:
            return jsonify({
                'error': f'Databricks API error: {response.status_code}',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/health')
def health():
    """Health check endpoint for debugging"""
    dist_exists = os.path.exists(DIST_DIR)
    index_exists = os.path.exists(os.path.join(DIST_DIR, 'index.html'))
    dist_contents = os.listdir(DIST_DIR) if dist_exists else []
    
    return jsonify({
        'status': 'healthy',
        'base_dir': BASE_DIR,
        'dist_dir': DIST_DIR,
        'dist_exists': dist_exists,
        'index_exists': index_exists,
        'dist_contents': dist_contents
    })

@app.route('/')
def index():
    index_path = os.path.join(DIST_DIR, 'index.html')
    print(f"[DEBUG] Accessing index at: {index_path}")
    print(f"[DEBUG] Dist dir exists: {os.path.exists(DIST_DIR)}")
    print(f"[DEBUG] Index exists: {os.path.exists(index_path)}")
    if os.path.exists(DIST_DIR):
        print(f"[DEBUG] Dist contents: {os.listdir(DIST_DIR)}")
    
    if os.path.exists(index_path):
        return send_file(index_path)
    else:
        return f"Error: index.html not found at {index_path}<br>BASE_DIR: {BASE_DIR}<br>DIST_DIR: {DIST_DIR}<br>Dist exists: {os.path.exists(DIST_DIR)}", 404

@app.route('/<path:path>')
def serve(path):
    print(f"[DEBUG] Requested path: {path}")
    
    # Try to serve static files (JS, CSS, etc.)
    file_path = os.path.join(DIST_DIR, path)
    print(f"[DEBUG] Looking for file at: {file_path}")
    print(f"[DEBUG] File exists: {os.path.exists(file_path)}")
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        print(f"[DEBUG] Serving file: {path}")
        return send_from_directory(DIST_DIR, path)
    
    # For React Router - serve index.html for all other routes
    print(f"[DEBUG] File not found, serving index.html for React Router")
    index_path = os.path.join(DIST_DIR, 'index.html')
    if os.path.exists(index_path):
        return send_file(index_path)
    else:
        return f"Error: index.html not found at {index_path}", 404

if __name__ == '__main__':
    # Databricks Apps expects port 8080
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
