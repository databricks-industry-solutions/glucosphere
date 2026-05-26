# Databricks notebook source
# MAGIC %md
# MAGIC # Real-baseline ingest (HUPA-UCM)
# MAGIC
# MAGIC Produces `${CATALOG_NAME}.${SCHEMA_NAME}.diabetes_data` — the single-table
# MAGIC data contract that `04_pseudo_data_modeling.py` reads.
# MAGIC Same schema as the synthetic path (see `01_synthetic_baseline.py`)
# MAGIC so downstream `04_*` / `05_*` / `06_*` work uniformly regardless of which
# MAGIC baseline path ran.
# MAGIC
# MAGIC Two ingest modes (selected by widget `BASELINE_SOURCE`):
# MAGIC
# MAGIC   - `from_source` — download HUPA-UCM zip from Mendeley → unpack into
# MAGIC     a UC volume → parse per-patient CSVs → write `diabetes_data`.
# MAGIC     Ported from `01_download_data.py` + `02_parseNcombine_processed_data.py`
# MAGIC     on `origin/hls-buildathon-main`.
# MAGIC   - `from_table` — copy from an existing UC table. Source resolved in this
# MAGIC     priority order (per #72 auto-detect, implemented in this notebook + the
# MAGIC     validate task):
# MAGIC     1. Explicit `SOURCE_CATALOG` / `SOURCE_SCHEMA` / `SOURCE_TABLE` widgets
# MAGIC        if all three set (deterministic; the e2e harness targets use this).
# MAGIC     2. Otherwise auto-detect against priority list under `CATALOG_NAME`:
# MAGIC        `glucosphere_dev.diabetes_data` → `glucosphere_from_source_e2e.diabetes_data`
# MAGIC        → `glucosphere_synth_e2e.diabetes_data`. First hit wins.
# MAGIC
# MAGIC The dispatch task in `glucosphere_full_setup` runs this notebook only when
# MAGIC `baseline_source != "synthetic"`. The synthetic path runs the other
# MAGIC notebook (`01_synthetic_baseline.py`).

# COMMAND ----------

# Widgets — all parameterized per codex C1 (no hardcoded sources)
dbutils.widgets.text("CATALOG_NAME", "glucosphere_catalog", "Catalog (target)")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere_dev", "Schema (target)")
dbutils.widgets.text("BASELINE_SOURCE", "from_source", "Mode: from_source | from_table")
dbutils.widgets.text(
    "DOWNLOAD_URL",
    # Mendeley public-API URL (stable). On request it 302-redirects to a fresh
    # signed S3 URL with a 5-min expiry. requests.get follows the redirect
    # automatically. The previously-hardcoded direct S3 URL (3hbcscwz44-1.zip)
    # was a stale presigned URL that returned AccessDenied — verified 2026-05-15.
    "https://data.mendeley.com/public-api/zip/3hbcscwz44/download/1",
    "HUPA-UCM Mendeley zip URL (from_source mode)",
)
dbutils.widgets.text(
    "DOWNLOAD_VOLUME",
    "raw_baseline",
    "UC Volume name for staging raw downloaded files (from_source mode)",
)
dbutils.widgets.text("SOURCE_CATALOG", "", "Source catalog (from_table mode only)")
dbutils.widgets.text("SOURCE_SCHEMA", "", "Source schema (from_table mode only)")
dbutils.widgets.text("SOURCE_TABLE", "", "Source table (from_table mode only)")

CATALOG_NAME    = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME     = dbutils.widgets.get("SCHEMA_NAME")
BASELINE_SOURCE = dbutils.widgets.get("BASELINE_SOURCE")
DOWNLOAD_URL    = dbutils.widgets.get("DOWNLOAD_URL")
DOWNLOAD_VOLUME = dbutils.widgets.get("DOWNLOAD_VOLUME")
SOURCE_CATALOG  = dbutils.widgets.get("SOURCE_CATALOG")
SOURCE_SCHEMA   = dbutils.widgets.get("SOURCE_SCHEMA")
SOURCE_TABLE    = dbutils.widgets.get("SOURCE_TABLE")

ALLOWED_MODES = {"from_source", "from_table"}
if BASELINE_SOURCE not in ALLOWED_MODES:
    raise ValueError(
        f"BASELINE_SOURCE={BASELINE_SOURCE!r} is not valid for this notebook. "
        f"Expected one of {sorted(ALLOWED_MODES)}. (For the synthetic path, "
        f"set baseline_source=synthetic at the bundle level — the dispatch will "
        f"route to 01_synthetic_baseline.py instead.)"
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
#   - from_table: handle inline here (CTAS from source → diabetes_data), then
#                      fall through; the source/download cells below are guarded
#                      so they only run when BASELINE_SOURCE == "from_source".
#   - from_source: pass through; download + parse cells handle the rest.
if BASELINE_SOURCE == "from_table":
    # #72 — prioritized source auto-detect:
    #   1. If SOURCE_CATALOG/SCHEMA/TABLE widgets are ALL explicitly set,
    #      use them verbatim (deterministic; this is what the e2e harness
    #      targets use, and what an operator gets when they override via
    #      `bundle deploy --var source_schema=...`).
    #   2. Otherwise iterate a fixed priority list under CATALOG_NAME and
    #      pick the first `<schema>.<table>` that exists. Priority is live
    #      production first, then real-data harness, then synth harness —
    #      so a from_table run "just works" against whatever the workspace
    #      has lying around.
    #   3. If none of the priority candidates exist, raise with the
    #      full candidate list so the operator knows what to populate.
    if SOURCE_CATALOG and SOURCE_SCHEMA and SOURCE_TABLE:
        source_fqn = f"{SOURCE_CATALOG}.{SOURCE_SCHEMA}.{SOURCE_TABLE}"
        print(f"[ingest:table] source = {source_fqn} (explicit widgets)")
    else:
        priority_candidates = [
            (f"{CATALOG_NAME}.glucosphere_dev.diabetes_data",                "live production"),
            (f"{CATALOG_NAME}.glucosphere_from_source_e2e.diabetes_data",    "real-data harness"),
            (f"{CATALOG_NAME}.glucosphere_synth_e2e.diabetes_data",          "synth harness"),
        ]
        source_fqn = None
        for fqn, label in priority_candidates:
            if spark.catalog.tableExists(fqn):
                source_fqn = fqn
                print(f"[ingest:table] source = {fqn} (auto-detected: {label})")
                break
        if source_fqn is None:
            tried = "\n  - ".join(f"{fqn} ({label})" for fqn, label in priority_candidates)
            raise ValueError(
                "from_table mode could not auto-detect a source table. "
                "Tried (in priority order):\n  - "
                f"{tried}\n"
                "Either populate one of those, or set SOURCE_CATALOG/SCHEMA/TABLE "
                "explicitly via bundle vars or widget UI."
            )
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
    # what `from_source` writes). If the source table is missing it,
    # writing unpartitioned still works and the validate check at the end
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

# from_source — download the HUPA-UCM zip from Mendeley and unpack to UC volume.
# Skipped when BASELINE_SOURCE == "from_table" (the table-mode dispatch above
# already wrote diabetes_data from an existing UC table).
if BASELINE_SOURCE == "from_source":
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
# Skipped when BASELINE_SOURCE == "from_table" (table-mode dispatch above
# already wrote diabetes_data from an existing UC table).
#
# Use an explicit schema (not inferSchema) so the types are deterministic at read
# time and match the contract checked by `validate_diabetes_data`. Without
# this, inferSchema picks DoubleType for `steps` (the contract wants LongType)
# and the check fails — caught 2026-05-16 during the first C.2 sandbox test.
if BASELINE_SOURCE == "from_source":
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
# MAGIC ## Build QC observability tables (baseline_timeseries + baseline_windows_metadata)
# MAGIC
# MAGIC Mirrors the windowed observability tables that `01_synthetic_baseline.py`
# MAGIC emits, so the two baseline paths produce a SYMMETRIC set of outputs:
# MAGIC
# MAGIC   - `diabetes_data` — the data contract for `04_*` (required)
# MAGIC   - `baseline_timeseries` — sliding 10-day windows per patient (stride 2 days)
# MAGIC   - `baseline_windows_metadata` — per-window aggregates (glucose mean / std / coverage)
# MAGIC
# MAGIC Foundation for model/data monitoring: concept-drift detection, per-window
# MAGIC data-quality monitoring, prediction-degradation diagnostics, retraining triggers,
# MAGIC cohort tracking. Runs for BOTH `from_source` and `from_table` modes
# MAGIC since both have written `diabetes_data` by this point.

# COMMAND ----------

# Build baseline_timeseries (10-day windows, stride 2 days, per patient) + baseline_windows_metadata
from pyspark.sql import functions as _F
from pyspark.sql.window import Window as _W

WINDOW_DAYS  = 10
STRIDE_DAYS  = 2
WINDOW_SECS  = WINDOW_DAYS  * 86400
STRIDE_SECS  = STRIDE_DAYS  * 86400

print(f"[windows] reading {target_table} to build observability tables")
diabetes_df = spark.table(target_table)

# Per-patient time range → number of windows that fit (need (span - WINDOW_DAYS) / STRIDE + 1 windows)
patient_ranges = (
    diabetes_df
    .groupBy("patient_id")
    .agg(
        _F.min("time").alias("t_first"),
        _F.max("time").alias("t_last"),
    )
    .withColumn("span_seconds", _F.unix_timestamp("t_last") - _F.unix_timestamp("t_first"))
    .withColumn(
        "n_windows",
        _F.greatest(
            _F.lit(0),
            ((_F.col("span_seconds") - _F.lit(WINDOW_SECS)) / _F.lit(STRIDE_SECS) + _F.lit(1)).cast("int"),
        ),
    )
)

# Explode each patient into one row per window
windows = (
    patient_ranges
    .withColumn("window_index", _F.explode(_F.expr("sequence(0, n_windows - 1)")))
    .withColumn(
        "window_start",
        _F.to_timestamp(_F.unix_timestamp("t_first") + _F.col("window_index") * _F.lit(STRIDE_SECS)),
    )
    .withColumn(
        "window_end",
        _F.to_timestamp(_F.unix_timestamp("t_first") + _F.col("window_index") * _F.lit(STRIDE_SECS) + _F.lit(WINDOW_SECS)),
    )
    .select("patient_id", "window_index", "window_start", "window_end")
)

# Assign stable global window_id (W000000 format). Order by (patient_id, window_index) for determinism.
windows_ranked = (
    windows
    .withColumn("global_idx", _F.row_number().over(_W.orderBy("patient_id", "window_index")) - _F.lit(1))
    .withColumn("window_id", _F.format_string("W%06d", _F.col("global_idx")))
    .drop("global_idx", "window_index")
)

# Join diabetes_data to windows — each reading may belong to multiple windows (stride < window).
# Note: is_non_anchor_15min is a synthetic-only flag (HUPA-UCM CSVs don't have it);
# emit as null for the real-data path so the column-set matches synthetic-mode parity.
baseline_ts = (
    diabetes_df.alias("d")
    .join(
        windows_ranked.alias("w"),
        (_F.col("d.patient_id") == _F.col("w.patient_id"))
        & (_F.col("d.time") >= _F.col("w.window_start"))
        & (_F.col("d.time") < _F.col("w.window_end")),
    )
    .select(
        _F.col("w.window_id"),
        _F.col("d.time"),
        _F.col("d.glucose"),
        _F.col("d.calories"),
        _F.col("d.heart_rate"),
        _F.col("d.steps"),
        _F.col("d.basal_rate"),
        _F.col("d.bolus_volume_delivered"),
        _F.col("d.carb_input"),
        _F.col("d.patient_id"),
        _F.lit(None).cast("boolean").alias("is_non_anchor_15min"),
    )
)

baseline_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries"
print(f"[windows] writing {baseline_table}")
(
    baseline_ts.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(baseline_table)
)
n_windows = baseline_ts.select("window_id").distinct().count()
n_baseline_rows = baseline_ts.count()
print(f"[windows] ✓ wrote {baseline_table}  ({n_baseline_rows:,} rows across {n_windows} windows)")

# COMMAND ----------

# Per-window aggregates → baseline_windows_metadata
meta = (
    baseline_ts
    .groupBy("window_id", "patient_id")
    .agg(
        _F.min("time").alias("start_time"),
        _F.max("time").alias("end_time"),
        _F.count("*").alias("n_readings"),
        _F.round(_F.mean("glucose"), 2).alias("glucose_mean"),
        _F.round(_F.stddev("glucose"), 2).alias("glucose_std"),
        _F.round(_F.mean(_F.col("glucose").isNotNull().cast("double")), 4).alias("glucose_coverage"),
    )
    .withColumn("tier", _F.lit("tier1"))
    .orderBy("window_id")
)

meta_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_windows_metadata"
print(f"[windows] writing {meta_table}")
(
    meta.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(meta_table)
)
print(f"[windows] ✓ wrote {meta_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check the diabetes_data table looks right
# MAGIC
# MAGIC Same check used by `01_synthetic_baseline.py` — confirms the
# MAGIC freshly-written `diabetes_data` matches the contract that `04_*` consumes
# MAGIC (required columns + reading interval + completeness).
# MAGIC
# MAGIC If this fails on Check 1 (required columns), the HUPA-UCM CSV headers
# MAGIC don't already match the contract — add a column-rename step in the
# MAGIC parse cell above (between `inferSchema` and the `patient_id`/`load_timestamp`
# MAGIC adds) and re-run.

# COMMAND ----------

# MAGIC %run ./utils/validate_diabetes_data
