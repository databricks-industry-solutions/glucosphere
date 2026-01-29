# Databricks notebook source
# MAGIC %md
# MAGIC # GlucoStream Intelligence Dashboard
# MAGIC 
# MAGIC This notebook serves the React application built with Vite.

# COMMAND ----------

# MAGIC %pip install flask flask-cors

# COMMAND ----------

from flask import Flask, send_from_directory, send_file
import os
import threading

app = Flask(__name__, static_folder='/dbfs/glucostream-app/dist')

@app.route('/')
def index():
    return send_file('/dbfs/glucostream-app/dist/index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('/dbfs/glucostream-app/dist', path)

@app.route('/assets/<path:path>')
def serve_assets(path):
    return send_from_directory('/dbfs/glucostream-app/dist/assets', path)

def run_app():
    app.run(host='0.0.0.0', port=8080, debug=False)

# Start the Flask app in a background thread
thread = threading.Thread(target=run_app)
thread.daemon = True
thread.start()

displayHTML(f"""
<h2>GlucoStream Dashboard is running!</h2>
<p>Access it at: <a href="/driver-proxy/o/0/8080/" target="_blank">/driver-proxy/o/0/8080/</a></p>
<p>Keep this notebook running to maintain the app.</p>
""")

# COMMAND ----------

# Keep the notebook running
import time
while True:
    time.sleep(60)

