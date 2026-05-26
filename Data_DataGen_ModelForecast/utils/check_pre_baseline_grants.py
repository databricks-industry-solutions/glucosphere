# Databricks notebook source
# MAGIC %md
# MAGIC # Pre-baseline grants check
# MAGIC
# MAGIC Runs early in `glucosphere_full_setup` (after `validate_baseline_source`,
# MAGIC before `dispatch_baseline_source`). Verifies the deploying user has the
# MAGIC Unity Catalog permissions that downstream baseline + modeling tasks
# MAGIC require. Fails fast in ~5 seconds with a clear "MISSING: <grant>" message
# MAGIC if anything's missing — instead of failing 25+ minutes into the run with
# MAGIC a cryptic "PERMISSION_DENIED on operation X."
# MAGIC
# MAGIC Approach: each check actually attempts the operation (create/drop a tiny
# MAGIC probe object). This catches real capability gaps without needing to
# MAGIC introspect grants via `SHOW GRANTS` (which itself requires a permission
# MAGIC some deployers might not have).
# MAGIC
# MAGIC Checks (in order):
# MAGIC
# MAGIC 1. **USE CATALOG** on `${CATALOG_NAME}`
# MAGIC 2. **CREATE / USE SCHEMA** on `${CATALOG_NAME}.${SCHEMA_NAME}` (creates if absent)
# MAGIC 3. **CREATE TABLE** on the schema (probe table created + dropped)
# MAGIC 4. **CREATE VOLUME** on the schema (probe volume created + dropped)
# MAGIC 5. **CREATE FUNCTION** on the schema (probe UDF created + dropped)
# MAGIC
# MAGIC Skips by design (handled elsewhere or unnecessary):
# MAGIC
# MAGIC - SQL warehouse `CAN_USE` — Spark already has a working compute connection
# MAGIC   if this notebook is running, so no separate check needed
# MAGIC - Serving endpoint `CAN_QUERY` — endpoints don't exist yet at this phase;
# MAGIC   `check_post_endpoint_grants.py` handles them after creation
# MAGIC - `CREATE MODEL` — covered implicitly by the broader CREATE * on schema;
# MAGIC   probing a UC model requires registering one which is heavier than worth

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "glucosphere_catalog", "Target catalog")
dbutils.widgets.text("SCHEMA_NAME",  "glucosphere_dev",  "Target schema")

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")

# Probe-object names — kept obvious so a stranger seeing them in a SHOW TABLES
# can immediately tell they're from this preflight, not real data
PROBE_TABLE  = f"__c6_grants_probe_table_{int(__import__('time').time())}"
PROBE_VOLUME = f"__c6_grants_probe_volume_{int(__import__('time').time())}"
PROBE_FN     = f"__c6_grants_probe_fn_{int(__import__('time').time())}"

failures = []

def check(label, sql_statements, cleanup_sql=None):
    """Run sql_statements; on success print ✓; on failure record under `label`."""
    try:
        if isinstance(sql_statements, str):
            sql_statements = [sql_statements]
        for s in sql_statements:
            spark.sql(s)
        print(f"[grants] ✓ {label}")
    except Exception as e:
        # Trim the Spark stack trace to the actual error message for readability
        msg = str(e).splitlines()[0] if str(e) else repr(e)
        failures.append(f"  ❌ {label}\n      {msg[:300]}")
    finally:
        if cleanup_sql is not None:
            try:
                if isinstance(cleanup_sql, str):
                    cleanup_sql = [cleanup_sql]
                for s in cleanup_sql:
                    spark.sql(s)
            except Exception:
                pass  # best-effort cleanup; don't mask real failure

# COMMAND ----------

bar = "=" * 72
print(bar)
print(f"  glucosphere_full_setup — PRE-BASELINE GRANTS CHECK")
print(bar)
print(f"  catalog = {CATALOG_NAME}")
print(f"  schema  = {SCHEMA_NAME}")
print(bar)

# Check 1: USE CATALOG
check(
    f"USE CATALOG `{CATALOG_NAME}`",
    f"USE CATALOG `{CATALOG_NAME}`",
)

# Check 2: CREATE SCHEMA + USE SCHEMA
check(
    f"CREATE SCHEMA / USE SCHEMA on `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
    [
        f"CREATE SCHEMA IF NOT EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
        f"USE `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
    ],
)

# Check 3: CREATE TABLE (probe + drop)
check(
    f"CREATE TABLE on `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
    f"CREATE TABLE IF NOT EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_TABLE} (id INT)",
    cleanup_sql=f"DROP TABLE IF EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_TABLE}",
)

# Check 4: CREATE VOLUME (probe + drop)
check(
    f"CREATE VOLUME on `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
    f"CREATE VOLUME IF NOT EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_VOLUME}",
    cleanup_sql=f"DROP VOLUME IF EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_VOLUME}",
)

# Check 5: CREATE FUNCTION (probe + drop)
check(
    f"CREATE FUNCTION on `{CATALOG_NAME}`.`{SCHEMA_NAME}`",
    f"CREATE FUNCTION IF NOT EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_FN}() RETURNS INT RETURN 1",
    cleanup_sql=f"DROP FUNCTION IF EXISTS `{CATALOG_NAME}`.`{SCHEMA_NAME}`.{PROBE_FN}",
)

# COMMAND ----------

print(bar)
if failures:
    print(f"  ❌ {len(failures)} grant check(s) FAILED:")
    print()
    for f in failures:
        print(f)
    print()
    print(bar)
    raise PermissionError(
        f"Pre-baseline grants check failed ({len(failures)} missing). "
        f"The deploying user is missing UC permissions required by downstream "
        f"baseline + modeling tasks. Fix grants and re-run."
    )
else:
    print(f"  ✓ all 5 grant checks PASSED")
    print(bar)
