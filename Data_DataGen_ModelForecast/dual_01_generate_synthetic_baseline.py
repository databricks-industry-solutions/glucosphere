# Databricks notebook source
# MAGIC %md
# MAGIC # Generate Synthetic Baseline for CGM Pipeline
# MAGIC
# MAGIC Produces `diabetes_data`, `baseline_timeseries`, and `baseline_windows_metadata`
# MAGIC directly from synthetic generation — no external dataset download required.
# MAGIC Designed to produce output identical in schema to the HUPA-UCM pipeline.

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "mmt_aws_usw2_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere_dev", "Schema")

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")

print(f"Catalog: {CATALOG_NAME}.{SCHEMA_NAME}")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}")

# Grant the current user full access on the catalog and schema.
# Required in HIPAA CSP workspaces where catalogs default to isolation_mode=ISOLATED
# and schema-level privileges (especially CREATE MODEL for MLflow UC registration)
# are not inherited from catalog-level grants.
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

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pyspark.sql import functions as F
from pyspark.sql.types import *

np.random.seed(42)

# ── Config ───────────────────────────────────────────────────────────────────
N_PATIENTS    = 60          # Number of synthetic source patients
DAYS_PER_PAT  = 14          # Days of data per patient
CADENCE_MIN   = 5           # CGM reading every 5 minutes
START_DATE    = datetime(2025, 10, 1)

# Patient phenotype library — (glucose_mean, glucose_std, diabetes_type)
#
# Designed to populate all 4 strata recognized by dual_04's stratified sampler
# (dual_04 lines 422-428): hypo_prone (>15% readings <70), hyper_prone
# (>40% readings >180), normal_stable (>60% readings in [70,180]), mixed (else).
# Without coverage of all 4 strata, dual_04 fails at the plan-size assertion
# (verified empirically 2026-05-26 via synth_e2e run 891637990308752 task
# datagen_modeling run_id 767146243479756: 935/1000 pseudo patients because
# hypo + mixed strata were empty in the original 6-phenotype set).
PHENOTYPES = [
    (95,  15, "Type1"),   # well-controlled T1D            → normal_stable
    (140, 30, "Type1"),   # poorly-controlled T1D          → normal_stable/borderline-hyper
    (110, 20, "Type2"),   # well-controlled T2D            → normal_stable
    (160, 40, "Type2"),   # poorly-controlled T2D          → hyper_prone
    (100, 12, "Type1"),   # tight control                  → normal_stable
    (175, 45, "Type2"),   # high baseline                  → hyper_prone
    (75,  20, "Type1"),   # hypo-prone (added 2026-05-26)  → hypo_prone (>15% readings <70)
    (150, 70, "Type1"),   # brittle T1D (added 2026-05-26, tuned 2026-05-26b — was 135/55 which landed in normal_stable @ 66% > 60% threshold) → mixed (≈54% normal / ≈13% hypo / ≈33% hyper, none dominant)
]

# Meal schedule: (hour, carb_g_mean, bolus_mean)
MEALS = [
    (7.5,  45, 4.0),   # Breakfast
    (12.0, 60, 5.5),   # Lunch
    (18.5, 70, 6.0),   # Dinner
    (21.5, 20, 1.5),   # Late snack (50% probability)
]

# ── Generation helpers ────────────────────────────────────────────────────────

def glucose_meal_response(t_min, carbs, amplitude=1.0):
    """Gaussian glucose excursion after a meal (peaks ~45 min post-meal)."""
    peak_t = 45
    width  = 30
    return amplitude * carbs * 0.6 * np.exp(-0.5 * ((t_min - peak_t) / width) ** 2)

def generate_patient(patient_id, phenotype_idx):
    """Generate CADENCE_MIN-resolution CGM timeseries for one patient."""
    g_mean, g_std, _ = PHENOTYPES[phenotype_idx % len(PHENOTYPES)]
    n_steps = int(DAYS_PER_PAT * 24 * 60 / CADENCE_MIN)
    times   = [START_DATE + timedelta(minutes=i * CADENCE_MIN) for i in range(n_steps)]

    # Base glucose: AR(1) process around phenotype mean
    glucose = np.zeros(n_steps)
    glucose[0] = g_mean + np.random.normal(0, g_std * 0.5)
    for i in range(1, n_steps):
        glucose[i] = 0.97 * glucose[i-1] + 0.03 * g_mean + np.random.normal(0, 2.5)

    # Meal spikes
    carb_input            = np.zeros(n_steps)
    bolus_volume_delivered = np.zeros(n_steps)
    for day in range(DAYS_PER_PAT):
        day_offset_min = day * 24 * 60
        for meal_hour, carb_mean, bolus_mean in MEALS:
            if meal_hour > 20 and np.random.rand() < 0.5:
                continue
            meal_jitter    = np.random.normal(0, 20)   # ±20 min
            meal_min       = day_offset_min + int(meal_hour * 60 + meal_jitter)
            carbs          = max(5, np.random.normal(carb_mean, carb_mean * 0.15))
            bolus          = max(0.5, np.random.normal(bolus_mean, bolus_mean * 0.1))
            # Apply glucose excursion over next 90 min
            for j in range(int(90 / CADENCE_MIN)):
                idx = int(meal_min / CADENCE_MIN) + j
                if 0 <= idx < n_steps:
                    glucose[idx] += glucose_meal_response(j * CADENCE_MIN, carbs)
            # Record carbs and bolus at meal time
            idx_meal = int(meal_min / CADENCE_MIN)
            if 0 <= idx_meal < n_steps:
                carb_input[idx_meal]             += carbs
                bolus_volume_delivered[idx_meal] += bolus

    # Clip glucose to physiologically plausible range
    glucose = np.clip(glucose, 40, 400)

    # Physiological signals
    hour_of_day = np.array([t.hour + t.minute / 60 for t in times])
    heart_rate  = 60 + 20 * np.sin(2 * np.pi * (hour_of_day - 6) / 24) \
                     + np.random.normal(0, 5, n_steps)
    steps       = np.maximum(0,
                    500 * np.exp(-0.5 * ((hour_of_day - 14) / 3) ** 2)
                    + np.random.exponential(50, n_steps))
    calories    = steps * 0.04 + np.random.exponential(2, n_steps)
    basal_rate  = 0.8 + 0.4 * np.sin(2 * np.pi * (hour_of_day - 3) / 24) \
                     + np.random.normal(0, 0.05, n_steps)
    basal_rate  = np.clip(basal_rate, 0.3, 2.0)

    return pd.DataFrame({
        "patient_id":             [f"SYNTH{patient_id:04d}"] * n_steps,
        "time":                   times,
        "glucose":                glucose.round(1),
        "calories":               calories.round(2),
        "heart_rate":             heart_rate.round(1),
        "steps":                  steps.round(0).astype(int),
        "basal_rate":             basal_rate.round(3),
        "bolus_volume_delivered": bolus_volume_delivered.round(2),
        "carb_input":             carb_input.round(1),
        "is_non_anchor_15min":    [False] * n_steps,
        "load_timestamp":         [datetime.utcnow()] * n_steps,
    })

# ── Generate all patients ────────────────────────────────────────────────────

print(f"Generating {N_PATIENTS} synthetic patients × {DAYS_PER_PAT} days...")
dfs = []
for pid in range(N_PATIENTS):
    ptype = pid % len(PHENOTYPES)
    dfs.append(generate_patient(pid + 1, ptype))

all_pd = pd.concat(dfs, ignore_index=True)
print(f"Total rows: {len(all_pd):,}  |  Patients: {all_pd['patient_id'].nunique()}")

# ── Write diabetes_data ──────────────────────────────────────────────────────

schema = StructType([
    StructField("patient_id",             StringType(),    False),
    StructField("time",                   TimestampType(), False),
    StructField("glucose",                DoubleType(),    True),
    StructField("calories",               DoubleType(),    True),
    StructField("heart_rate",             DoubleType(),    True),
    StructField("steps",                  LongType(),      True),
    StructField("basal_rate",             DoubleType(),    True),
    StructField("bolus_volume_delivered", DoubleType(),    True),
    StructField("carb_input",             DoubleType(),    True),
    StructField("is_non_anchor_15min",    BooleanType(),   True),
    StructField("load_timestamp",         TimestampType(), True),
])

sdf = spark.createDataFrame(all_pd, schema=schema)
diabetes_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data"
sdf.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
         .partitionBy("patient_id").saveAsTable(diabetes_table)
print(f"✓ Wrote {diabetes_table}")

# ── Build baseline_timeseries windows (what notebook 03 outputs) ──────────────

WINDOW_DAYS = 10
STRIDE_DAYS = 2
window_secs = WINDOW_DAYS * 24 * 3600

print("\nBuilding baseline_timeseries windows...")
window_rows = []
all_pd["time"] = pd.to_datetime(all_pd["time"])
window_id = 0

for pid, grp in all_pd.groupby("patient_id"):
    grp = grp.sort_values("time").reset_index(drop=True)
    t0  = grp["time"].iloc[0]
    t_end = grp["time"].iloc[-1]
    cursor = t0
    while cursor + timedelta(days=WINDOW_DAYS) <= t_end:
        w_end = cursor + timedelta(days=WINDOW_DAYS)
        mask  = (grp["time"] >= cursor) & (grp["time"] < w_end)
        chunk = grp[mask].copy()
        chunk["window_id"] = f"W{window_id:06d}"
        window_rows.append(chunk)
        window_id += 1
        cursor   += timedelta(days=STRIDE_DAYS)

baseline_pd = pd.concat(window_rows, ignore_index=True)
cols = ["window_id", "time", "glucose", "calories", "heart_rate", "steps",
        "basal_rate", "bolus_volume_delivered", "carb_input", "patient_id",
        "is_non_anchor_15min"]
baseline_pd = baseline_pd[cols]

sdf_baseline = spark.createDataFrame(baseline_pd)
baseline_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries"
sdf_baseline.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
            .saveAsTable(baseline_table)
print(f"✓ Wrote {baseline_table}  ({baseline_pd['window_id'].nunique()} windows)")

# ── Build baseline_windows_metadata ──────────────────────────────────────────

meta_rows = []
for wid, grp in baseline_pd.groupby("window_id"):
    meta_rows.append({
        "window_id":  wid,
        "patient_id": grp["patient_id"].iloc[0],
        "start_time": grp["time"].min(),
        "end_time":   grp["time"].max(),
        "n_readings": len(grp),
        "glucose_mean":    round(grp["glucose"].mean(), 2),
        "glucose_std":     round(grp["glucose"].std(), 2),
        "glucose_coverage": round(grp["glucose"].notna().mean(), 4),
        "tier":       "tier1",
    })

meta_pd = pd.DataFrame(meta_rows)
sdf_meta = spark.createDataFrame(meta_pd)
meta_table = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_windows_metadata"
sdf_meta.write.format("delta").mode("overwrite").option("overwriteSchema", "true") \
        .saveAsTable(meta_table)
print(f"✓ Wrote {meta_table}")

print("\n" + "=" * 60)
print("Synthetic baseline generation complete.")
print(f"  diabetes_data:             {len(all_pd):,} rows")
print(f"  baseline_timeseries:       {len(baseline_pd):,} rows  ({baseline_pd['window_id'].nunique()} windows)")
print(f"  baseline_windows_metadata: {len(meta_pd)} windows")
print("=" * 60)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Check the diabetes_data table looks right
# MAGIC
# MAGIC Reads the freshly-written `diabetes_data` and confirms it has the columns,
# MAGIC reading interval, and completeness that `dual_04_CGM_PseudoGeneration_CleanData_Modeling.py`
# MAGIC expects. The same check runs at the end of the real-data path
# MAGIC (`01_ingest_real_baseline.py`) so synthetic and real outputs are
# MAGIC interchangeable. Raises `AssertionError` if anything is off.

# COMMAND ----------

# MAGIC %run ./utils/dual_validate_diabetes_data
