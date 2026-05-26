# Databricks notebook source
# MAGIC %md
# MAGIC # Validate baseline_source + print run banner
# MAGIC
# MAGIC Runs at the head of `glucosphere_full_setup`. Three responsibilities:
# MAGIC
# MAGIC 1. **Enum validation** — `baseline_source` must be one of
# MAGIC    `{synthetic, from_source, from_table}`. Fail fast on typos
# MAGIC    or invalid values, BEFORE the dispatch routes to the wrong branch.
# MAGIC 2. **Mode banner** — print a clear banner at the very start of the run
# MAGIC    so anyone reading the job log immediately knows which mode is
# MAGIC    selected, what catalog/schema is the target, and which source table
# MAGIC    will be read (if applicable).
# MAGIC 3. **Provenance write** — overwrite a 1-row `baseline_provenance` UC
# MAGIC    table with the validated mode + source detail + timestamp. The App's
# MAGIC    `/api/config` route queries this row (with 60s TTL cache) so the
# MAGIC    Metrics Explained page can render mode-accurate prose without
# MAGIC    relying on deploy-time env vars (which can skew from the pipeline's
# MAGIC    actual run mode). See `~/.claude/projects/.../memory/reference_provenance_table_pattern.md`.

# COMMAND ----------

dbutils.widgets.text("BASELINE_SOURCE",  "synthetic",         "Baseline source mode")
dbutils.widgets.text("CATALOG_NAME",     "glucosphere_catalog",  "Target catalog")
dbutils.widgets.text("SCHEMA_NAME",      "glucosphere_dev",   "Target schema")
dbutils.widgets.text("SOURCE_CATALOG",   "",                  "Source catalog (from_table only)")
dbutils.widgets.text("SOURCE_SCHEMA",    "",                  "Source schema (from_table only)")
dbutils.widgets.text("SOURCE_TABLE",     "",                  "Source table (from_table only)")

BASELINE_SOURCE = dbutils.widgets.get("BASELINE_SOURCE")
CATALOG_NAME    = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME     = dbutils.widgets.get("SCHEMA_NAME")
SOURCE_CATALOG  = dbutils.widgets.get("SOURCE_CATALOG")
SOURCE_SCHEMA   = dbutils.widgets.get("SOURCE_SCHEMA")
SOURCE_TABLE    = dbutils.widgets.get("SOURCE_TABLE")

# COMMAND ----------

# Enum validation — fail fast on typos
ALLOWED_MODES = {"synthetic", "from_source", "from_table"}
if BASELINE_SOURCE not in ALLOWED_MODES:
    raise ValueError(
        f"Invalid baseline_source={BASELINE_SOURCE!r}. "
        f"Expected one of {sorted(ALLOWED_MODES)}. "
        f"Set the bundle var --var baseline_source=<value> or fix the target's "
        f"variables block in databricks.yml. (A common cause is a typo like "
        f"'syntethic' or a stray quote/space.)"
    )

# from_table source resolution — match dual_01's auto-detect (#72):
#   1. Explicit SOURCE_CATALOG/SCHEMA/TABLE widgets win if all three set.
#   2. Otherwise auto-detect against priority list under CATALOG_NAME.
#   3. If neither resolves, fail fast here (before the real-baseline notebook
#      attempts the read).
# The resolved values are surfaced in the banner below + the provenance row,
# AND re-exported as widget defaults so dual_01 sees the same selection.
SOURCE_FQN = None
if BASELINE_SOURCE == "from_table":
    if SOURCE_CATALOG and SOURCE_SCHEMA and SOURCE_TABLE:
        SOURCE_FQN = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{SOURCE_TABLE}"
        SOURCE_PROVENANCE = f"{SOURCE_FQN} (explicit widgets)"
    else:
        priority_candidates = [
            (f"{CATALOG_NAME}.glucosphere_dev.diabetes_data",             "live production"),
            (f"{CATALOG_NAME}.glucosphere_from_source_e2e.diabetes_data", "real-data harness"),
            (f"{CATALOG_NAME}.glucosphere_synth_e2e.diabetes_data",       "synth harness"),
        ]
        selected_label = None
        for fqn, label in priority_candidates:
            if spark.catalog.tableExists(fqn):
                SOURCE_FQN = fqn
                selected_label = label
                break
        if SOURCE_FQN is None:
            tried = "\n  - ".join(f"{fqn} ({label})" for fqn, label in priority_candidates)
            raise ValueError(
                "baseline_source=from_table could not auto-detect a source table. "
                "Tried (in priority order):\n  - "
                f"{tried}\n"
                "Either populate one of those, or set SOURCE_CATALOG/SCHEMA/TABLE "
                "explicitly via bundle vars or widget UI."
            )
        SOURCE_PROVENANCE = f"{SOURCE_FQN} (auto-detected: {selected_label})"

# COMMAND ----------

# Mode banner — make the dispatch obvious in the log
branch = "synthetic" if BASELINE_SOURCE == "synthetic" else "real"
target_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data"

bar = "=" * 72
print(bar)
print(f"  glucosphere_full_setup — RUN PREFLIGHT")
print(bar)
print(f"  baseline_source       = {BASELINE_SOURCE}")
print(f"  dispatch branch       = {branch}")
print(f"  target catalog.schema = {CATALOG_NAME}.{SCHEMA_NAME}")
print(f"  target diabetes table = {target_table}")
if BASELINE_SOURCE == "from_table":
    print(f"  source table          = {SOURCE_PROVENANCE}")
elif BASELINE_SOURCE == "from_source":
    print(f"  source                = HUPA-UCM Mendeley dataset (downloaded fresh)")
else:
    print(f"  source                = synthetic generator (textbook phenotypes + AR(1))")
print(bar)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Provenance write
# MAGIC
# MAGIC Write a 1-row `baseline_provenance` table so the App's `/api/config` route
# MAGIC can render mode-accurate prose on the Metrics Explained page (from_source
# MAGIC mention HUPA-UCM seed, synthetic mention textbook generator, etc.) without
# MAGIC having to read deploy-time env vars (which can skew from the pipeline's
# MAGIC actual run mode). Single-row table replaced on every pipeline run.

# COMMAND ----------

source_detail = (
    SOURCE_FQN if BASELINE_SOURCE == "from_table"
    else "HUPA-UCM Mendeley dataset" if BASELINE_SOURCE == "from_source"
    else "synthetic generator (textbook phenotypes + AR(1))"
)
# Ensure schema exists before writing provenance. dual_01_* notebooks (which
# create the schema themselves) run AFTER this validate task, so for any fresh
# sandbox deploy (e.g., the mmt_aws_usw2_synth_e2e / from_table_e2e harness
# targets, or any new workspace bootstrap) the schema doesn't exist yet at
# this point. Idempotent CREATE SCHEMA IF NOT EXISTS — no-op for existing
# schemas (e.g., the live mmt_aws_usw2.glucosphere_dev target).
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.baseline_provenance (
        baseline_source STRING,
        source_detail   STRING,
        last_run_at     TIMESTAMP
    )
""")
spark.sql(f"""
    INSERT OVERWRITE {CATALOG_NAME}.{SCHEMA_NAME}.baseline_provenance VALUES
        ('{BASELINE_SOURCE}', '{source_detail}', current_timestamp())
""")
print(f"[PROVENANCE] Wrote baseline_provenance row: baseline_source={BASELINE_SOURCE!r}, source_detail={source_detail!r}")
