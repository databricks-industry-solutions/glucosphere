# Databricks notebook source
# MAGIC %md
# MAGIC # Glucosphere: Grant App Service Principal Permissions
# MAGIC
# MAGIC > ⛔ **Do not run standalone.** This notebook is invoked by the `glucosphere` full_setup job
# MAGIC > DAG, which injects per-target `CATALOG_NAME` / `SCHEMA_NAME` / `BUNDLE_TARGET` / `APP_NAME` /
# MAGIC > `KA_NAME` / `MAS_NAME` / `GENIE_NAME`. The widget defaults are intentionally **blank** so a
# MAGIC > bare manual run aborts (see the guard cell) instead of granting the wrong app/endpoints in
# MAGIC > the wrong catalog. To run by hand, pass all required params for your target.
# MAGIC
# MAGIC Programmatically:
# MAGIC 1. Look up the Glucosphere App's service principal from the Apps API
# MAGIC 2. Grant `USE CATALOG`, `USE SCHEMA`, `SELECT` on `{catalog}.{schema}` via SQL
# MAGIC 3. Grant `CAN_QUERY` on the MAS serving endpoint
# MAGIC 4. Grant `CAN_QUERY` on the KA serving endpoint
# MAGIC 5. Grant access to the Genie space
# MAGIC
# MAGIC **Prerequisites:** App must be deployed (run `databricks bundle deploy` first).

# COMMAND ----------

# DBTITLE 1, Parameters
# Per-target params: defaults are intentionally BLANK so a standalone run (which would otherwise
# fall back to prod-flavored values and grant the WRONG app/endpoints in the WRONG catalog) trips
# the guard below. The full_setup job injects all of these via base_parameters, which override the
# blank widget defaults — so DAG runs are unaffected. (Was: APP_NAME="glucosphere-app",
# KA_NAME="Glucosphere_KA", etc. — moved to required-from-DAG to close the standalone-run footgun.)
dbutils.widgets.text("CATALOG_NAME",       "",  "Catalog (required — set by the bundle job)")
dbutils.widgets.text("SCHEMA_NAME",        "",  "Schema (required — set by the bundle job)")
dbutils.widgets.text("APP_NAME",           "",  "App Name (required — set by the bundle job)")
dbutils.widgets.text("MAS_ENDPOINT_NAME",  "",  "MAS Endpoint Name (empty → looked up by MAS_NAME tile)")
dbutils.widgets.text("KA_ENDPOINT_NAME",   "",  "KA Endpoint Name (empty → looked up by KA_NAME tile)")
dbutils.widgets.text("GENIE_SPACE_ID",     "",  "Genie Space ID (empty → looked up by GENIE_NAME)")
dbutils.widgets.text("WAREHOUSE_ID",       "",  "SQL Warehouse ID (empty → discovered by BUNDLE_TARGET)")
dbutils.widgets.text("BUNDLE_TARGET",      "",  "Bundle target (required — set by the bundle job; also discovers warehouse)")
# Canonical KA/MAS/Genie names — injected per-target by the job as "Glucosphere_*${harness_suffix}".
# Discovery uses these for *exact-equality* matches against the tile catalog / Genie space list,
# avoiding substring-match brittleness (e.g. another team's `ka-*-endpoint`). Defaults BLANK +
# required (see guard) so a bare run can't silently use the unsuffixed prod anchors.
dbutils.widgets.text("KA_NAME",            "",  "KA tile name (required — set by the bundle job)")
dbutils.widgets.text("MAS_NAME",           "",  "MAS tile name (required — set by the bundle job)")
dbutils.widgets.text("GENIE_NAME",         "",  "Genie space display name (required — set by the bundle job)")

CATALOG_NAME      = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME       = dbutils.widgets.get("SCHEMA_NAME")
APP_NAME          = dbutils.widgets.get("APP_NAME")
MAS_ENDPOINT_NAME = dbutils.widgets.get("MAS_ENDPOINT_NAME")
KA_ENDPOINT_NAME  = dbutils.widgets.get("KA_ENDPOINT_NAME")
GENIE_SPACE_ID    = dbutils.widgets.get("GENIE_SPACE_ID")
WAREHOUSE_ID      = dbutils.widgets.get("WAREHOUSE_ID")
BUNDLE_TARGET     = dbutils.widgets.get("BUNDLE_TARGET")
KA_NAME           = dbutils.widgets.get("KA_NAME")
MAS_NAME          = dbutils.widgets.get("MAS_NAME")
GENIE_NAME        = dbutils.widgets.get("GENIE_NAME")

print(f"Catalog:      {CATALOG_NAME}.{SCHEMA_NAME}")
print(f"App:          {APP_NAME}")
print(f"MAS endpoint: {MAS_ENDPOINT_NAME}")
print(f"KA endpoint:  {KA_ENDPOINT_NAME}")
print(f"Genie space:  {GENIE_SPACE_ID}")
print(f"Warehouse:    {WAREHOUSE_ID}")

# GUARD — refuse standalone runs. This notebook grants the App SP access to PER-TARGET resources
# and is meant to run ONLY from the glucosphere full_setup job DAG, which injects the values below
# for the target being deployed. Run by hand, the widget defaults are blank (see above), so abort
# loudly here rather than fall back to wrong values and grant the wrong app/endpoints in the wrong
# catalog. DAG base_parameters override the blank defaults, so job runs are unaffected. To run
# manually, pass all required params for your target.
_required = {
    "CATALOG_NAME": CATALOG_NAME, "SCHEMA_NAME": SCHEMA_NAME, "BUNDLE_TARGET": BUNDLE_TARGET,
    "APP_NAME": APP_NAME, "KA_NAME": KA_NAME, "MAS_NAME": MAS_NAME, "GENIE_NAME": GENIE_NAME,
}
_missing = [k for k, v in _required.items() if not (v or "").strip()]
assert not _missing, (
    f"Refusing to run: {_missing} not set. 09_grant_app_permissions runs from the glucosphere "
    f"full_setup job, which injects per-target values. Do NOT run it standalone — the widget "
    f"defaults are intentionally blank so a bare run aborts here instead of granting the wrong "
    f"resources. To run by hand, pass all required params for your target."
)

# COMMAND ----------

# DBTITLE 1, REST API helper
import json
import time
import urllib.request
import urllib.error

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
    req  = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

# COMMAND ----------

# DBTITLE 1, Look up App service principal
status, app_data = _api("GET", f"/api/2.0/apps/{APP_NAME}")
if status != 200:
    raise Exception(f"Could not fetch app '{APP_NAME}': {status} {app_data}")

sp_client_id = app_data.get("service_principal_client_id") or app_data.get("id")
sp_name      = app_data.get("service_principal_name", str(sp_client_id))

# Unity Catalog GRANT requires the SP's applicationId (UUID), not the display name
# (e.g. "app-3jrqvp glucosphere-app" is not a valid UC principal). The app object's
# `service_principal_client_id` IS that applicationId UUID, so use it directly.
#
# Prior approach (commented out, kept for reference — NOT deleted): a SCIM
# ServicePrincipals lookup on `service_principal_id`. It was redundant (the client_id
# above already is the applicationId) AND crashed with JSONDecodeError when
# `service_principal_id` is absent from the app object, as on the DAIS booth workspace:
#   status_scim, scim_data = _api("GET", f"/api/2.0/preview/scim/v2/ServicePrincipals/{app_data.get('service_principal_id')}")
#   sp_app_id = scim_data.get("applicationId") or sp_client_id
sp_app_id = sp_client_id

print(f"App SP client ID:    {sp_client_id}")
print(f"App SP display name: {sp_name}")
print(f"App SP applicationId (for GRANT): {sp_app_id}")
assert sp_app_id, "Could not determine service principal applicationId — is the app deployed?"

# COMMAND ----------

# DBTITLE 1, Auto-discover endpoint names + Genie space (anchored by exact name)
# Look up the serving_endpoint_name from the tile whose `name` matches the
# canonical KA/MAS name set in notebook 08. The /api/2.0/tiles response carries
# `serving_endpoint_name` directly per tile, so this is a single round-trip and
# guarantees the discovered endpoint is the one we just created — not a
# substring sibling from another team's work in the same workspace.
def _find_endpoint_by_tile_name(tile_type: str, tile_name: str) -> str:
    status, data = _api("GET", "/api/2.0/tiles", params={"tile_type": tile_type})
    if status != 200:
        return ""
    for t in data.get("tiles", []):
        if t.get("name") == tile_name:
            return t.get("serving_endpoint_name", "")
    return ""

if not MAS_ENDPOINT_NAME:
    MAS_ENDPOINT_NAME = _find_endpoint_by_tile_name("MULTI_AGENT_SUPERVISOR", MAS_NAME)
    print(f"Auto-discovered MAS endpoint via tile {MAS_NAME!r}: {MAS_ENDPOINT_NAME!r}")

if not KA_ENDPOINT_NAME:
    KA_ENDPOINT_NAME = _find_endpoint_by_tile_name("KNOWLEDGE_ASSISTANT", KA_NAME)
    print(f"Auto-discovered KA endpoint via tile {KA_NAME!r}: {KA_ENDPOINT_NAME!r}")

if not GENIE_SPACE_ID:
    # Exact name match against the Genie space (same bug class as the tile
    # lookups above — substring/partial match could pick up an unrelated CGM
    # or glucose-themed space in a workspace with multiple Genie rooms).
    # API choice (/data-rooms vs /genie/spaces): see notebook 08 comment.
    status, data = _api("GET", "/api/2.0/data-rooms/")
    for room in (data.get("data_rooms", []) if status == 200 else []):
        if room.get("display_name", "") == GENIE_NAME:
            GENIE_SPACE_ID = room.get("space_id") or room.get("id", "")
            print(f"Auto-discovered Genie space {GENIE_NAME!r}: {GENIE_SPACE_ID!r}")
            break

# COMMAND ----------

# DBTITLE 1, Grant Unity Catalog SQL permissions
sql_grants = [
    f"GRANT USE CATALOG ON CATALOG {CATALOG_NAME} TO `{sp_app_id}`",
    f"GRANT USE SCHEMA ON SCHEMA {CATALOG_NAME}.{SCHEMA_NAME} TO `{sp_app_id}`",
    f"GRANT SELECT ON SCHEMA {CATALOG_NAME}.{SCHEMA_NAME} TO `{sp_app_id}`",
    # READ VOLUME on pipeline_data — required for the Flask /uc-assets/ route in
    # App/databricks/app.py to fetch notebook-generated PNGs live from UC Volume
    # at runtime. Without this grant, the App gets 403 PERMISSION_DENIED when
    # MetricsExplained.jsx tries to load the distribution-comparison PNG.
    # Volume name "pipeline_data" is hardcoded across the pipeline (see grep
    # results in 02/05/app.py + transformations.sql).
    f"GRANT READ VOLUME ON VOLUME {CATALOG_NAME}.{SCHEMA_NAME}.pipeline_data TO `{sp_app_id}`",
]

for sql in sql_grants:
    try:
        spark.sql(sql)
        print(f"  ✓ {sql}")
    except Exception as e:
        print(f"  ✗ {sql}\n    Error: {e}")

# COMMAND ----------

# DBTITLE 1, Grant CAN_QUERY on serving endpoints
def grant_endpoint_permission(endpoint_name, sp_name):
    if not endpoint_name:
        print("  ⚠ Skipping — endpoint name not provided")
        return
    # Get internal endpoint ID
    status, ep_data = _api("GET", f"/api/2.0/serving-endpoints/{endpoint_name}")
    if status != 200:
        print(f"  ✗ Could not fetch endpoint '{endpoint_name}': {status}")
        return
    ep_id = ep_data.get("id")
    # PATCH permissions
    status2, perm_resp = _api("PATCH",
        f"/api/2.0/permissions/serving-endpoints/{ep_id}",
        {"access_control_list": [
            {"service_principal_name": sp_app_id, "permission_level": "CAN_QUERY"}
        ]}
    )
    if status2 == 200:
        print(f"  ✓ CAN_QUERY granted on {endpoint_name}")
    else:
        print(f"  ✗ Failed to grant CAN_QUERY on {endpoint_name}: {status2} {perm_resp}")

print("Granting endpoint permissions:")
grant_endpoint_permission(MAS_ENDPOINT_NAME, sp_app_id)
grant_endpoint_permission(KA_ENDPOINT_NAME, sp_app_id)

# COMMAND ----------

# DBTITLE 1, Grant CAN_USE on SQL warehouse
# Discover the bundle-managed warehouse by deterministic name when WAREHOUSE_ID
# is empty. Pattern: `glucosphere-warehouse-<BUNDLE_TARGET>` (with `[dev USER]`
# auto-prefix when target uses `mode: development`). Uses `endswith` to handle
# both cases. Falls through cleanly if neither WAREHOUSE_ID nor BUNDLE_TARGET set.
if not WAREHOUSE_ID and BUNDLE_TARGET:
    expected_suffix = f"glucosphere-warehouse-{BUNDLE_TARGET}"
    status_wl, wl_resp = _api("GET", "/api/2.0/sql/warehouses")
    if status_wl == 200:
        for w in wl_resp.get("warehouses", []):
            if w.get("name", "").endswith(expected_suffix):
                WAREHOUSE_ID = w["id"]
                print(f"  → discovered warehouse {WAREHOUSE_ID} by name '{w['name']}'")
                break
        if not WAREHOUSE_ID:
            print(f"  ⚠ No warehouse matching suffix '{expected_suffix}' — was bundle deployed?")
    else:
        print(f"  ✗ warehouses list failed: {status_wl} {wl_resp}")

if WAREHOUSE_ID:
    status_wh, wh_resp = _api("PATCH",
        f"/api/2.0/permissions/warehouses/{WAREHOUSE_ID}",
        {"access_control_list": [
            {"service_principal_name": sp_app_id, "permission_level": "CAN_USE"}
        ]}
    )
    if status_wh == 200:
        print(f"  ✓ CAN_USE granted on warehouse {WAREHOUSE_ID}")
    else:
        print(f"  ✗ Failed to grant CAN_USE on warehouse {WAREHOUSE_ID}: {status_wh} {wh_resp}")
else:
    print("  ⚠ No warehouse ID — skipping warehouse permission")

# COMMAND ----------

# DBTITLE 1, Grant Genie space access
if GENIE_SPACE_ID:
    # Genie spaces use /api/2.0/permissions/genie/{space_id}
    # Valid levels: CAN_RUN, CAN_EDIT, CAN_MANAGE
    status, perm_resp = _api("PATCH",
        f"/api/2.0/permissions/genie/{GENIE_SPACE_ID}",
        {"access_control_list": [
            {"service_principal_name": sp_app_id, "permission_level": "CAN_RUN"}
        ]}
    )
    if status == 200:
        print(f"  ✓ CAN_RUN granted on Genie space {GENIE_SPACE_ID}")
    else:
        print(f"  ✗ Genie space grant returned {status}: {perm_resp}")
else:
    print("  ⚠ No Genie space ID — skipping Genie permissions")

# COMMAND ----------

# DBTITLE 1, Summary
print("\n" + "="*60)
print("Glucosphere App Permissions Summary")
print("="*60)
print(f"Service Principal: {sp_name} ({sp_app_id})")
print(f"Catalog access:    {CATALOG_NAME}.{SCHEMA_NAME}  (USE CATALOG, USE SCHEMA, SELECT)")
print(f"MAS endpoint:      {MAS_ENDPOINT_NAME or 'N/A'}  (CAN_QUERY)")
print(f"KA endpoint:       {KA_ENDPOINT_NAME or 'N/A'}   (CAN_QUERY)")
print(f"Genie space:       {GENIE_SPACE_ID or 'N/A'}     (CAN_RUN)")
print("="*60)
print("Done.")
