# Databricks notebook source
# MAGIC %md
# MAGIC # Glucosphere: Knowledge Assistant + Genie Room + Supervisor Agent
# MAGIC
# MAGIC Uses native Databricks Agent Bricks APIs:
# MAGIC - `/api/2.0/knowledge-assistants`   — WHO diabetes RAG (Databricks handles chunking/VS)
# MAGIC - `/api/2.0/data-rooms/`            — Genie room over gold_patient_device_readings
# MAGIC - `/api/2.0/multi-agent-supervisors` — MAS routing between KA and Genie
# MAGIC
# MAGIC **Prerequisites:** DLT pipeline must have completed.

# COMMAND ----------

# DBTITLE 1, Parameters
dbutils.widgets.text("CATALOG_NAME",     "",                              "Catalog (required — set by the bundle job)")
dbutils.widgets.text("SCHEMA_NAME",      "glucosphere",           "Schema")
dbutils.widgets.text("KA_NAME",          "Glucosphere_KA",            "KA Name")
dbutils.widgets.text("GENIE_NAME",       "Glucosphere_Intelligence",  "Genie Space Name")
dbutils.widgets.text("MAS_NAME",         "Glucosphere_Supervisor",    "MAS Name")
dbutils.widgets.text("BUNDLE_TARGET",    "",                              "Bundle target name (used to discover bundle-managed warehouse by deterministic name)")

CATALOG_NAME  = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME   = dbutils.widgets.get("SCHEMA_NAME")
KA_NAME       = dbutils.widgets.get("KA_NAME")
GENIE_NAME    = dbutils.widgets.get("GENIE_NAME")
MAS_NAME      = dbutils.widgets.get("MAS_NAME")
BUNDLE_TARGET = dbutils.widgets.get("BUNDLE_TARGET")

GOLD_TABLE  = f"{CATALOG_NAME}.{SCHEMA_NAME}.gold_patient_device_readings"
DOCS_VOLUME = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/who_docs"

print(f"Catalog:       {CATALOG_NAME}.{SCHEMA_NAME}")
print(f"Gold table:    {GOLD_TABLE}")
print(f"Docs volume:   {DOCS_VOLUME}")
print(f"Bundle target: {BUNDLE_TARGET or '(not set — will fall back to first non-deleted warehouse)'}")

# COMMAND ----------

# DBTITLE 1, REST API helper
import json
import time
import urllib.request
import urllib.error
import os

host  = spark.conf.get("spark.databricks.workspaceUrl", "")
if not host.startswith("https://"):
    host = f"https://{host}"
token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()

def _api(method, path, body=None, params=None):
    url = f"{host}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url, data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {path}: {e.read().decode()}") from e

# COMMAND ----------

# MAGIC %md ## Part 1: WHO Knowledge Assistant

# COMMAND ----------

# DBTITLE 1, Copy WHO PDF from bundle assets to volume
import shutil

# Ensure the 'pipeline_data' volume exists before writing to it. pipeline_data is
# the shared UC Volume used by: utils/additional_patient_info/Create *.ipynb
# (raw_patient_registry/, raw_device_telemetry_stream/),
# 05_incident_inference_bidirectional.py (incident_inference_assets/), and now
# 08 (who_docs/). One volume, three subdirectories — single grants surface, less
# UC-Volume-management overhead than maintaining a separate `data` volume just
# for the WHO PDF. IF NOT EXISTS is idempotent — safe if earlier tasks created it.
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.pipeline_data")
# dbutils.fs.mkdirs (not os.makedirs) — UC Volume FUSE returns errno 95 EOPNOTSUPP
# on Python stdlib os.makedirs (same bug fixed in 05_incident_inference_bidirectional.py).
# dbutils.fs.mkdirs is the DBR-native API that handles
# UC Volume paths correctly + is idempotent (no exist_ok arg needed).
dbutils.fs.mkdirs(DOCS_VOLUME)

WHO_PDF_PATH = f"{DOCS_VOLUME}/WHO_NCD_NCS_99.2.pdf"

if os.path.exists(WHO_PDF_PATH):
    print(f"Already in volume ({os.path.getsize(WHO_PDF_PATH) // 1024} KB): {WHO_PDF_PATH}")
else:
    notebook_ws_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
    # notebookPath() returns a workspace path (e.g. /Users/...) without the /Workspace prefix.
    # Prepend /Workspace so os.path.exists resolves via the FUSE mount.
    if not notebook_ws_path.startswith("/Workspace"):
        notebook_ws_path = "/Workspace" + notebook_ws_path
    notebook_dir     = os.path.dirname(notebook_ws_path)
    src_pdf          = f"{notebook_dir}/assets/who_docs/WHO_NCD_NCS_99.2.pdf"

    if not os.path.exists(src_pdf):
        raise FileNotFoundError(
            f"WHO PDF not found at {src_pdf}. "
            "Place the file at Data_DataGen_ModelForecast/assets/who_docs/WHO_NCD_NCS_99.2.pdf "
            "in the repo and re-deploy the bundle."
        )

    shutil.copy2(src_pdf, WHO_PDF_PATH)
    print(f"Copied to volume ({os.path.getsize(WHO_PDF_PATH) // 1024} KB): {WHO_PDF_PATH}")

# COMMAND ----------

# DBTITLE 1, Create Knowledge Assistant
# Check if it already exists
tiles = _api("GET", "/api/2.0/tiles", params={"tile_type": "KNOWLEDGE_ASSISTANT"})
existing_ka = next(
    (t for t in tiles.get("tiles", [])
     if t.get("name", "").lower() == KA_NAME.lower()),
    None,
)

if existing_ka:
    KA_TILE_ID = existing_ka["tile_id"]
    print(f"KA already exists: {KA_TILE_ID}")
else:
    print(f"Creating Knowledge Assistant: {KA_NAME}")
    resp = _api("POST", "/api/2.0/knowledge-assistants", {
        "name": KA_NAME,
        "description": "WHO diabetes definition, diagnosis and classification guidelines (1999)",
        "instructions": (
            "Answer questions about diabetes diagnosis, classification, and WHO guidelines. "
            "Always cite the source page when possible. Be precise and clinical."
        ),
        "knowledge_sources": [
            {
                "files_source": {
                    "name":  "who-diabetes-docs",
                    "type":  "files",
                    "files": {"path": DOCS_VOLUME},
                }
            }
        ],
    })
    KA_TILE_ID = resp.get("knowledge_assistant", {}).get("tile", {}).get("tile_id") or resp.get("tile_id")
    print(f"KA created: tile_id={KA_TILE_ID}")

# COMMAND ----------

# DBTITLE 1, Wait for KA endpoint to be ONLINE (blocks MAS creation otherwise)
# Previously this was a "quick check, no long wait" that broke out the loop as
# soon as the endpoint NAME was populated — even if status was still PENDING.
# That race let MAS creation race ahead and silently fail when it tried to
# reference a KA endpoint that wasn't actually ready.
# Fix: require status == ONLINE before proceeding. Bump max wait to 10 min.
print("Waiting for KA endpoint to be ONLINE...")
KA_ENDPOINT_NAME = ""
KA_STATUS = "UNKNOWN"
KA_WAIT_MAX_SEC = 600   # 10 min — KA serving endpoints commonly take 3-7 min
KA_POLL_SEC = 15
ka_wait_start = time.time()
while time.time() - ka_wait_start < KA_WAIT_MAX_SEC:
    ka_info = _api("GET", f"/api/2.0/knowledge-assistants/{KA_TILE_ID}")
    KA_STATUS = (
        ka_info.get("knowledge_assistant", {})
               .get("status", {})
               .get("endpoint_status", "UNKNOWN")
    )
    # NOTE on JSON path: the API returns serving_endpoint_name at .tile.*, not
    # at .status.* — the original notebook 09 read the wrong path and got
    # empty strings (which the silent try/except then masked).
    KA_ENDPOINT_NAME = (
        ka_info.get("knowledge_assistant", {})
               .get("tile", {})
               .get("serving_endpoint_name", "")
    )
    elapsed = int(time.time() - ka_wait_start)
    print(f"  [{elapsed:>3}s] KA status: {KA_STATUS} | endpoint: {KA_ENDPOINT_NAME}")
    if KA_STATUS == "ONLINE" and KA_ENDPOINT_NAME:
        break
    if KA_STATUS in ("FAILED", "ERROR"):
        raise RuntimeError(f"KA endpoint creation failed: status={KA_STATUS}")
    time.sleep(KA_POLL_SEC)
else:
    raise RuntimeError(
        f"KA endpoint did not reach ONLINE within {KA_WAIT_MAX_SEC}s "
        f"(last status: {KA_STATUS}, endpoint: {KA_ENDPOINT_NAME}). "
        f"MAS creation depends on KA being ready; aborting."
    )
print(f"✓ KA endpoint ready: {KA_ENDPOINT_NAME}")

# COMMAND ----------

# MAGIC %md ## Part 2: Genie Room

# COMMAND ----------

# DBTITLE 1, Create Genie Room
# Warehouse selection: prefer the bundle-managed warehouse (deterministic name
# `glucosphere-warehouse-<BUNDLE_TARGET>`) when BUNDLE_TARGET is set. Falls back
# to the first non-deleted warehouse. The bundle-managed pick is important when
# multiple workspaces have shared warehouses — without it, Genie may get bound to
# an unrelated warehouse and queries may run against wrong data sources.
warehouses = _api("GET", "/api/2.0/sql/warehouses")
wh_list    = warehouses.get("warehouses", [])
if not wh_list:
    raise RuntimeError("No SQL warehouses found.")
wh = None
if BUNDLE_TARGET:
    expected_suffix = f"glucosphere-warehouse-{BUNDLE_TARGET}"
    wh = next((w for w in wh_list if w.get("name", "").endswith(expected_suffix)
               and w.get("state") not in ("DELETING", "DELETED")), None)
    if wh:
        print(f"Discovered bundle-managed warehouse by name: '{wh['name']}'")
    else:
        print(f"[WARN] no warehouse name endswith '{expected_suffix}' — falling back to first non-deleted")
if not wh:
    wh = next((w for w in wh_list if w.get("state") not in ("DELETING", "DELETED")), wh_list[0])
warehouse_id = wh["id"]
print(f"Using warehouse: {wh['name']} ({warehouse_id})")

# Check if Genie space already exists
data_rooms = _api("GET", "/api/2.0/data-rooms")
existing_room = next(
    (r for r in data_rooms.get("data_rooms", [])
     if r.get("display_name", "") == GENIE_NAME),
    None,
)

if existing_room:
    GENIE_SPACE_ID = existing_room.get("space_id") or existing_room.get("id")
    print(f"Genie space already exists: {GENIE_SPACE_ID}")
    # Rebind the reused space to the current catalog's tables + bundle-managed
    # warehouse. Verified via direct PATCH test: the Data Rooms API
    # supports PATCH /api/2.0/data-rooms/{id} with `display_name` (required),
    # `table_identifiers`, and `warehouse_id` — returns the updated space.
    # Without this rebind, the reused space stays bound to whatever tables +
    # warehouse it had at original-create time → fails for workspace/catalog
    # migrations where the underlying tables now live elsewhere.
    print(f"  → rebinding space to {GOLD_TABLE} + warehouse {warehouse_id}")
    _api("PATCH", f"/api/2.0/data-rooms/{GENIE_SPACE_ID}", {
        "display_name":      GENIE_NAME,
        "table_identifiers": [GOLD_TABLE],
        "warehouse_id":      warehouse_id,
    })
else:
    print(f"Creating Genie space: {GENIE_NAME}")
    room = _api("POST", "/api/2.0/data-rooms/", {
        "display_name":      GENIE_NAME,
        "description":       "AI-powered natural language interface for CGM glucose monitoring data",
        "warehouse_id":      warehouse_id,
        "table_identifiers": [GOLD_TABLE],
        "run_as_type":       "VIEWER",
    })
    GENIE_SPACE_ID = room.get("space_id") or room.get("id")
    print(f"Genie space created: {GENIE_SPACE_ID}")

# Add instructions to the Genie space — idempotent dedupe by title.
# Without dedupe, every setup-job re-run POSTs both instructions again, accumulating
# duplicates in /api/2.0/data-rooms/{id}/instructions. Querying by title and skipping
# already-present entries keeps the space clean across re-runs.
#
# API surface note: this uses legacy /api/2.0/data-rooms/{id}/instructions because
# modern /api/2.0/genie/spaces has no instruction-write subresource — POST/GET on
# /instructions and /example-question-sqls both return "No API found". The two
# surfaces share backing storage (legacy POSTs appear in the modern view's
# serialized_space.instructions.example_question_sqls[]), so this is forward-
# compatible. Revisit when Databricks ships an instruction-write API on /genie/spaces.

def _ensure_genie_instruction(space_id: str, title: str, content: str) -> None:
    existing = _api("GET", f"/api/2.0/data-rooms/{space_id}/instructions").get("instructions", []) or []
    match = next((i for i in existing if i.get("title") == title), None)
    if match:
        # Dedupe is by title. On a FRESH space there is no match, so the POST below
        # runs and seeds the instruction. On a RE-RUN against an existing space the
        # title is already present and we skip — BUT if the desired content has since
        # changed (e.g. a corrected column list), a silent skip would leave the old
        # text in place. Surface that drift explicitly so it can be updated (the
        # legacy /instructions surface seeds new entries; remove/update the existing
        # one in the Genie space UI to apply a content change).
        if (match.get("content") or "").strip() != content.strip():
            print(f"  → [DRIFT] instruction {title!r} exists with DIFFERENT content; "
                  f"remove/update the existing entry in the Genie space UI to apply this update")
        else:
            print(f"  → instruction {title!r} already present; skipping")
        return
    _api("POST", f"/api/2.0/data-rooms/{space_id}/instructions", {
        "title": title,
        "content": content,
        "instruction_type": "TEXT",
    })
    print(f"  → instruction {title!r} added")

_ensure_genie_instruction(GENIE_SPACE_ID, "CGM Data Context", (
    "This space contains continuous glucose monitoring (CGM) fleet data in one table, "
    "gold_patient_device_readings, with ONE ROW PER READING (~5-min cadence, "
    "~288 rows/patient/day). Key columns: patient_id, device_id, device_model, "
    "firmware_version, time (reading timestamp), glucose (mg/dL), "
    "glucose_out_of_range (1 = reading outside 70-180), region, "
    "patient_diagnosis (T1D / T2D / gestational), event_type, steps, heart_rate, "
    "basal_rate, bolus_volume_delivered, carb_input. "
    "Normal range 70-180 mg/dL; hypoglycemia <70 (very low <54); "
    "hyperglycemia >180 (very high >250). A COUNT of rows scales with fleet size and "
    "monitoring duration, NOT clinical severity."
))

# Time-window interpretation instruction. Demo data is a fixed
# 7-day window so MAX(time) is NOT today's wall-clock — it's the latest point
# in the demo dataset. Without this instruction Genie generates
# `WHERE time >= NOW() - INTERVAL 24 HOUR` which returns 0 results because
# the data is backdated. With this instruction Genie should generate
# `WHERE time >= (SELECT MAX(time) - INTERVAL 24 HOUR FROM <table>)`.
_ensure_genie_instruction(GENIE_SPACE_ID, "Time Window Interpretation", (
    "The data in this space is a fixed 7-day demo window. The most recent "
    "timestamp in the data is NOT today's wall-clock time — it is the LATEST "
    "point in the demo dataset. When a user asks for queries like "
    "\"in the last 24 hours\", \"past 7 days\", \"recent\", or any relative "
    "time window, ALWAYS interpret the window relative to MAX(time) in the "
    "dataset, NOT relative to NOW(). Example: instead of "
    "`WHERE time >= NOW() - INTERVAL 24 HOUR`, generate "
    "`WHERE time >= (SELECT MAX(time) - INTERVAL 24 HOUR FROM <table>)`. "
    "This avoids returning 0 results because the demo data is backdated."
))

# Metric guidance: rates over raw counts. Without this, Genie answers cross-group
# questions ("out-of-range readings by device model / diagnosis / region") with a
# raw COUNT(*), which just ranks groups by fleet size — and inverts the real picture
# (the smallest cohort often has the HIGHEST out-of-range rate). Steer it to rates,
# Battelino level-2 danger bands, and device-health signals that actually reflect the
# device (completeness / gaps), not patient physiology.
_ensure_genie_instruction(GENIE_SPACE_ID, "Metric Guidance - rates over counts", (
    "For ANY comparison across groups (device_model, patient_diagnosis, region, "
    "firmware_version), ALWAYS report a RATE or PERCENTAGE, never a raw COUNT of "
    "readings — a raw count just ranks groups by how many patients/readings they have. "
    "Use ROUND(AVG(glucose_out_of_range)*100,1) AS out_of_range_pct, not COUNT(*). "
    "For 'high risk', prefer the Battelino level-2 danger bands very low <54 and very "
    "high >250 mg/dL (AVG(CASE WHEN glucose<54 OR glucose>250 THEN 1 ELSE 0 END)*100) "
    "rather than the routine <70/>180 flag. For DEVICE-HEALTH or fault questions, do "
    "NOT use glucose excursions — a failing CGM reports FEWER or biased readings, not "
    "more out-of-range glucose; use data completeness (readings vs the expected "
    "~288/day at 5-min cadence), missing-reading gaps, or calibration bias. If a user "
    "asks for the 'number' or 'total' of out-of-range readings by a group, answer with "
    "the RATE and note briefly that raw counts mostly reflect group size."
))
print(f"Genie Space ID: {GENIE_SPACE_ID}")

# COMMAND ----------

# MAGIC %md ## Part 3: Multi-Agent Supervisor

# COMMAND ----------

# DBTITLE 1, Create MAS Supervisor Agent
# NOT wrapped in `try/except Exception` — a previous "non-fatal" warning
# pattern silently swallowed real failures (the task would succeed in DABs
# even when MAS was never created). Errors propagate. The KA-ready wait
# above is the precondition that makes this safe to fail fast.
MAS_TILE_ID = ""
MAS_ENDPOINT_NAME = ""

tiles_mas = _api("GET", "/api/2.0/tiles", params={"tile_type": "MULTI_AGENT_SUPERVISOR"})
existing_mas = next(
    (t for t in tiles_mas.get("tiles", [])
     if t.get("name", "").lower() == MAS_NAME.lower()),
    None,
)

if existing_mas:
    MAS_TILE_ID = existing_mas["tile_id"]
    print(f"MAS already exists: {MAS_TILE_ID}")
else:
    print(f"Creating Supervisor Agent: {MAS_NAME}")
    mas_resp = _api("POST", "/api/2.0/multi-agent-supervisors", {
        "name":        MAS_NAME,
        "description": "Clinical intelligence supervisor for the Glucosphere CGM platform",
        "instructions": (
            "You are GlucoScope, an AI clinical intelligence assistant for the Glucosphere CGM platform. "
            "Route SQL/data questions about patient glucose readings, device incidents, "
            "fleet statistics, and trends to the CGM Genie space. "
            "Route questions about WHO diagnostic criteria, diabetes classification, "
            "and clinical guidelines to the WHO Knowledge Assistant."
        ),
        "agents": [
            {
                "name":        "CGM_Data_Explorer",
                "description": "Answers questions about patient glucose readings, device incidents, fleet statistics, time-in-range, and CGM trends by querying the gold table",
                "agent_type":  "genie",
                "genie_space": {"id": GENIE_SPACE_ID},
            },
            {
                "name":        "WHO_Guidelines_Assistant",
                "description": "Answers clinical questions about diabetes diagnosis, WHO criteria, diabetes types, and evidence-based guidelines",
                "agent_type":  "serving_endpoint",
                "serving_endpoint": {"name": KA_ENDPOINT_NAME},
            },
        ],
    })
    MAS_TILE_ID = (
        mas_resp.get("multi_agent_supervisor", {}).get("tile", {}).get("tile_id")
        or mas_resp.get("tile_id")
    )
    print(f"MAS created: tile_id={MAS_TILE_ID}")

# COMMAND ----------

# DBTITLE 1, Get MAS endpoint name (quick check, no long wait)
if MAS_TILE_ID:
    print("Fetching MAS status...")
    for attempt in range(12):  # max ~2 min
        mas_info = _api("GET", f"/api/2.0/multi-agent-supervisors/{MAS_TILE_ID}")
        status = (
            mas_info.get("multi_agent_supervisor", {})
                    .get("status", {})
                    .get("endpoint_status", "UNKNOWN")
        )
        # Same path correction as the KA block above — endpoint name lives at
        # .tile.serving_endpoint_name, not at .status.endpoint_name.
        MAS_ENDPOINT_NAME = (
            mas_info.get("multi_agent_supervisor", {})
                    .get("tile", {})
                    .get("serving_endpoint_name", "")
        )
        print(f"  MAS status: {status} | endpoint: {MAS_ENDPOINT_NAME}")
        if status in ("ONLINE", "FAILED", "ERROR") or MAS_ENDPOINT_NAME:
            break
        time.sleep(10)
else:
    print("Skipping MAS status check (MAS was not created).")
print(f"MAS endpoint name: {MAS_ENDPOINT_NAME}")

# COMMAND ----------

# DBTITLE 1, Summary
print("=" * 60)
print("DEPLOYMENT COMPLETE")
print("=" * 60)
print(f"KA tile_id:     {KA_TILE_ID}")
print(f"KA endpoint:    {KA_ENDPOINT_NAME}")
print(f"Genie space ID: {GENIE_SPACE_ID}")
print(f"MAS tile_id:    {MAS_TILE_ID}")
print(f"MAS endpoint:   {MAS_ENDPOINT_NAME}")
print()
print("Update App/databricks/app.yaml with:")
print(f"  ENDPOINT_NAME:  {MAS_ENDPOINT_NAME}")
print(f"  GENIE_SPACE_ID: {GENIE_SPACE_ID}")
