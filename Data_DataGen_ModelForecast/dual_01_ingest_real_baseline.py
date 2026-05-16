# Databricks notebook source
# MAGIC %md
# MAGIC # Real-baseline ingest (HUPA-UCM)
# MAGIC
# MAGIC Produces `${CATALOG_NAME}.${SCHEMA_NAME}.diabetes_data` — the single-table
# MAGIC data contract that `04_CGM_PseudoGeneration_CleanData_Modeling.py` reads.
# MAGIC Same schema as the synthetic path (see `dual_01_generate_synthetic_baseline.py`)
# MAGIC so downstream `04_*` / `05_*` / `06_*` work uniformly regardless of which
# MAGIC baseline path ran.
# MAGIC
# MAGIC Two ingest modes (selected by widget `BASELINE_SOURCE`):
# MAGIC
# MAGIC   - `real_from_source` — download HUPA-UCM zip from Mendeley → unpack into
# MAGIC     a UC volume → parse per-patient CSVs → write `diabetes_data`.
# MAGIC     Ported from `01_download_data.py` + `02_parseNcombine_processed_data.py`
# MAGIC     on `origin/hls-buildathon-main`.
# MAGIC   - `real_from_table` — copy from an existing UC table (set via
# MAGIC     `SOURCE_CATALOG` / `SOURCE_SCHEMA` / `SOURCE_TABLE`).
# MAGIC     **NOT YET IMPLEMENTED — plan's Commit C.3.**
# MAGIC
# MAGIC The dispatch task in `glucosphere_full_setup` runs this notebook only when
# MAGIC `baseline_source != "synthetic"`. The synthetic path runs the other
# MAGIC notebook (`dual_01_generate_synthetic_baseline.py`).

# COMMAND ----------

# Widgets — all parameterized per codex C1 (no hardcoded sources)
dbutils.widgets.text("CATALOG_NAME", "hls_amer_catalog", "Catalog (target)")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere_dev", "Schema (target)")
dbutils.widgets.text("BASELINE_SOURCE", "real_from_source", "Mode: real_from_source | real_from_table")
dbutils.widgets.text(
    "DOWNLOAD_URL",
    # Mendeley public-API URL (stable). On request it 302-redirects to a fresh
    # signed S3 URL with a 5-min expiry. requests.get follows the redirect
    # automatically. The previously-hardcoded direct S3 URL (3hbcscwz44-1.zip)
    # was a stale presigned URL that returned AccessDenied — verified 2026-05-15.
    "https://data.mendeley.com/public-api/zip/3hbcscwz44/download/1",
    "HUPA-UCM Mendeley zip URL (real_from_source mode)",
)
dbutils.widgets.text(
    "DOWNLOAD_VOLUME",
    "raw_baseline",
    "UC Volume name for staging raw downloaded files (real_from_source mode)",
)
dbutils.widgets.text("SOURCE_CATALOG", "", "Source catalog (real_from_table mode only)")
dbutils.widgets.text("SOURCE_SCHEMA", "", "Source schema (real_from_table mode only)")
dbutils.widgets.text("SOURCE_TABLE", "", "Source table (real_from_table mode only)")

CATALOG_NAME    = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME     = dbutils.widgets.get("SCHEMA_NAME")
BASELINE_SOURCE = dbutils.widgets.get("BASELINE_SOURCE")
DOWNLOAD_URL    = dbutils.widgets.get("DOWNLOAD_URL")
DOWNLOAD_VOLUME = dbutils.widgets.get("DOWNLOAD_VOLUME")
SOURCE_CATALOG  = dbutils.widgets.get("SOURCE_CATALOG")
SOURCE_SCHEMA   = dbutils.widgets.get("SOURCE_SCHEMA")
SOURCE_TABLE    = dbutils.widgets.get("SOURCE_TABLE")

ALLOWED_MODES = {"real_from_source", "real_from_table"}
if BASELINE_SOURCE not in ALLOWED_MODES:
    raise ValueError(
        f"BASELINE_SOURCE={BASELINE_SOURCE!r} is not valid for this notebook. "
        f"Expected one of {sorted(ALLOWED_MODES)}. (For the synthetic path, "
        f"set baseline_source=synthetic at the bundle level — the dispatch will "
        f"route to dual_01_generate_synthetic_baseline.py instead.)"
    )

target_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data"
print(f"[ingest] target = {target_table}")
print(f"[ingest] mode   = {BASELINE_SOURCE}")

# COMMAND ----------

# Make sure the target schema exists + the running user has the grants
# downstream notebooks need
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

current_user = spark.sql("SELECT current_user()").collect()[0][0]
for stmt in [
    f"GRANT USE CATALOG ON CATALOG `{CATALOG_NAME}` TO `{current_user}`",
    f"GRANT USE SCHEMA ON SCHEMA `{CATALOG_NAME}`.`{SCHEMA_NAME}` TO `{current_user}`",
    f"GRANT CREATE TABLE ON SCHEMA `{CATALOG_NAME}`.`{SCHEMA_NAME}` TO `{current_user}`",
    f"GRANT CREATE VOLUME ON SCHEMA `{CATALOG_NAME}`.`{SCHEMA_NAME}` TO `{current_user}`",
    f"GRANT CREATE FUNCTION ON SCHEMA `{CATALOG_NAME}`.`{SCHEMA_NAME}` TO `{current_user}`",
    f"GRANT CREATE MODEL ON SCHEMA `{CATALOG_NAME}`.`{SCHEMA_NAME}` TO `{current_user}`",
]:
    spark.sql(stmt)
    print(f"  ✓ {stmt}")

# COMMAND ----------

# Mode dispatch:
#   - real_from_table: handle inline here (CTAS from source → diabetes_data), then
#                      fall through; the source/download cells below are guarded
#                      so they only run when BASELINE_SOURCE == "real_from_source".
#   - real_from_source: pass through; download + parse cells handle the rest.
if BASELINE_SOURCE == "real_from_table":
    # codex C1: parameterized source — fail fast if widgets aren't set.
    if not (SOURCE_CATALOG and SOURCE_SCHEMA and SOURCE_TABLE):
        raise ValueError(
            "real_from_table mode requires SOURCE_CATALOG, SOURCE_SCHEMA, "
            "SOURCE_TABLE widgets to be set. "
            f"Got SOURCE_CATALOG={SOURCE_CATALOG!r}, SOURCE_SCHEMA={SOURCE_SCHEMA!r}, "
            f"SOURCE_TABLE={SOURCE_TABLE!r}. Set them via job parameters or the "
            "widget UI before re-running."
        )
    source_fqn = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{SOURCE_TABLE}"
    print(f"[ingest:table] source = {source_fqn}")
    print(f"[ingest:table] target = {target_table}")

    df = spark.table(source_fqn)
    print(f"[ingest:table] columns = {df.columns}")

    n_rows = df.count()
    n_patients = (
        df.select("patient_id").distinct().count()
        if "patient_id" in df.columns
        else 0
    )
    print(f"[ingest:table] rows = {n_rows:,}  patients = {n_patients}")

    # Partition by patient_id when present (the contract requires it; matches
    # what `real_from_source` writes). If the source table is missing it,
    # writing unpartitioned still works and the dual_validate check at the end
    # will surface the missing-required-column violation clearly.
    writer = (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
    )
    if "patient_id" in df.columns:
        writer = writer.partitionBy("patient_id")
    writer.saveAsTable(target_table)
    print(f"[write] ✓ wrote {target_table}")

# COMMAND ----------

# real_from_source — download the HUPA-UCM zip from Mendeley and unpack to UC volume.
# Skipped when BASELINE_SOURCE == "real_from_table" (the table-mode dispatch above
# already wrote diabetes_data from an existing UC table).
if BASELINE_SOURCE == "real_from_source":
    import os
    import shutil
    import zipfile

    import requests

    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.{DOWNLOAD_VOLUME}")
    volume_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{DOWNLOAD_VOLUME}"
    temp_dir = "/tmp/hupa_ucm_download"
    os.makedirs(temp_dir, exist_ok=True)
    zip_path = os.path.join(temp_dir, "data.zip")

    print(f"[download] fetching {DOWNLOAD_URL}")
    response = requests.get(DOWNLOAD_URL, stream=True, timeout=300)
    response.raise_for_status()

    total_size = 0
    last_mb_printed = 0
    with open(zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                total_size += len(chunk)
                mb = total_size / (1024 * 1024)
                if mb - last_mb_printed >= 10:  # progress every 10 MB
                    print(f"  ... {mb:.0f} MB downloaded")
                    last_mb_printed = mb
    print(f"[download] ✓ {total_size / (1024 * 1024):.2f} MB → {zip_path}")

    print(f"[extract] → {volume_path}")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(volume_path)
    print(f"[extract] ✓ complete")

    shutil.rmtree(temp_dir)

# COMMAND ----------

# Parse per-patient CSVs (HUPA-UCM uses ';' delimiter) and combine into diabetes_data.
# Skipped when BASELINE_SOURCE == "real_from_table" (table-mode dispatch above
# already wrote diabetes_data from an existing UC table).
#
# Use an explicit schema (not inferSchema) so the types are deterministic at read
# time and match the contract checked by `dual_validate_diabetes_data`. Without
# this, inferSchema picks DoubleType for `steps` (the contract wants LongType)
# and the check fails — caught 2026-05-16 during the first C.2 sandbox test.
if BASELINE_SOURCE == "real_from_source":
    from pyspark.sql import functions as F
    from pyspark.sql.types import StructType, StructField, TimestampType, DoubleType, LongType

    # HUPA-UCM Preprocessed CSV header (verified 2026-05-16):
    #   time;glucose;calories;heart_rate;steps;basal_rate;bolus_volume_delivered;carb_input
    HUPA_CSV_SCHEMA = StructType([
        StructField("time",                   TimestampType(), True),
        StructField("glucose",                DoubleType(),    True),
        StructField("calories",               DoubleType(),    True),
        StructField("heart_rate",             DoubleType(),    True),
        StructField("steps",                  LongType(),      True),
        StructField("basal_rate",             DoubleType(),    True),
        StructField("bolus_volume_delivered", DoubleType(),    True),
        StructField("carb_input",             DoubleType(),    True),
    ])

    csv_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{DOWNLOAD_VOLUME}/HUPA-UCM Diabetes Dataset/Preprocessed/"
    print(f"[parse] reading CSVs from {csv_path}")

    df = (
        spark.read
        .option("header", "true")
        .option("delimiter", ";")
        .schema(HUPA_CSV_SCHEMA)
        .csv(csv_path + "*.csv")
    )

    # patient_id is encoded in the filename; load_timestamp is when this run wrote the row
    df = (
        df
        .withColumn("patient_id", F.regexp_extract(F.col("_metadata.file_path"), "([^/]+)\\.csv$", 1))
        .withColumn("load_timestamp", F.current_timestamp())
    )

    n_rows = df.count()
    n_patients = df.select("patient_id").distinct().count()
    print(f"[parse] rows = {n_rows:,}  patients = {n_patients}  columns = {df.columns}")

    print(f"[write] → {target_table}")
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .partitionBy("patient_id")
        .saveAsTable(target_table)
    )
    print(f"[write] ✓ wrote {target_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check the diabetes_data table looks right
# MAGIC
# MAGIC Same check used by `dual_01_generate_synthetic_baseline.py` — confirms the
# MAGIC freshly-written `diabetes_data` matches the contract that `04_*` consumes
# MAGIC (required columns + reading interval + completeness).
# MAGIC
# MAGIC If this fails on Check 1 (required columns), the HUPA-UCM CSV headers
# MAGIC don't already match the contract — add a column-rename step in the
# MAGIC parse cell above (between `inferSchema` and the `patient_id`/`load_timestamp`
# MAGIC adds) and re-run.

# COMMAND ----------

# MAGIC %run ./utils/dual_validate_diabetes_data
