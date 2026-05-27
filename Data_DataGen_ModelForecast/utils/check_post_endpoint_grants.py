# Databricks notebook source
# MAGIC %md
# MAGIC # Post-endpoint grants check
# MAGIC
# MAGIC Runs after `create_genie_ka_mas` (which creates the KA + MAS tiles +
# MAGIC serving endpoints + Genie space). Verifies the endpoints + Genie space
# MAGIC exist and are queryable BEFORE `grant_app_permissions` runs.
# MAGIC
# MAGIC The split into pre-baseline / post-endpoint matters because these
# MAGIC resources don't exist at job start — checking them pre-baseline would
# MAGIC always false-fail. By the time this notebook runs, the resources
# MAGIC should be in place (or the job will have failed earlier).
# MAGIC
# MAGIC Checks (best-effort; logs warnings rather than failing the whole task,
# MAGIC since `grant_app_permissions` runs immediately after and will apply
# MAGIC grants regardless):
# MAGIC
# MAGIC 1. KA tile exists in `/api/2.0/tiles` with `tile_type=KA` named
# MAGIC    `Glucosphere-Knowledge-Assistant`
# MAGIC 2. KA tile has a non-empty `serving_endpoint_name` (the actual
# MAGIC    `ka-<hash>-endpoint` provisioned by Agent Bricks)
# MAGIC 3. MAS tile exists similarly, with non-empty `serving_endpoint_name`
# MAGIC 4. Genie space exists with title matching the expected name

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "glucosphere_catalog", "Target catalog (unused; here for parity)")
dbutils.widgets.text("SCHEMA_NAME",  "glucosphere_schema",  "Target schema (unused; here for parity)")
dbutils.widgets.text("KA_NAME",      "Glucosphere-Knowledge-Assistant", "KA tile name")
dbutils.widgets.text("MAS_NAME",     "Glucosphere-Supervisor",          "MAS tile name")
dbutils.widgets.text("GENIE_NAME",   "Glucosphere CGM Intelligence",    "Genie space title")

KA_NAME    = dbutils.widgets.get("KA_NAME")
MAS_NAME   = dbutils.widgets.get("MAS_NAME")
GENIE_NAME = dbutils.widgets.get("GENIE_NAME")

# COMMAND ----------

# API helpers (same pattern as notebook 09)
import json
import urllib.request

def _workspace_host():
    return dbutils.notebook.entry_point.getDbutils().notebook().getContext() \
        .apiUrl().getOrElse(None)

def _token():
    return dbutils.notebook.entry_point.getDbutils().notebook().getContext() \
        .apiToken().getOrElse(None)

def _api_get(path):
    req = urllib.request.Request(
        f"{_workspace_host()}{path}",
        headers={"Authorization": f"Bearer {_token()}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

# COMMAND ----------

warnings = []

def find_tile(tile_type, name):
    """Look up a tile by name + type. Returns the tile dict or None."""
    try:
        all_tiles = _api_get("/api/2.0/tiles").get("tiles", [])
    except Exception as e:
        warnings.append(f"  ⚠️  Could not list tiles: {e}")
        return None
    matches = [
        t for t in all_tiles
        if t.get("tile_type") == tile_type and t.get("name", "").lower() == name.lower()
    ]
    return matches[0] if matches else None

bar = "=" * 72
print(bar)
print(f"  glucosphere_full_setup — POST-ENDPOINT GRANTS CHECK")
print(bar)

# Check 1 + 2: KA tile + serving endpoint name
ka = find_tile("KA", KA_NAME)
if ka is None:
    warnings.append(f"  ⚠️  KA tile {KA_NAME!r} not found")
else:
    ka_endpoint = ka.get("serving_endpoint_name", "")
    if not ka_endpoint:
        warnings.append(f"  ⚠️  KA tile found but serving_endpoint_name is empty")
    else:
        print(f"  ✓ KA: tile_id={ka['tile_id']}, endpoint={ka_endpoint}")

# Check 3: MAS tile + serving endpoint name
mas = find_tile("MAS", MAS_NAME)
if mas is None:
    warnings.append(f"  ⚠️  MAS tile {MAS_NAME!r} not found")
else:
    mas_endpoint = mas.get("serving_endpoint_name", "")
    if not mas_endpoint:
        warnings.append(f"  ⚠️  MAS tile found but serving_endpoint_name is empty")
    else:
        print(f"  ✓ MAS: tile_id={mas['tile_id']}, endpoint={mas_endpoint}")

# Check 4: Genie space exists
try:
    spaces = _api_get("/api/2.0/genie/spaces?page_size=50").get("spaces", [])
    genie = next((s for s in spaces if s.get("title", "") == GENIE_NAME), None)
    if genie is None:
        warnings.append(f"  ⚠️  Genie space {GENIE_NAME!r} not found")
    else:
        print(f"  ✓ Genie: space_id={genie.get('id') or genie.get('space_id')}")
except Exception as e:
    warnings.append(f"  ⚠️  Could not list Genie spaces: {e}")

# COMMAND ----------

print(bar)
if warnings:
    print(f"  ⚠️  {len(warnings)} resource(s) NOT FOUND or incomplete:")
    print()
    for w in warnings:
        print(w)
    print()
    print(f"  These are WARNINGS, not failures — grant_app_permissions runs next")
    print(f"  and will surface the actual grant-application problem clearly.")
    print(bar)
else:
    print(f"  ✓ all 3 resources (KA, MAS, Genie) found and queryable")
    print(bar)
