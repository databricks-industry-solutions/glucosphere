# Databricks notebook source
# MAGIC %md
# MAGIC # Check that the `diabetes_data` table looks right
# MAGIC
# MAGIC Reads `${CATALOG_NAME}.${SCHEMA_NAME}.diabetes_data` and confirms it
# MAGIC matches what `dual_04_CGM_PseudoGeneration_CleanData_Modeling.py` expects.
# MAGIC
# MAGIC `%run`-able from any baseline-generation notebook. The caller MUST set
# MAGIC `CATALOG_NAME` and `SCHEMA_NAME` as Python variables before `%run`.
# MAGIC
# MAGIC Optional caller overrides (all have sensible defaults):
# MAGIC
# MAGIC   - `TABLE_NAME`                  — table name (default `"diabetes_data"`)
# MAGIC   - `EXPECTED_CADENCE_SECONDS`    — expected reading interval (default `300` = 5 min)
# MAGIC   - `MIN_GLUCOSE_NONNULL`         — minimum non-null glucose ratio (default `0.95`)
# MAGIC   - `MIN_PATIENT_COVERAGE`        — minimum per-patient row coverage (default `0.90`)
# MAGIC
# MAGIC Raises `AssertionError` on any failed check; prints `✅ all 4 checks passed` on success.

# COMMAND ----------

# Confirm the caller set the catalog/schema variables
try:
    CATALOG_NAME, SCHEMA_NAME
except NameError as e:
    raise NameError(
        "validate_diabetes_data requires CATALOG_NAME and SCHEMA_NAME to be "
        "set in scope by the caller (e.g., via dbutils.widgets.get) before %run."
    ) from e

TABLE_NAME               = globals().get("TABLE_NAME", "diabetes_data")
EXPECTED_CADENCE_SECONDS = globals().get("EXPECTED_CADENCE_SECONDS", 300)
MIN_GLUCOSE_NONNULL      = globals().get("MIN_GLUCOSE_NONNULL", 0.95)
MIN_PATIENT_COVERAGE     = globals().get("MIN_PATIENT_COVERAGE", 0.90)

table_fqn = f"{CATALOG_NAME}.{SCHEMA_NAME}.{TABLE_NAME}"
print(f"[check] target = {table_fqn}")

# COMMAND ----------

# Check 1: required columns are present with the expected types
from pyspark.sql.types import StringType, TimestampType, DoubleType, LongType

REQUIRED_SCHEMA = {
    "patient_id":             StringType,
    "time":                   TimestampType,
    "glucose":                DoubleType,
    "steps":                  LongType,
    "basal_rate":             DoubleType,
    "bolus_volume_delivered": DoubleType,
    "carb_input":             DoubleType,
    "heart_rate":             DoubleType,
    "calories":               DoubleType,
}

df = spark.table(table_fqn)
actual_schema = {f.name: type(f.dataType) for f in df.schema.fields}

missing_cols = [c for c in REQUIRED_SCHEMA if c not in actual_schema]
type_mismatches = [
    f"{c}: expected {REQUIRED_SCHEMA[c].__name__}, got {actual_schema[c].__name__}"
    for c in REQUIRED_SCHEMA
    if c in actual_schema and actual_schema[c] is not REQUIRED_SCHEMA[c]
]

assert not missing_cols, f"[check 1] missing required columns: {missing_cols}"
assert not type_mismatches, f"[check 1] type mismatches: {type_mismatches}"
print(f"[check 1] ✓ all {len(REQUIRED_SCHEMA)} required columns present with correct types")

# COMMAND ----------

# Check 2: at least MIN_GLUCOSE_NONNULL fraction of rows have non-null glucose
from pyspark.sql import functions as F

stats = df.select(
    F.count("*").alias("n_total"),
    F.count("glucose").alias("n_glucose_nonnull"),
).first()
n_total = stats["n_total"]
n_glucose_nonnull = stats["n_glucose_nonnull"]

assert n_total > 0, "[check 2] table is empty"
nonnull_ratio = n_glucose_nonnull / n_total
assert nonnull_ratio >= MIN_GLUCOSE_NONNULL, (
    f"[check 2] glucose non-null ratio {nonnull_ratio:.3%} < threshold "
    f"{MIN_GLUCOSE_NONNULL:.0%} ({n_glucose_nonnull:,}/{n_total:,} non-null)"
)
print(f"[check 2] ✓ glucose non-null ratio = {nonnull_ratio:.3%} (≥ {MIN_GLUCOSE_NONNULL:.0%})")

# COMMAND ----------

# Check 3: readings come at roughly the expected interval (per-patient median gap)
from pyspark.sql.window import Window

w = Window.partitionBy("patient_id").orderBy("time")
deltas = (df
    .select("patient_id", "time")
    .withColumn("prev_time", F.lag("time").over(w))
    .withColumn("delta_sec", F.unix_timestamp("time") - F.unix_timestamp("prev_time"))
    .filter(F.col("delta_sec").isNotNull())
)
per_patient_median = (deltas
    .groupBy("patient_id")
    .agg(F.percentile_approx("delta_sec", 0.5).alias("median_delta_sec"))
)
max_median = per_patient_median.agg(F.max("median_delta_sec")).first()[0]
n_patients_off = per_patient_median.filter(
    F.col("median_delta_sec") > EXPECTED_CADENCE_SECONDS * 1.2
).count()

assert n_patients_off == 0, (
    f"[check 3] {n_patients_off} patients have median Δt > "
    f"{EXPECTED_CADENCE_SECONDS * 1.2:.0f}s (expected ~{EXPECTED_CADENCE_SECONDS}s reading interval; "
    f"max-median observed = {max_median}s)"
)
print(f"[check 3] ✓ reading interval — max per-patient median Δt = {max_median}s (expected ~{EXPECTED_CADENCE_SECONDS}s)")

# COMMAND ----------

# Check 4: each patient has at least MIN_PATIENT_COVERAGE fraction of expected rows
per_patient_stats = (df
    .groupBy("patient_id")
    .agg(
        F.count("*").alias("actual_rows"),
        F.min("time").alias("time_min"),
        F.max("time").alias("time_max"),
    )
    .withColumn("span_sec", F.unix_timestamp("time_max") - F.unix_timestamp("time_min"))
    .withColumn("expected_rows", (F.col("span_sec") / EXPECTED_CADENCE_SECONDS).cast("int") + 1)
    .withColumn("coverage", F.col("actual_rows") / F.col("expected_rows"))
)

low_coverage = per_patient_stats.filter(F.col("coverage") < MIN_PATIENT_COVERAGE)
n_low = low_coverage.count()

if n_low > 0:
    sample = low_coverage.orderBy("coverage").limit(5).collect()
    sample_str = "\n  ".join(
        f"{r['patient_id']}: {r['actual_rows']:,}/{r['expected_rows']:,} = {r['coverage']:.1%}"
        for r in sample
    )
    raise AssertionError(
        f"[check 4] {n_low} patients have coverage < {MIN_PATIENT_COVERAGE:.0%}. Sample:\n  {sample_str}"
    )

agg = per_patient_stats.agg(
    F.min("coverage").alias("min_cov"),
    F.avg("coverage").alias("avg_cov"),
    F.max("coverage").alias("max_cov"),
).first()
print(
    f"[check 4] ✓ per-patient row coverage min={agg['min_cov']:.1%} "
    f"avg={agg['avg_cov']:.1%} max={agg['max_cov']:.1%} (threshold ≥ {MIN_PATIENT_COVERAGE:.0%})"
)

# COMMAND ----------

print(f"[check] ✅ all 4 checks passed on {table_fqn}")
