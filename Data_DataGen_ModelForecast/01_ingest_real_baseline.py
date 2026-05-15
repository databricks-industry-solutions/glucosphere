# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest Real Baseline for CGM Pipeline (STUB)
# MAGIC
# MAGIC Produces `diabetes_data` (the single-table data contract consumed by
# MAGIC `04_CGM_PseudoGeneration_CleanData_Modeling.py`) from a real CGM source —
# MAGIC either downloaded from the HUPA-UCM Mendeley dataset or read from an
# MAGIC existing UC table.
# MAGIC
# MAGIC **Status: STUB** — wired into `glucosphere_full_setup` via
# MAGIC `condition_task` so the job graph validates and deploys. Real ingest
# MAGIC logic lands in the next commit (plan's Commit C):
# MAGIC
# MAGIC   1. Widgets: `SOURCE_MODE` (download | table), `SOURCE_CATALOG`,
# MAGIC      `SOURCE_SCHEMA`, `SOURCE_TABLE`.
# MAGIC   2. download mode: pull HUPA-UCM ZIP from Mendeley, parse + merge into
# MAGIC      `diabetes_data` shape (mirrors original `02_parseNcombine_*`).
# MAGIC   3. table mode: SELECT * FROM ${source_catalog}.${source_schema}.${source_table}
# MAGIC      into `diabetes_data` (default source is `hls_glucosphere.cgm.diabetes_data`
# MAGIC      on fe-vm-hls-amer — the frozen reference catalog).
# MAGIC   4. Shared schema-contract preflight (codex C2) emitted as a separate
# MAGIC      cell so both this notebook and `01_generate_synthetic_baseline.py`
# MAGIC      can `%run` it for parity.

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "hls_amer_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere_dev", "Schema")

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")

print(f"[stub] 01_ingest_real_baseline target = {CATALOG_NAME}.{SCHEMA_NAME}")
print("[stub] real-baseline ingest not yet implemented — set baseline_source=synthetic for now")
raise NotImplementedError(
    "01_ingest_real_baseline.py is a stub. Set bundle var baseline_source=synthetic "
    "to run the synthetic ingest path until plan's Commit C lands the real implementation."
)
