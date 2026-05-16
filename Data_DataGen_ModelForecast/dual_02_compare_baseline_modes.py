# Databricks notebook source
# MAGIC %md
# MAGIC # Compare baseline modes — synthetic vs real_from_source vs real_from_table
# MAGIC
# MAGIC Standalone analytics notebook that runs AFTER you've populated `diabetes_data`
# MAGIC in multiple schemas (one per `baseline_source` mode). Reads each, computes
# MAGIC headline distribution stats side-by-side, and emits a comparison table.
# MAGIC
# MAGIC Use cases:
# MAGIC   - **Demo**: "look, our synthetic data approximates real HUPA-UCM glucose
# MAGIC     distributions within X%"
# MAGIC   - **Regression catcher**: if a future change drifts either side's
# MAGIC     distribution unexpectedly, the comparison surfaces it quickly
# MAGIC   - **Onboarding**: a new operator can see all three modes side-by-side
# MAGIC     and understand what each path produces
# MAGIC
# MAGIC NOT part of `glucosphere_full_setup` job — operators run this manually
# MAGIC after they have at least 2 modes populated. Set any mode's schema widget
# MAGIC to empty string ("") to skip that mode in the comparison.
# MAGIC
# MAGIC Stats computed per mode (whatever modes are configured):
# MAGIC   - `n_rows`, `n_patients`
# MAGIC   - Glucose: `mean`, `median`, `std`, p5/p25/p50/p75/p95
# MAGIC   - Glucose range buckets: hypoglycemia (<70), normal (70-180), hyperglycemia (>180) — as %
# MAGIC   - `nonnull_glucose_pct`
# MAGIC
# MAGIC Optional (best-effort if `scipy` available):
# MAGIC   - Pairwise Kolmogorov-Smirnov test for distribution similarity

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME",             "mmt_aws_usw2_catalog",    "Catalog containing the schemas to compare")
dbutils.widgets.text("SYNTHETIC_SCHEMA",         "glucosphere_dev",         "Schema where synthetic-mode diabetes_data lives (empty to skip)")
dbutils.widgets.text("REAL_FROM_SOURCE_SCHEMA",  "glucosphere_dev_test",    "Schema where real_from_source-mode diabetes_data lives (empty to skip)")
dbutils.widgets.text("REAL_FROM_TABLE_SCHEMA",   "glucosphere_dev_test_table", "Schema where real_from_table-mode diabetes_data lives (empty to skip)")
dbutils.widgets.text("WRITE_SUMMARY_TO_SCHEMA",  "",                        "Optional: write summary table to this schema (empty = print only)")

CATALOG_NAME           = dbutils.widgets.get("CATALOG_NAME")
SYNTHETIC_SCHEMA       = dbutils.widgets.get("SYNTHETIC_SCHEMA")
REAL_FROM_SOURCE_SCHEMA = dbutils.widgets.get("REAL_FROM_SOURCE_SCHEMA")
REAL_FROM_TABLE_SCHEMA = dbutils.widgets.get("REAL_FROM_TABLE_SCHEMA")
WRITE_SUMMARY_TO_SCHEMA = dbutils.widgets.get("WRITE_SUMMARY_TO_SCHEMA")

# Build mode → schema mapping, skipping any with empty schema
MODES = {}
if SYNTHETIC_SCHEMA:        MODES["synthetic"]        = SYNTHETIC_SCHEMA
if REAL_FROM_SOURCE_SCHEMA: MODES["real_from_source"] = REAL_FROM_SOURCE_SCHEMA
if REAL_FROM_TABLE_SCHEMA:  MODES["real_from_table"]  = REAL_FROM_TABLE_SCHEMA

if len(MODES) < 2:
    raise ValueError(
        f"Need at least 2 baseline modes configured to compare. Got {len(MODES)}: {list(MODES.keys())}. "
        f"Set the schema widgets for the modes you want to include (or non-empty to enable)."
    )

print(f"Comparing {len(MODES)} baseline modes: {list(MODES.keys())}")
for mode, schema in MODES.items():
    print(f"  {mode:18s} → {CATALOG_NAME}.{schema}.diabetes_data")

# COMMAND ----------

# Compute headline stats per mode
from pyspark.sql import functions as F

def headline_stats(catalog, schema):
    """Return a dict of comparable stats for diabetes_data in the given catalog.schema."""
    df = spark.table(f"{catalog}.{schema}.diabetes_data")

    # Single-pass aggregates
    agg = df.agg(
        F.count("*").alias("n_rows"),
        F.countDistinct("patient_id").alias("n_patients"),
        F.count("glucose").alias("n_glucose_nonnull"),
        F.round(F.mean("glucose"), 2).alias("glucose_mean"),
        F.round(F.stddev("glucose"), 2).alias("glucose_std"),
        F.round(F.min("glucose"), 2).alias("glucose_min"),
        F.round(F.max("glucose"), 2).alias("glucose_max"),
        F.round(F.expr("percentile_approx(glucose, 0.05)"), 2).alias("glucose_p05"),
        F.round(F.expr("percentile_approx(glucose, 0.25)"), 2).alias("glucose_p25"),
        F.round(F.expr("percentile_approx(glucose, 0.50)"), 2).alias("glucose_p50"),
        F.round(F.expr("percentile_approx(glucose, 0.75)"), 2).alias("glucose_p75"),
        F.round(F.expr("percentile_approx(glucose, 0.95)"), 2).alias("glucose_p95"),
        F.round(100.0 * F.sum((F.col("glucose") <  70).cast("int")) / F.count("glucose"), 2).alias("pct_hypoglycemia"),
        F.round(100.0 * F.sum(((F.col("glucose") >= 70) & (F.col("glucose") <= 180)).cast("int")) / F.count("glucose"), 2).alias("pct_normal"),
        F.round(100.0 * F.sum((F.col("glucose") > 180).cast("int")) / F.count("glucose"), 2).alias("pct_hyperglycemia"),
    ).first().asDict()

    agg["nonnull_glucose_pct"] = round(100.0 * agg["n_glucose_nonnull"] / agg["n_rows"], 2) if agg["n_rows"] else 0.0
    return agg

per_mode_stats = {}
for mode, schema in MODES.items():
    print(f"\n[stats] computing for mode={mode} schema={schema} ...")
    per_mode_stats[mode] = headline_stats(CATALOG_NAME, schema)
    print(f"[stats] ✓ {mode}: {per_mode_stats[mode]['n_rows']:,} rows, "
          f"{per_mode_stats[mode]['n_patients']} patients, glucose mean={per_mode_stats[mode]['glucose_mean']}")

# COMMAND ----------

# Print side-by-side comparison
metric_rows = [
    ("n_rows",             "rows"),
    ("n_patients",         "distinct patients"),
    ("nonnull_glucose_pct", "non-null glucose %"),
    ("glucose_mean",       "glucose mean (mg/dL)"),
    ("glucose_std",        "glucose std (mg/dL)"),
    ("glucose_min",        "glucose min (mg/dL)"),
    ("glucose_p05",        "glucose p05 (mg/dL)"),
    ("glucose_p25",        "glucose p25 (mg/dL)"),
    ("glucose_p50",        "glucose p50 / median (mg/dL)"),
    ("glucose_p75",        "glucose p75 (mg/dL)"),
    ("glucose_p95",        "glucose p95 (mg/dL)"),
    ("glucose_max",        "glucose max (mg/dL)"),
    ("pct_hypoglycemia",   "hypo % (<70)"),
    ("pct_normal",         "normal % (70-180)"),
    ("pct_hyperglycemia",  "hyper % (>180)"),
]

mode_names = list(MODES.keys())
col_width = 22
label_width = 32

bar = "=" * (label_width + col_width * len(mode_names) + len(mode_names) + 2)
print()
print(bar)
print(f"  BASELINE MODE COMPARISON ({CATALOG_NAME})")
print(bar)

# Header
header = f"  {'metric':<{label_width}}"
for m in mode_names:
    header += f" | {m:>{col_width-1}}"
print(header)
print(f"  {'-' * label_width}" + ("-" + "-" * col_width) * len(mode_names))

# Rows
for key, label in metric_rows:
    row = f"  {label:<{label_width}}"
    for m in mode_names:
        v = per_mode_stats[m].get(key, "?")
        if isinstance(v, float):
            row += f" | {v:>{col_width-1},.2f}"
        elif isinstance(v, int):
            row += f" | {v:>{col_width-1},}"
        else:
            row += f" | {str(v):>{col_width-1}}"
    print(row)
print(bar)

# COMMAND ----------

# Optional pairwise KS-test (best-effort; needs scipy + .toPandas() so size-bounded)
try:
    from scipy.stats import ks_2samp
    import itertools

    print()
    print("[ks-test] pairwise distribution similarity (scipy ks_2samp)")
    print("[ks-test] note: samples each mode at 50k rows max for tractability")

    samples = {}
    for mode, schema in MODES.items():
        df = spark.table(f"{CATALOG_NAME}.{schema}.diabetes_data")
        n = per_mode_stats[mode]["n_rows"]
        sample_frac = min(1.0, 50000.0 / max(n, 1))
        samples[mode] = (
            df.select("glucose")
              .where(F.col("glucose").isNotNull())
              .sample(False, sample_frac, seed=42)
              .toPandas()["glucose"]
              .values
        )
        print(f"[ks-test]   {mode}: sampled {len(samples[mode]):,} glucose values")

    print()
    for a, b in itertools.combinations(mode_names, 2):
        stat, pval = ks_2samp(samples[a], samples[b])
        verdict = "indistinguishable" if pval > 0.05 else "DIFFERENT"
        print(f"[ks-test] {a:18s} vs {b:18s}: D={stat:.4f}  p={pval:.4f}  → {verdict}")
except ImportError:
    print("[ks-test] scipy not available; skipping pairwise KS-test")
except Exception as e:
    print(f"[ks-test] failed (non-fatal): {e}")

# COMMAND ----------

# Optional: write summary table for archival / dashboards
if WRITE_SUMMARY_TO_SCHEMA:
    from datetime import datetime
    summary_rows = []
    run_ts = datetime.utcnow()
    for mode, stats in per_mode_stats.items():
        row = {"comparison_run_ts": run_ts, "mode": mode, "source_schema": MODES[mode]}
        row.update({k: v for k, v in stats.items()})
        summary_rows.append(row)

    summary_df = spark.createDataFrame(summary_rows)
    summary_table = f"{CATALOG_NAME}.{WRITE_SUMMARY_TO_SCHEMA}.baseline_comparison_summary"
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{WRITE_SUMMARY_TO_SCHEMA}")
    summary_df.write.format("delta").mode("append").saveAsTable(summary_table)
    print(f"\n[write] ✓ appended {len(summary_rows)} rows to {summary_table}")
else:
    print(f"\n[write] skipped (WRITE_SUMMARY_TO_SCHEMA is empty)")
