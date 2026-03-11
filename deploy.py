#!/usr/bin/env python3
"""
Glucosphere End-to-End Deployment Pipeline
==========================================
Deploys everything to fevm-ws-ward-pixels and prints the live app URL.

Usage:
    python deploy.py

Requires: databricks CLI authenticated with profile 'fe-vm-ward-pixels'
          npm installed (for React frontend build)
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# ── Config ────────────────────────────────────────────────────────────────────

PROFILE      = "fe-vm-ward-pixels"
HOST         = "https://fevm-ws-ward-pixels.cloud.databricks.com"
CATALOG      = "ws_ward_pixels_catalog"
SCHEMA       = "glucosphere"
APP_NAME     = "glucosphere-dashboard"
MAS_ENDPOINT = "glucosphere-mas-endpoint"
GENIE_TITLE  = "Glucosphere CGM Intelligence"
REPO_ROOT    = os.path.dirname(os.path.abspath(__file__))
APP_DIR      = os.path.join(REPO_ROOT, "App")
APP_SRC_DIR  = os.path.join(APP_DIR, "databricks")
NB_MAS       = "Data_DataGen_ModelForecast/07_Create_MAS_Endpoint.py"

# ── Helpers ───────────────────────────────────────────────────────────────────

class Step:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        print(f"\n{'═'*64}")
        print(f"  {self.name}")
        print(f"{'═'*64}")
        return self
    def __exit__(self, *_):
        pass

def run(args, check=True, capture=False, cwd=None):
    """Run a subprocess; stream output unless capture=True."""
    if isinstance(args, str):
        args = args.split()
    result = subprocess.run(
        args,
        capture_output=capture,
        text=True,
        cwd=cwd or REPO_ROOT,
    )
    if check and result.returncode != 0:
        stderr = result.stderr[:500] if capture else ""
        print(f"[FATAL] Command failed: {' '.join(args)}\n{stderr}", file=sys.stderr)
        sys.exit(1)
    return result

def db(*args, json_out=False):
    """Run a databricks CLI command against PROFILE."""
    cmd = ["databricks", "--profile", PROFILE] + list(args)
    if json_out:
        cmd += ["-o", "json"]
    result = run(cmd, capture=json_out)
    if json_out:
        return json.loads(result.stdout)
    return result

def api_get(path):
    token = get_token()
    req = urllib.request.Request(
        f"{HOST}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def api_post(path, payload):
    token = get_token()
    data  = json.dumps(payload).encode()
    req   = urllib.request.Request(
        f"{HOST}{path}",
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())

_token_cache = None
def get_token():
    global _token_cache
    if _token_cache:
        return _token_cache
    result = run(["databricks", "--profile", PROFILE, "auth", "token"], capture=True)
    raw = result.stdout.strip()
    try:
        # Output may be JSON: {"access_token": "...", ...}
        _token_cache = json.loads(raw).get("access_token", raw)
    except (json.JSONDecodeError, AttributeError):
        _token_cache = raw
    return _token_cache

def poll_job_run(run_id, label):
    """Poll a job run until terminal; print task progress."""
    print(f"  Polling run {run_id} ...")
    last_states = {}
    while True:
        data   = api_get(f"/api/2.1/jobs/runs/get?run_id={run_id}&include_history=false")
        state  = data.get("state", {})
        lc     = state.get("life_cycle_state", "")
        tasks  = data.get("tasks", [])
        for t in tasks:
            tk = t.get("task_key", "")
            ts = t.get("state", {})
            tstate = ts.get("result_state") or ts.get("life_cycle_state", "?")
            if last_states.get(tk) != tstate:
                print(f"    {tk}: {tstate}")
                last_states[tk] = tstate
        if lc in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
            result_state = state.get("result_state", "UNKNOWN")
            msg          = state.get("state_message", "")
            if result_state == "SUCCESS":
                print(f"  ✓ {label} complete")
                return
            else:
                print(f"  ✗ {label} FAILED: {result_state} — {msg}", file=sys.stderr)
                sys.exit(1)
        time.sleep(20)

def poll_pipeline_update(pipeline_id, update_id, label):
    """Poll a DLT pipeline update until terminal."""
    print(f"  Polling pipeline update {update_id} ...")
    while True:
        data   = api_get(f"/api/2.0/pipelines/{pipeline_id}/updates/{update_id}")
        update = data.get("update", {})
        status = update.get("state", "?")
        print(f"    {label}: {status}")
        if status in ("COMPLETED",):
            print(f"  ✓ {label} complete")
            return
        if status in ("FAILED", "CANCELED", "STOPPING"):
            cause = update.get("cause", "unknown")
            print(f"  ✗ {label} FAILED: {status} — {cause}", file=sys.stderr)
            sys.exit(1)
        time.sleep(30)

def get_pipeline_id(name):
    data = api_get("/api/2.0/pipelines?max_results=50")
    for p in data.get("statuses", []):
        if p.get("name") == name:
            return p.get("pipeline_id")
    return None

def get_job_id(name):
    data = api_get("/api/2.1/jobs/list?limit=50")
    for j in data.get("jobs", []):
        if j.get("settings", {}).get("name") == name:
            return j.get("job_id")
    return None

# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_preflight():
    with Step("Pre-flight checks"):
        print("  Checking databricks auth ...")
        result = run(["databricks", "--profile", PROFILE, "auth", "env"], capture=True, check=False)
        if result.returncode != 0:
            print(f"  Auth failed. Run: databricks auth login --profile {PROFILE}", file=sys.stderr)
            sys.exit(1)
        print("  ✓ Auth OK")

        print("  Ensuring schema + volume exist ...")
        try:
            db("schemas", "create", SCHEMA, CATALOG, check=False)
        except Exception:
            pass
        try:
            db("volumes", "create", CATALOG, SCHEMA, "data", "MANAGED", check=False)
        except Exception:
            pass
        print("  ✓ Schema/volume ready")


def step_bundle_deploy():
    with Step("Deploy Databricks bundle"):
        run(["databricks", "--profile", PROFILE, "bundle", "deploy"], cwd=REPO_ROOT)
        print("  ✓ Bundle deployed")


def step_run_setup_job():
    with Step("Run setup job (generate baseline → train models)"):
        job_id = get_job_id(f"glucosphere-setup-dev")
        if not job_id:
            print("  ✗ Could not find glucosphere-setup-dev job", file=sys.stderr)
            sys.exit(1)
        print(f"  Job ID: {job_id}")
        data   = api_post("/api/2.1/jobs/run-now", {"job_id": job_id})
        run_id = data["run_id"]
        print(f"  Run URL: {HOST}/?#job/{job_id}/run/{run_id}")
        poll_job_run(run_id, "Setup job")


def step_run_dlt():
    with Step("Run DLT pipeline (silver → gold tables)"):
        pipeline_name = f"glucosphere-cgm-silver-gold-dev"
        pipeline_id   = get_pipeline_id(pipeline_name)
        if not pipeline_id:
            print(f"  ✗ Could not find pipeline: {pipeline_name}", file=sys.stderr)
            sys.exit(1)
        print(f"  Pipeline ID: {pipeline_id}")
        data      = api_post(f"/api/2.0/pipelines/{pipeline_id}/updates", {"full_refresh": True})
        update_id = data["update_id"]
        print(f"  Update ID: {update_id}")
        poll_pipeline_update(pipeline_id, update_id, pipeline_name)


def step_create_genie_room():
    with Step("Create Genie room"):
        # Check if a room with this title already exists
        try:
            existing = api_get("/api/2.0/genie/spaces?page_size=50")
            for space in existing.get("spaces", []):
                if space.get("title") == GENIE_TITLE:
                    space_id = space["id"]
                    print(f"  ✓ Genie room already exists: {space_id}")
                    return space_id
        except Exception:
            pass

        payload = {
            "title": GENIE_TITLE,
            "description": "Natural language CGM analytics — glucose trends, device health, fleet insights.",
            "tables": [{
                "catalog": CATALOG,
                "schema":  SCHEMA,
                "table":   "gold_patient_device_readings",
                "description": "Gold CGM readings with patient demographics, device metadata, glucose values, incident flags, and XGBoost forecasts.",
            }],
            "instructions": (
                "You are GlucoScope, a clinical intelligence assistant for continuous glucose monitoring (CGM) data. "
                "Answer questions about patient glucose trends, device calibration incidents, "
                "fleet-level statistics, and XGBoost forecast accuracy. "
                "Key thresholds: hypoglycemia <70 mg/dL, normal 70-180 mg/dL, hyperglycemia >180 mg/dL. "
                "Always provide specific numbers."
            ),
        }
        resp     = api_post("/api/2.0/genie/spaces", payload)
        space_id = resp.get("id") or resp.get("space_id")
        if not space_id:
            print(f"  Unexpected Genie response: {resp}", file=sys.stderr)
            sys.exit(1)
        print(f"  ✓ Genie room created: {space_id}")
        print(f"  URL: {HOST}/genie/rooms/{space_id}")
        return space_id


def step_create_mas_endpoint():
    with Step("Create MAS endpoint (register agent + deploy serving endpoint)"):
        # Submit notebook 07 as a one-time job run
        nb_workspace_path = (
            f"/Workspace/Users/justin.ward@databricks.com"
            f"/.bundle/glucosphere/dev/files/{NB_MAS.replace('.py', '')}"
        )
        payload = {
            "run_name": "glucosphere-create-mas",
            "tasks": [{
                "task_key":       "create_mas",
                "environment_key": "default",
                "notebook_task": {
                    "notebook_path": nb_workspace_path,
                    "base_parameters": {
                        "CATALOG_NAME":   CATALOG,
                        "SCHEMA_NAME":    SCHEMA,
                        "ENDPOINT_NAME":  MAS_ENDPOINT,
                        "MODEL_NAME":     "glucosphere_mas_agent",
                        "LLM_ENDPOINT":   "databricks-claude-sonnet-4-6",
                    },
                },
            }],
            "environments": [{"environment_key": "default", "spec": {"client": "1"}}],
        }
        data   = api_post("/api/2.1/jobs/runs/submit", payload)
        run_id = data["run_id"]
        print(f"  Submitted notebook run: {run_id}")
        poll_job_run(run_id, "MAS endpoint creation")
        print(f"  ✓ MAS endpoint ready: {MAS_ENDPOINT}")
        return MAS_ENDPOINT


def step_build_frontend():
    with Step("Build React frontend"):
        if not os.path.exists(os.path.join(APP_DIR, "node_modules")):
            print("  npm install ...")
            run(["npm", "install"], cwd=APP_DIR)
        print("  npm run build ...")
        run(["npm", "run", "build"], cwd=APP_DIR)
        dist_dir = os.path.join(APP_DIR, "dist")
        if not os.path.exists(dist_dir):
            print("  ✗ Build failed — dist/ not found", file=sys.stderr)
            sys.exit(1)
        # Copy built assets to App/databricks/dist
        import shutil
        dest_dist = os.path.join(APP_SRC_DIR, "dist")
        if os.path.exists(dest_dist):
            shutil.rmtree(dest_dist)
        shutil.copytree(dist_dir, dest_dist)
        print(f"  ✓ Frontend built and copied to App/databricks/dist/")


def step_wire_and_deploy(genie_space_id, endpoint_name):
    with Step("Update app.yaml + final deploy"):
        app_yaml = os.path.join(APP_SRC_DIR, "app.yaml")
        with open(app_yaml) as f:
            content = f.read()

        # Replace empty values with real ones
        import re
        content = re.sub(
            r'(- name: ENDPOINT_NAME\s+value: ")[^"]*(")',
            f'\\g<1>{endpoint_name}\\2',
            content,
        )
        content = re.sub(
            r'(- name: GENIE_SPACE_ID\s+value: ")[^"]*(")',
            f'\\g<1>{genie_space_id}\\2',
            content,
        )
        with open(app_yaml, "w") as f:
            f.write(content)
        print(f"  ✓ app.yaml updated")
        print(f"    ENDPOINT_NAME  = {endpoint_name}")
        print(f"    GENIE_SPACE_ID = {genie_space_id}")

        # Redeploy bundle (pushes updated app.yaml to workspace)
        run(["databricks", "--profile", PROFILE, "bundle", "deploy"], cwd=REPO_ROOT)
        print("  ✓ Bundle redeployed")

        # Deploy the app
        print("  Deploying Databricks App ...")
        run([
            "databricks", "--profile", PROFILE,
            "apps", "deploy", APP_NAME,
            "--source-code-path", APP_SRC_DIR,
        ], cwd=REPO_ROOT)

        # Start / restart the app
        print("  Starting app ...")
        start_result = run(
            ["databricks", "--profile", PROFILE, "apps", "start", APP_NAME],
            capture=True, check=False,
        )
        if start_result.returncode != 0 and "already running" not in start_result.stderr.lower():
            run(["databricks", "--profile", PROFILE, "apps", "restart", APP_NAME], check=False)

        # Get the app URL
        time.sleep(5)
        app_data = db("apps", "get", APP_NAME, json_out=True)
        url = app_data.get("url") or app_data.get("app_url") or "(see Databricks Apps UI)"
        return url


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("\nGlucosphere Deployment Pipeline")
    print(f"Target: {HOST}")
    print(f"Catalog: {CATALOG}.{SCHEMA}\n")

    step_preflight()
    step_bundle_deploy()
    step_run_setup_job()
    step_run_dlt()
    genie_space_id = step_create_genie_room()
    endpoint_name  = step_create_mas_endpoint()
    step_build_frontend()
    app_url        = step_wire_and_deploy(genie_space_id, endpoint_name)

    print(f"\n{'═'*64}")
    print(f"  DEPLOYMENT COMPLETE")
    print(f"{'═'*64}")
    print(f"  App URL:       {app_url}")
    print(f"  Genie Room:    {HOST}/genie/rooms/{genie_space_id}")
    print(f"  MAS Endpoint:  {MAS_ENDPOINT}")
    print(f"{'═'*64}\n")


if __name__ == "__main__":
    main()
