# Databricks notebook source
# MAGIC %md
# MAGIC # Sanity summary: confirm diabetes_data is non-empty + print headline stats
# MAGIC
# MAGIC Runs after the baseline-ingest branches converge but BEFORE the heavy
# MAGIC downstream modeling (`04_*`) starts. If the baseline step somehow produced
# MAGIC an empty or unusable table, this task fails fast — saving ~45 minutes of
# MAGIC wasted modeling compute that would otherwise run on bad data.
# MAGIC
# MAGIC Checks:
# MAGIC
# MAGIC 1. `diabetes_data` table exists
# MAGIC 2. Row count > 0
# MAGIC 3. At least one distinct `patient_id`
# MAGIC 4. Glucose mean falls in a plausible CGM range (40-400 mg/dL) — catches
# MAGIC    unit-of-measure mistakes or wholesale-corrupt data

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "your_workspace_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME",  "glucosphere",  "Schema")

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")
target_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data"

# COMMAND ----------

# Check 1: table exists (raises AnalysisException if not)
try:
    df = spark.table(target_table)
except Exception as e:
    raise RuntimeError(
        f"[sanity] {target_table} does not exist. The baseline-ingest step "
        f"should have created it. Original error: {e}"
    ) from e

# Check 2 + 3: row + patient counts
from pyspark.sql import functions as F

stats = df.agg(
    F.count("*").alias("n_rows"),
    F.countDistinct("patient_id").alias("n_patients"),
    F.round(F.mean("glucose"), 2).alias("glucose_mean"),
    F.round(F.min("glucose"), 2).alias("glucose_min"),
    F.round(F.max("glucose"), 2).alias("glucose_max"),
).first()
n_rows = stats["n_rows"]
n_patients = stats["n_patients"]
glucose_mean = stats["glucose_mean"]
glucose_min = stats["glucose_min"]
glucose_max = stats["glucose_max"]

assert n_rows > 0, f"[sanity] {target_table} is EMPTY (0 rows). Baseline ingest must have failed silently — investigate before retrying."
assert n_patients > 0, f"[sanity] {target_table} has 0 distinct patient_ids. Schema or write went wrong."

# Check 4: glucose plausibility — CGM range typically 40-400 mg/dL
if not (40 <= glucose_mean <= 400):
    raise AssertionError(
        f"[sanity] glucose mean={glucose_mean} mg/dL is outside the plausible "
        f"CGM range [40, 400]. min={glucose_min}, max={glucose_max}. Possible "
        f"unit-of-measure mistake (mmol/L instead of mg/dL?) or wholesale "
        f"data corruption. Investigate before continuing to modeling."
    )

# COMMAND ----------

bar = "=" * 72
print(bar)
print(f"  glucosphere_full_setup — POST-BASELINE SANITY ✓")
print(bar)
print(f"  table              = {target_table}")
print(f"  rows               = {n_rows:,}")
print(f"  distinct patients  = {n_patients}")
print(f"  glucose mean       = {glucose_mean} mg/dL")
print(f"  glucose range      = [{glucose_min}, {glucose_max}] mg/dL")
print(bar)
