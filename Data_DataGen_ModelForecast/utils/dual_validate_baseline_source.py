# Databricks notebook source
# MAGIC %md
# MAGIC # Validate baseline_source + print run banner
# MAGIC
# MAGIC Runs at the head of `glucosphere_full_setup`. Two responsibilities:
# MAGIC
# MAGIC 1. **Enum validation** — `baseline_source` must be one of
# MAGIC    `{synthetic, real_from_source, real_from_table}`. Fail fast on typos
# MAGIC    or invalid values, BEFORE the dispatch routes to the wrong branch.
# MAGIC 2. **Mode banner** — print a clear banner at the very start of the run
# MAGIC    so anyone reading the job log immediately knows which mode is
# MAGIC    selected, what catalog/schema is the target, and which source table
# MAGIC    will be read (if applicable).

# COMMAND ----------

dbutils.widgets.text("BASELINE_SOURCE",  "synthetic",         "Baseline source mode")
dbutils.widgets.text("CATALOG_NAME",     "hls_amer_catalog",  "Target catalog")
dbutils.widgets.text("SCHEMA_NAME",      "glucosphere_dev",   "Target schema")
dbutils.widgets.text("SOURCE_CATALOG",   "",                  "Source catalog (real_from_table only)")
dbutils.widgets.text("SOURCE_SCHEMA",    "",                  "Source schema (real_from_table only)")
dbutils.widgets.text("SOURCE_TABLE",     "",                  "Source table (real_from_table only)")

BASELINE_SOURCE = dbutils.widgets.get("BASELINE_SOURCE")
CATALOG_NAME    = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME     = dbutils.widgets.get("SCHEMA_NAME")
SOURCE_CATALOG  = dbutils.widgets.get("SOURCE_CATALOG")
SOURCE_SCHEMA   = dbutils.widgets.get("SOURCE_SCHEMA")
SOURCE_TABLE    = dbutils.widgets.get("SOURCE_TABLE")

# COMMAND ----------

# Enum validation — fail fast on typos
ALLOWED_MODES = {"synthetic", "real_from_source", "real_from_table"}
if BASELINE_SOURCE not in ALLOWED_MODES:
    raise ValueError(
        f"Invalid baseline_source={BASELINE_SOURCE!r}. "
        f"Expected one of {sorted(ALLOWED_MODES)}. "
        f"Set the bundle var --var baseline_source=<value> or fix the target's "
        f"variables block in databricks.yml. (A common cause is a typo like "
        f"'syntethic' or a stray quote/space.)"
    )

# real_from_table also requires SOURCE_* widgets — fail fast here rather than
# letting the real-baseline notebook fail later
if BASELINE_SOURCE == "real_from_table":
    if not (SOURCE_CATALOG and SOURCE_SCHEMA and SOURCE_TABLE):
        raise ValueError(
            "baseline_source=real_from_table requires SOURCE_CATALOG, "
            "SOURCE_SCHEMA, SOURCE_TABLE widgets to be set. "
            f"Got SOURCE_CATALOG={SOURCE_CATALOG!r}, "
            f"SOURCE_SCHEMA={SOURCE_SCHEMA!r}, SOURCE_TABLE={SOURCE_TABLE!r}."
        )

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
if BASELINE_SOURCE == "real_from_table":
    print(f"  source table          = {SOURCE_CATALOG}.{SOURCE_SCHEMA}.{SOURCE_TABLE}")
elif BASELINE_SOURCE == "real_from_source":
    print(f"  source                = HUPA-UCM Mendeley dataset (downloaded fresh)")
else:
    print(f"  source                = synthetic generator (textbook phenotypes + AR(1))")
print(bar)
