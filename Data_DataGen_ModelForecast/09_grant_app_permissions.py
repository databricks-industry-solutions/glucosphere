# Databricks notebook source
# MAGIC %md
# MAGIC # Glucosphere: Grant App Service Principal Permissions
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
dbutils.widgets.text("CATALOG_NAME",       "",                            "Catalog (required — set by the bundle job; e.g. mmt_aws_usw2_catalog)")
dbutils.widgets.text("SCHEMA_NAME",        "glucosphere_schema",         "Schema")
dbutils.widgets.text("APP_NAME",           "glucosphere-app",            "App Name")
dbutils.widgets.text("MAS_ENDPOINT_NAME",  "",                           "MAS Endpoint Name")
dbutils.widgets.text("KA_ENDPOINT_NAME",   "",                           "KA Endpoint Name")
dbutils.widgets.text("GENIE_SPACE_ID",     "",                           "Genie Space ID")
dbutils.widgets.text("WAREHOUSE_ID",       "",                           "SQL Warehouse ID (empty → discovered by BUNDLE_TARGET)")
dbutils.widgets.text("BUNDLE_TARGET",      "",                           "Bundle target name (used to discover warehouse if WAREHOUSE_ID empty)")

CATALOG_NAME      = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME       = dbutils.widgets.get("SCHEMA_NAME")
APP_NAME          = dbutils.widgets.get("APP_NAME")
MAS_ENDPOINT_NAME = dbutils.widgets.get("MAS_ENDPOINT_NAME")
KA_ENDPOINT_NAME  = dbutils.widgets.get("KA_ENDPOINT_NAME")
GENIE_SPACE_ID    = dbutils.widgets.get("GENIE_SPACE_ID")
WAREHOUSE_ID      = dbutils.widgets.get("WAREHOUSE_ID")
BUNDLE_TARGET     = dbutils.widgets.get("BUNDLE_TARGET")

print(f"Catalog:      {CATALOG_NAME}.{SCHEMA_NAME}")
print(f"App:          {APP_NAME}")
print(f"MAS endpoint: {MAS_ENDPOINT_NAME}")
print(f"KA endpoint:  {KA_ENDPOINT_NAME}")
print(f"Genie space:  {GENIE_SPACE_ID}")
print(f"Warehouse:    {WAREHOUSE_ID}")

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

# Unity Catalog GRANT requires the SP's applicationId (UUID), not the display name.
# The display name (e.g. "app-3jrqvp glucosphere-app") is not a valid UC principal.
status_scim, scim_data = _api("GET", f"/api/2.0/preview/scim/v2/ServicePrincipals/{app_data.get('service_principal_id')}")
sp_app_id = scim_data.get("applicationId") or sp_client_id

print(f"App SP client ID:    {sp_client_id}")
print(f"App SP display name: {sp_name}")
print(f"App SP applicationId (for GRANT): {sp_app_id}")
assert sp_app_id, "Could not determine service principal applicationId — is the app deployed?"

# COMMAND ----------

# DBTITLE 1, Auto-discover endpoint names from app resources (if not set as parameters)
def _find_endpoint_by_suffix(suffix):
    """Scan all serving endpoints for one whose name ends with the given suffix."""
    status, data = _api("GET", "/api/2.0/serving-endpoints")
    if status != 200:
        return None
    for ep in data.get("endpoints", []):
        if ep["name"].endswith(suffix):
            return ep["name"]
    return None

if not MAS_ENDPOINT_NAME:
    MAS_ENDPOINT_NAME = _find_endpoint_by_suffix("-endpoint") or ""
    # Narrow to the MAS endpoint specifically (contains "mas" or "supervisor")
    status, data = _api("GET", "/api/2.0/serving-endpoints")
    for ep in (data.get("endpoints", []) if status == 200 else []):
        name = ep["name"].lower()
        if "mas" in name or "supervisor" in name:
            MAS_ENDPOINT_NAME = ep["name"]
            break
    print(f"Auto-discovered MAS endpoint: {MAS_ENDPOINT_NAME}")

if not KA_ENDPOINT_NAME:
    status, data = _api("GET", "/api/2.0/serving-endpoints")
    for ep in (data.get("endpoints", []) if status == 200 else []):
        name = ep["name"].lower()
        if "ka" in name or "knowledge" in name:
            KA_ENDPOINT_NAME = ep["name"]
            break
    print(f"Auto-discovered KA endpoint: {KA_ENDPOINT_NAME}")

if not GENIE_SPACE_ID:
    # Try to find Genie space by name
    status, data = _api("GET", "/api/2.0/data-rooms/")
    for room in (data.get("data_rooms", []) if status == 200 else []):
        display = room.get("display_name", "") or room.get("name", "")
        if "glucosphere" in display.lower() or "cgm" in display.lower():
            GENIE_SPACE_ID = room.get("space_id") or room.get("id", "")
            print(f"Auto-discovered Genie space: {display} ({GENIE_SPACE_ID})")
            break

# COMMAND ----------

# DBTITLE 1, Grant Unity Catalog SQL permissions
sql_grants = [
    f"GRANT USE CATALOG ON CATALOG {CATALOG_NAME} TO `{sp_app_id}`",
    f"GRANT USE SCHEMA ON SCHEMA {CATALOG_NAME}.{SCHEMA_NAME} TO `{sp_app_id}`",
    f"GRANT SELECT ON SCHEMA {CATALOG_NAME}.{SCHEMA_NAME} TO `{sp_app_id}`",
    # READ VOLUME on landing_zone — required for the Flask /uc-assets/ route in
    # App/databricks/app.py to fetch notebook-generated PNGs live from UC Volume
    # at runtime. Without this grant, the App gets 403 PERMISSION_DENIED when
    # MetricsExplained.jsx tries to load the distribution-comparison PNG.
    # Volume name "landing_zone" is hardcoded across the pipeline (see grep
    # results in 02/05/app.py + transformations.sql).
    f"GRANT READ VOLUME ON VOLUME {CATALOG_NAME}.{SCHEMA_NAME}.landing_zone TO `{sp_app_id}`",
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
