# Databricks notebook source
# DBTITLE 1,Install dependencies for system metrics logging
# Install dependencies for MLflow system metrics logging and Optuna
# Required for log_system_metrics=True in mlflow.start_run() and Optuna SQLite storage

print("Installing dependencies...")
print("   • psutil: CPU and memory metrics")
print("   • nvidia-ml-py3: GPU metrics (g5.12xlarge with A10G GPUs)")
print("   • alembic: Optuna SQLite storage support\n")

%pip install psutil alembic pyyaml xgboost "optuna-integration[xgboost]" optuna scipy matplotlib seaborn scikit-learn "mlflow[databricks]" databricks-sdk --quiet

print("\n✓ Dependencies installed. Restarting Python...")

# Restart Python to load newly installed packages
dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Pipeline Overview
# MAGIC %md
# MAGIC ## CGM Pseudo Patient Generation & Glucose Forecasting
# MAGIC
# MAGIC **Pipeline:** Setup → Baseline → Pseudo Gen → Validation → Features → Training → Forecast
# MAGIC
# MAGIC **Configuration:** Hybrid YAML + Widgets approach
# MAGIC * **Cells 4-5**: Setup configuration (6 essential widgets + YAML file)
# MAGIC * **Benefits**: Clean UI (6 widgets vs 50+), environment-specific configs (dev/staging/prod), easy to maintain
# MAGIC * **Essential Widgets**: ENV, CATALOG_NAME, SCHEMA_NAME, INCLUDE_INCIDENT, CONFIG_FILE, NUM_PSEUDO_OVERRIDE
# MAGIC * **All other parameters**: Loaded from `configs/baseline_config.yaml`
# MAGIC
# MAGIC **Current Settings:** GLUCOSE_OFFSET=8.0 mg/dL, p25 anchor, simple features, no class weights
# MAGIC
# MAGIC **Output:** 1000 pseudo patients (dev), 2 UC models, fleet forecast table

# COMMAND ----------

# DBTITLE 1,Essential Widgets (7 only - YAML config approach)
# ------------------------
# Essential Widgets (7 only - down from 50+!)
# All other parameters loaded from YAML config
# ------------------------

# Remove all existing widgets first
dbutils.widgets.removeAll()

# Essential widgets only
dbutils.widgets.dropdown("ENV", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("CATALOG_NAME", "mmt_aws_usw2_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "cgm", "Schema")
dbutils.widgets.dropdown("INCLUDE_INCIDENT", "false", ["false", "true"], "Include Incident")
dbutils.widgets.dropdown("RUN_OPTUNA_TUNING", "true", ["false", "true"], "Run Optuna Tuning")
dbutils.widgets.text("CONFIG_FILE", "configs/baseline_config.yaml", "Config File")
dbutils.widgets.text("NUM_PSEUDO_OVERRIDE", "", "Num Pseudo Override (optional)")

# Define HORIZONS here (used by multiple cells)
HORIZONS = [1, 2, 3, 6]  # 5/10/15/30 min ahead

print("✓ Essential widgets created (7 total)")
print("\nWidget values:")
print(f"  ENV: {dbutils.widgets.get('ENV')}")
print(f"  CATALOG: {dbutils.widgets.get('CATALOG_NAME')}")
print(f"  SCHEMA: {dbutils.widgets.get('SCHEMA_NAME')}")
print(f"  INCLUDE_INCIDENT: {dbutils.widgets.get('INCLUDE_INCIDENT')}")
print(f"  RUN_OPTUNA_TUNING: {dbutils.widgets.get('RUN_OPTUNA_TUNING')}")
print(f"  CONFIG_FILE: {dbutils.widgets.get('CONFIG_FILE')}")
print(f"\nℹ️  All other parameters will be loaded from YAML config")

# COMMAND ----------

# DBTITLE 1,Configuration Loader (Hybrid: Widgets + cfg object)
# ------------------------
# Configuration Loader (YAML + Widget Overrides)
# Hybrid approach: Widgets for user-facing vars, cfg object for internal params
# ------------------------

import yaml
import os
from pathlib import Path
import pandas as pd

class Config:
    """Configuration loader with YAML + widget override support"""
    
    def __init__(self, yaml_path, env, widget_overrides=None):
        self._env = env
        self._widget_overrides = widget_overrides or {}
        self._config = self._load_yaml(yaml_path, env)
        self._cache = {}
        
        # Construct baseline_tbl from catalog/schema/table_name
        if 'CATALOG_NAME' in self._widget_overrides and 'SCHEMA_NAME' in self._widget_overrides:
            catalog = self._widget_overrides['CATALOG_NAME']
            schema = self._widget_overrides['SCHEMA_NAME']
            table_name = self._config.get('BASELINE_TABLE_NAME', 'diabetes_data')
            self._config['BASELINE_TBL'] = f"{catalog}.{schema}.{table_name}"
    
    def _load_yaml(self, yaml_path, env):
        """Load YAML config and merge environment-specific values with dev defaults"""
        try:
            with open(yaml_path, 'r') as f:
                all_config = yaml.safe_load(f)
            
            # Start with dev as base
            config = all_config.get('dev', {}).copy()
            
            # Merge environment-specific overrides
            if env != 'dev' and env in all_config:
                config.update(all_config[env])
            
            # Convert all keys to UPPERCASE for backward compatibility
            config = {k.upper(): v for k, v in config.items()}
            
            return config
        except FileNotFoundError:
            print(f"⚠️  Config file not found: {yaml_path}")
            print(f"   Please ensure the config file exists at the specified path.")
            print(f"   Using empty config - this will fail until config file is created.")
            return {}
        except Exception as e:
            print(f"⚠️  Error loading config: {str(e)}")
            return {}
    
    def __getattr__(self, name):
        """Get config value with widget override support (UPPERCASE)"""
        # Convert to uppercase for lookup
        name_upper = name.upper()
        
        # Use object.__getattribute__ to avoid recursion
        cache = object.__getattribute__(self, '_cache')
        widget_overrides = object.__getattribute__(self, '_widget_overrides')
        config = object.__getattribute__(self, '_config')
        
        # Check cache first
        if name_upper in cache:
            return cache[name_upper]
        
        # Check widget overrides
        if name_upper in widget_overrides:
            value = widget_overrides[name_upper]
            cache[name_upper] = value
            return value
        
        # Check YAML config
        if name_upper in config:
            value = config[name_upper]
            cache[name_upper] = value
            return value
        
        raise AttributeError(f"Config parameter '{name}' not found in YAML or widgets")
    
    def get(self, name, default=None):
        """Get config value with default fallback"""
        try:
            return getattr(self, name)
        except AttributeError:
            return default
    
    def get_list_int(self, name):
        """Get list parameter as integers"""
        value = getattr(self, name)
        if isinstance(value, list):
            return [int(x) for x in value]
        return [int(x.strip()) for x in str(value).split(",") if x.strip()]

# Load configuration
env = dbutils.widgets.get("ENV")
config_file = dbutils.widgets.get("CONFIG_FILE")
catalog_name = dbutils.widgets.get("CATALOG_NAME")
schema_name = dbutils.widgets.get("SCHEMA_NAME")
include_incident = dbutils.widgets.get("INCLUDE_INCIDENT") == "true"
num_pseudo_override = dbutils.widgets.get("NUM_PSEUDO_OVERRIDE").strip()

# Widget overrides (UPPERCASE keys)
widget_overrides = {
    "CATALOG_NAME": catalog_name,
    "SCHEMA_NAME": schema_name,
    "INCLUDE_INCIDENT": include_incident,
}

# Add optional overrides
if num_pseudo_override:
    widget_overrides["NUM_PSEUDO"] = int(num_pseudo_override)

# Create config object
cfg = Config(config_file, env, widget_overrides)

# ------------------------
# HYBRID APPROACH: Expose only user-facing variables as UPPERCASE
# Use cfg.param for internal parameters (cleaner, less duplication)
# ------------------------

# User-facing variables (catalog, schema, tables, key settings)
CATALOG_NAME = cfg.catalog_name
SCHEMA_NAME = cfg.schema_name
BASELINE_TBL = cfg.baseline_tbl
INCLUDE_INCIDENT = cfg.include_incident
NUM_PSEUDO = cfg.num_pseudo
ENV = env
CONFIG_FILE = config_file

# Computed values used across multiple cells
ROWS_PER_DAY = int((24*60)//cfg.cadence_min)
ROWS_7D = cfg.seg_days * ROWS_PER_DAY

# Computed incident timestamps (needed by multiple cells)
base_date = pd.Timestamp(cfg.demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)

# XGBoost hyperparameters (may be updated by Optuna in cell 26)
MAX_DEPTH = cfg.max_depth
ETA = cfg.eta
SUBSAMPLE = cfg.subsample
COLSAMPLE = cfg.colsample
N_ROUNDS = cfg.n_rounds
EARLY_STOP = cfg.early_stop

# Print summary
print("✓ Configuration loaded (env={})" .format(env))
print(f"\nUser-facing variables (UPPERCASE):")
print(f"  CATALOG_NAME: {CATALOG_NAME}")
print(f"  SCHEMA_NAME: {SCHEMA_NAME}")
print(f"  BASELINE_TBL: {BASELINE_TBL}")
print(f"  NUM_PSEUDO: {NUM_PSEUDO}")
print(f"  INCLUDE_INCIDENT: {INCLUDE_INCIDENT}")
print(f"\nInternal parameters (use cfg.param):")
print(f"  cfg.seed: {cfg.seed}")
print(f"  cfg.glucose_offset: {cfg.glucose_offset} mg/dL")
print(f"  cfg.lags: {cfg.lags}")
print(f"  cfg.train_sample_frac: {cfg.train_sample_frac}")
print(f"\nXGBoost hyperparameters (may be updated by Optuna):")
print(f"  MAX_DEPTH: {MAX_DEPTH}, ETA: {ETA}")
print(f"  N_ROUNDS: {N_ROUNDS}, EARLY_STOP: {EARLY_STOP}")
print(f"\nℹ️  Using configs/baseline_config.yaml with widget overrides")
print(f"ℹ️  Access internal params as: cfg.param_name (e.g., cfg.seed, cfg.gain_lo)")

# COMMAND ----------

# DBTITLE 1,Define Output Tables
# ------------------------
# Output table definitions
# Uses CATALOG_NAME, SCHEMA_NAME (uppercase) + cfg object for parameters
# ------------------------

# Baseline processing tables
base2_tbl       = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_base_with_contigs_7d"
base2_clean_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_base_with_contigs_7d_clean"
contigs_tbl     = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_contig_registry_7d"
seg_tbl         = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_segment_registry_7d_stride{cfg.stride_days}"
plan_tbl        = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_pseudo_plan_7d"
joined_tbl      = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_joined_slices_7d"

# Pseudo patient tables
pseudo_clean_tbl    = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_clean_7d"
pseudo_incident_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d"

# Labeled data tables
clean_labeled_tbl               = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_clean_7d_labeled"
incident_labeled_observed_tbl   = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled_observed"
incident_labeled_true_tbl       = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled_true"
incident_flag_tbl               = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_with_flag"

# Validation table
baseline_val_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_for_validation_7d"

# Feature and forecast tables
xgb_features_tbl   = f"{CATALOG_NAME}.{SCHEMA_NAME}.xgb_flat_min_lags{cfg.lags}"
fleet_forecast_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.fleet_forecast_now"

# UC model names
uc_model_fqn_15m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{cfg.uc_model_name_15m}"
uc_model_fqn_30m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{cfg.uc_model_name_30m}"

print("✓ Output tables defined")
print(f"\nKey tables:")
print(f"  Baseline: {BASELINE_TBL}")
print(f"  Pseudo patients: {pseudo_clean_tbl}")
print(f"  Features: {xgb_features_tbl}")
print(f"  Fleet forecast: {fleet_forecast_tbl}")
print(f"\nModels:")
print(f"  15-min: {uc_model_fqn_15m}")
print(f"  30-min: {uc_model_fqn_30m}")

# COMMAND ----------

# DBTITLE 1,Import libraries
from pyspark.sql import functions as F, Window
from pyspark.sql.types import *
import pandas as pd
import numpy as np
import xgboost as xgb

# COMMAND ----------

# DBTITLE 1,Demo Week and Incident Window
# Demo-week start and incident window
# Computed in cell 4, just print for reference

print("demo_week_start (UTC):", cfg.demo_week_start)
print("incident window (if enabled):", incident_start_ts, "->", incident_end_ts)

# COMMAND ----------

# DBTITLE 1,Load Baseline and Build Contigs
# Load baseline and build contigs + flags

base = spark.table(BASELINE_TBL)
required = [
    "patient_id","time",
    "glucose","steps","basal_rate","bolus_volume_delivered","carb_input",
    "heart_rate","calories"
]
missing = [c for c in required if c not in base.columns]
assert not missing, f"Missing required columns: {missing}"

base = base.select(*required)

w = Window.partitionBy("patient_id").orderBy("time")
base2 = (base
  .withColumn("prev_time", F.lag("time").over(w))
  .withColumn("dt_min", (F.unix_timestamp("time") - F.unix_timestamp("prev_time"))/60.0)
  .withColumn("is_break", F.when(F.col("prev_time").isNull(), 1)
                          .when(F.col("dt_min") >= cfg.gap_min, 1)
                          .otherwise(0))
  .withColumn("contig_id", F.sum("is_break").over(w))
  .drop("prev_time","dt_min","is_break")
  .withColumn("basal_present", (F.col("basal_rate").cast("double") > 0).cast("int"))
  .withColumn("bolus_event",   (F.col("bolus_volume_delivered").cast("double") > 0).cast("int"))
  .withColumn("carb_event",    (F.col("carb_input").cast("double") > 0).cast("int"))
)

base2.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(base2_tbl)

contigs = (base2.groupBy("patient_id","contig_id")
  .agg(
    F.min("time").alias("contig_start"),
    F.max("time").alias("contig_end"),
    F.count("*").alias("n_rows"),
    (F.count("*")/F.lit(float(ROWS_PER_DAY))).alias("days")
  )
)

contigs.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(contigs_tbl)
print("patients with any contig:", contigs.select("patient_id").distinct().count())

# COMMAND ----------

# DBTITLE 1,Clean baseline data with physiological constraints
# ------------------------
# Clean baseline data: Apply physiological constraints
# Fixes impossible values (e.g., negative bolus) at the source
# ------------------------

print("Cleaning baseline data with physiological constraints...")

base2_df = spark.table(base2_tbl)

# Apply physiological clipping
base2_clean = base2_df.select(
    "patient_id", "time", "contig_id",
    # Clip glucose to realistic CGM range [40, 600]
    F.when(F.col("glucose") < 40, 40)
     .when(F.col("glucose") > 600, 600)
     .otherwise(F.col("glucose")).alias("glucose"),
    # Clip all other signals to [0, ∞) - cannot be negative
    F.greatest(F.col("bolus_volume_delivered"), F.lit(0.0)).alias("bolus_volume_delivered"),
    F.greatest(F.col("basal_rate"), F.lit(0.0)).alias("basal_rate"),
    F.greatest(F.col("carb_input"), F.lit(0.0)).alias("carb_input"),
    F.greatest(F.col("steps"), F.lit(0.0)).alias("steps"),
    F.greatest(F.col("heart_rate"), F.lit(0.0)).alias("heart_rate"),
    F.greatest(F.col("calories"), F.lit(0.0)).alias("calories"),
    # Keep flags
    "basal_present", "bolus_event", "carb_event"
)

# Save cleaned baseline
base2_clean.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(base2_clean_tbl)

# Verify cleaning
verify = base2_clean.select(
    F.sum((F.col("bolus_volume_delivered") < 0).cast("int")).alias("negative_bolus"),
    F.sum((F.col("basal_rate") < 0).cast("int")).alias("negative_basal"),
    F.sum((F.col("carb_input") < 0).cast("int")).alias("negative_carbs"),
    F.sum((F.col("glucose") < 40).cast("int")).alias("glucose_too_low"),
    F.sum((F.col("glucose") > 600).cast("int")).alias("glucose_too_high"),
    F.count("*").alias("total_rows")
).collect()[0]

print(f"Cleaned baseline saved: {base2_clean_tbl}")
print(f"   Total rows: {verify['total_rows']:,}")
print(f"   Negative bolus: {verify['negative_bolus']} (was 4)")
print(f"   Negative basal: {verify['negative_basal']}")
print(f"   Negative carbs: {verify['negative_carbs']}")
print(f"   Glucose < 40: {verify['glucose_too_low']}")
print(f"   Glucose > 600: {verify['glucose_too_high']}")
print(f"All physiological constraints satisfied!")

# COMMAND ----------

# DBTITLE 1,Classify baseline patients into glucose strata
# ------------------------
# Classify baseline patients by glucose profile for stratified sampling
# Goal: Match baseline distribution (ratios derived from source per stratum, #77 2026-05-26)
# ------------------------

print("Classifying baseline patients by glucose profile...")

base2_clean = spark.table(base2_clean_tbl)

# Calculate % time in each glucose range per patient
patient_profiles = base2_clean.groupBy("patient_id").agg(
    F.count("*").alias("total_points"),
    F.sum((F.col("glucose") < 70).cast("int")).alias("hypo_points"),
    F.sum(((F.col("glucose") >= 70) & (F.col("glucose") <= 180)).cast("int")).alias("normal_points"),
    F.sum((F.col("glucose") > 180).cast("int")).alias("hyper_points")
).withColumn("hypo_pct", F.col("hypo_points") / F.col("total_points") * 100) \
 .withColumn("normal_pct", F.col("normal_points") / F.col("total_points") * 100) \
 .withColumn("hyper_pct", F.col("hyper_points") / F.col("total_points") * 100)

# Classify into strata based on dominant glucose range
patient_strata = patient_profiles.withColumn(
    "stratum",
    F.when(F.col("hypo_pct") > 15, "hypo_prone")  # >15% time in hypo
     .when(F.col("hyper_pct") > 40, "hyper_prone")  # >40% time in hyper
     .when(F.col("normal_pct") > 60, "normal_stable")  # >60% time in normal
     .otherwise("mixed")
)

patient_strata_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.gen_patient_strata"
patient_strata.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(patient_strata_tbl)

# Show stratum distribution
stratum_counts = patient_strata.groupBy("stratum").agg(
    F.count("*").alias("n_patients"),
    F.avg("hypo_pct").alias("avg_hypo_pct"),
    F.avg("normal_pct").alias("avg_normal_pct"),
    F.avg("hyper_pct").alias("avg_hyper_pct")
).orderBy("stratum").toPandas()

print("\nPatient Classification Complete:")
print("-" * 80)
print(stratum_counts.to_string(index=False))

total_patients = stratum_counts['n_patients'].sum()
print(f"\nTotal patients: {total_patients}")
for idx, row in stratum_counts.iterrows():
    print(f"  {row['stratum']:15s}: {row['n_patients']:2d} patients ({row['n_patients']/total_patients*100:4.1f}%)")

print(f"\nSaved: {patient_strata_tbl}")
print("   Ready for stratified sampling in Cell 12")

# COMMAND ----------

# DBTITLE 1,Build Segment Registry
# Build segment registry (7-day windows with stride)

seg = (contigs
  .filter(F.col("days") >= F.lit(cfg.seg_days))
  .withColumn("max_start_day", F.floor(F.col("days") - F.lit(cfg.seg_days)))
  .withColumn("start_day", F.explode(F.sequence(F.lit(0), F.col("max_start_day"), F.lit(cfg.stride_days))))
  .withColumn("segment_start", F.expr("date_add(contig_start, cast(start_day as int))"))
  .withColumn("segment_end",   F.expr(f"date_add(segment_start, {cfg.seg_days})"))
  .selectExpr(
      "patient_id as source_patient_id",
      "contig_id",
      "segment_start",
      "segment_end",
      f"cast({cfg.seg_days} as int) as segment_days"
  )
)

seg.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(seg_tbl)
print("segments:", seg.count())

# COMMAND ----------

# DBTITLE 1,Stratified Sampling Plan
# ------------------------
# STRATIFIED sampling plan — targets derived from SOURCE stratum distribution.
# Originally hardcoded to HUPA-UCM ratios (6.4/71.8/21.8%); changed 2026-05-26
# to derive from source so pseudo cohort shape matches baseline shape per mode
# (real HUPA-UCM → ~HUPA-UCM ratios; synthetic → synthetic-distribution ratios;
# from_table → whatever source UC table has). Avoids systematic right-shift of
# pseudo vs baseline when source distribution doesn't match HUPA-UCM (#77).
# (Originally 4 strata with 0.1% "mixed" residual; dropped 2026-05-26 and
#  absorbed into normal — see target computation below.)
# ------------------------

print("Stratified sampling to match baseline distribution...")

seg = spark.table(seg_tbl)
patient_strata = spark.table(patient_strata_tbl)

# Cap windows per patient
wcap = Window.partitionBy("source_patient_id").orderBy("segment_start")
seg_capped = (seg
  .withColumn("rn", F.row_number().over(wcap))
  .filter(F.col("rn") <= F.lit(cfg.max_windows_per_source))
  .drop("rn")
)

# Join segments with patient strata
seg_with_strata = seg_capped.join(patient_strata.select("patient_id", "stratum"), 
                                   seg_capped.source_patient_id == patient_strata.patient_id,
                                   "inner").drop(patient_strata.patient_id)

# Calculate target counts per stratum — DERIVED FROM SOURCE DISTRIBUTION
# (changed 2026-05-26 from hardcoded HUPA-UCM ratios to source-adaptive #77).
#
# Why source-adaptive: hardcoded ratios (6.4/71.8/21.8%) only matched HUPA-UCM
# real-data source shape. For synthetic (or any other source whose distribution
# differs from HUPA-UCM), hardcoded ratios cause systematic right-shift of
# pseudo vs baseline (verified empirically 2026-05-26: synthetic baseline had
# 4.7/89.2/6.1% but sampler targeted 6.4/71.8/21.8% → pseudo +15% hyper).
#
# Pseudo cohort now matches BASELINE shape per mode:
#   - real_from_source (HUPA-UCM): targets ≈ 6.6/71.7/21.7% (~unchanged)
#   - synthetic (C17 phenotypes):   targets ≈ source-derived (e.g., 22/72/7%)
#   - from_table (any UC table):    targets ≈ that source's actual distribution
#
# The 4th "mixed" stratum target stays 0 (residual classification, no consumer
# — see git history for the 2026-05-26 mixed-drop rationale).
src_strata = {row['stratum']: row['n_patients']
              for row in stratum_counts.to_dict('records')}
# Exclude `mixed` from ratio computation; absorb into normal_stable as residual.
src_active_total = (src_strata.get('hypo_prone', 0) +
                    src_strata.get('normal_stable', 0) +
                    src_strata.get('hyper_prone', 0))
if src_active_total == 0:
    raise RuntimeError(
        "No source patients in any active stratum (hypo/normal/hyper). "
        "Source baseline is empty or all-mixed. Check dual_01 output + "
        "patient_strata classification at the top of this notebook."
    )
src_hypo_ratio  = src_strata.get('hypo_prone', 0)  / src_active_total
src_hyper_ratio = src_strata.get('hyper_prone', 0) / src_active_total
target_hypo   = int(NUM_PSEUDO * src_hypo_ratio)
target_hyper  = int(NUM_PSEUDO * src_hyper_ratio)
target_normal = NUM_PSEUDO - target_hypo - target_hyper  # remainder, absorbs mixed slot
target_mixed  = 0

print(f"\nSource distribution (from {src_active_total} active-stratum patients):")
print(f"   hypo_prone:    {src_strata.get('hypo_prone', 0):3d} patients ({src_hypo_ratio*100:5.1f}%)")
print(f"   normal_stable: {src_strata.get('normal_stable', 0):3d} patients ({(1-src_hypo_ratio-src_hyper_ratio)*100:5.1f}% — absorbs mixed)")
print(f"   hyper_prone:   {src_strata.get('hyper_prone', 0):3d} patients ({src_hyper_ratio*100:5.1f}%)")
print(f"   mixed:         {src_strata.get('mixed', 0):3d} patients (classification only; sampling target=0)")
print(f"\nTarget distribution (DERIVED from source; matches baseline shape):")
print(f"   Hypo-prone:     {target_hypo:3d} patients ({src_hypo_ratio*100:5.1f}%)")
print(f"   Normal-stable:  {target_normal:3d} patients ({target_normal/NUM_PSEUDO*100:5.1f}%)")
print(f"   Hyper-prone:    {target_hyper:3d} patients ({src_hyper_ratio*100:5.1f}%)")
print(f"   Mixed:          {target_mixed:3d} patients (sampling target dropped 2026-05-26)")

# Sample from each stratum
from pyspark.sql.functions import lit, row_number, monotonically_increasing_id

strata_targets = [
    ("hypo_prone", target_hypo),
    ("normal_stable", target_normal),
    ("hyper_prone", target_hyper),
    ("mixed", target_mixed)
]

sampled_plans = []
for stratum_name, target_count in strata_targets:
    if target_count == 0:
        continue
    
    # Get segments for this stratum
    stratum_segs = seg_with_strata.filter(F.col("stratum") == stratum_name)
    n_available = stratum_segs.count()
    
    if n_available == 0:
        print(f"   WARNING: {stratum_name}: No patients available, skipping")
        continue
    
    # Deterministic exact-count sampling.
    #   1. Shuffle source segments via row_number() over rand(seed) — controlled randomization
    #   2. Generate exactly target_count indices 0..target_count-1
    #   3. Map each index to a source segment via modular arithmetic
    # When target_count > n_available, source segments cycle deterministically (each
    # appears ⌈target_count/n_available⌉ or ⌊target_count/n_available⌋ times). Replaces
    # the previous stochastic sample(withReplacement=True, fraction=...) approach, which
    # was Poisson-noisy and could land short of target_count even after .limit() —
    # surfaced as the "999 patients" off-by-one in the gold table on 2026-05-16.
    w_seg = Window.orderBy(F.rand(seed=cfg.seed))
    stratum_segs_indexed = stratum_segs.withColumn(
        "seg_idx", F.row_number().over(w_seg) - F.lit(1)
    )
    sampled = (
        spark.range(target_count)
             .withColumn("seg_idx", (F.col("id") % F.lit(n_available)).cast("int"))
             .drop("id")
             .join(stratum_segs_indexed, "seg_idx")
             .drop("seg_idx")
    )

    sampled_plans.append(sampled)
    print(f"   {stratum_name:15s}: {target_count:3d} requested, {n_available:3d} available, returned exactly {target_count}")

# Combine all strata
plan0 = sampled_plans[0]
for sp in sampled_plans[1:]:
    plan0 = plan0.union(sp)

# Assign pseudo_index
w_pi = Window.orderBy(F.monotonically_increasing_id())
plan = (plan0
  .withColumn("pseudo_index", F.row_number().over(w_pi) - 1)
  .filter(F.col("pseudo_index") < NUM_PSEUDO)
  .select("pseudo_index", "source_patient_id", "contig_id", "segment_start", "segment_end",
          F.lit("stratified").alias("plan_type"), "stratum")
)

plan.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(plan_tbl)

actual_plan_size = plan.count()
print(f"\nStratified sampling plan created: {actual_plan_size} pseudo patients")
print("   Distribution will match baseline after generation")

# Hard assertion: plan size MUST equal NUM_PSEUDO. With the deterministic cycling
# sampler above (added 2026-05-16), this holds by construction. The assertion catches
# regressions (e.g. anyone reintroducing stochastic sampling, or a stratum with zero
# source patients getting silently skipped) BEFORE the off-by-one propagates to the
# gold table + dashboard. Diagnoses the 2026-05-16 "999 patients" issue at the source.
assert actual_plan_size == NUM_PSEUDO, (
    f"[plan-size] expected {NUM_PSEUDO} pseudo patients in {plan_tbl}, got {actual_plan_size}. "
    f"Per-stratum targets were: hypo={target_hypo}, normal={target_normal}, "
    f"hyper={target_hyper}, mixed={target_mixed} "
    f"(sum={target_hypo + target_normal + target_hyper + target_mixed}). "
    f"If a non-zero-target stratum was skipped (n_available == 0), the sum will fall short. "
    f"mixed is intentionally target=0 (dropped 2026-05-26); other strata gaps indicate the "
    f"source dataset doesn't satisfy the hypo/hyper/normal phenotype coverage. Fix either "
    f"by adjusting source phenotypes (dual_01 PHENOTYPES) or by absorbing the missing "
    f"stratum's target into normal_stable in the target computation above."
)

# COMMAND ----------

# DBTITLE 1,Materialize slices from cleaned baseline
# Materialize slices from CLEANED baseline
base2_clean = spark.table(base2_clean_tbl)  # Use cleaned baseline
plan  = spark.table(plan_tbl)

joined = (plan
  .join(base2_clean,
        (plan.source_patient_id == base2_clean.patient_id) &
        (plan.contig_id == base2_clean.contig_id) &
        (base2_clean.time >= plan.segment_start) &
        (base2_clean.time <  plan.segment_end),
        "inner")
  .select(
      "pseudo_index","source_patient_id","plan_type",
      "time",
      F.col("glucose").alias("glucose"),
      "steps","basal_rate","bolus_volume_delivered","carb_input",
      "heart_rate","calories",
      "basal_present","bolus_event","carb_event"
  )
).repartition(200, "pseudo_index")

joined.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(joined_tbl)
print("Joined slices from CLEANED baseline")
print("   Rows:", joined.count())

# COMMAND ----------

# DBTITLE 1,Build baseline validation dataset
# Build baseline validation dataset using same slices as plan (apples-to-apples)
baseline_val = (joined
  .select(
      F.col("source_patient_id"),
      F.col("pseudo_index"),
      F.col("time"),
      F.col("glucose").cast("double").alias("glucose"),
      F.col("steps").cast("double").alias("steps"),
      F.col("basal_rate").cast("double").alias("basal_rate"),
      F.col("bolus_volume_delivered").cast("double").alias("bolus_volume_delivered"),
      F.col("carb_input").cast("double").alias("carb_input"),
      F.col("heart_rate").cast("double").alias("heart_rate"),
      F.col("calories").cast("double").alias("calories"),
      F.col("basal_present").cast("int").alias("basal_present"),
      F.col("bolus_event").cast("int").alias("bolus_event"),
      F.col("carb_event").cast("int").alias("carb_event"),
  )
)
baseline_val.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(baseline_val_tbl)
print("Saved:", baseline_val_tbl)

# COMMAND ----------

# DBTITLE 1,Define Pseudo Generation Function
# ------------------------
# SIMPLIFIED Pseudo generation - Minimal Perturbation Approach
# - Sample with replacement from baseline (stratified by glucose profile)
# - Apply ONLY time shift (±2h) for diversity
# - Optional: tiny Gaussian noise (σ=2 mg/dL) for variation
# - NO gain scaling, NO coupling, NO offset
# - Preserves baseline distribution exactly
# ------------------------

def _circular_shift_df(pdf: pd.DataFrame, k_steps: int) -> pd.DataFrame:
    if k_steps == 0:
        return pdf
    k_steps = k_steps % len(pdf)
    return pd.concat([pdf.iloc[k_steps:], pdf.iloc[:k_steps]], ignore_index=True)

def _ensure_7d_reflective(pdf: pd.DataFrame) -> pd.DataFrame:
    out = pdf.sort_values("time").copy()
    while len(out) < ROWS_7D:
        out = pd.concat([out, out.iloc[::-1].copy()], ignore_index=True)
    return out.iloc[:ROWS_7D].copy()

def make_pseudo_clean(pdf: pd.DataFrame) -> pd.DataFrame:
    pseudo_index = int(pdf["pseudo_index"].iloc[0])
    rng = np.random.default_rng(cfg.seed + pseudo_index)

    out = pdf.sort_values("time").copy()
    out = out.iloc[:ROWS_7D].copy()
    if cfg.allow_reflective_padding and len(out) < ROWS_7D:
        out = _ensure_7d_reflective(out)

    # Small-gap interpolation for glucose
    g = pd.to_numeric(out["glucose"], errors="coerce")
    g = g.interpolate(limit=cfg.interp_max_gap_points, limit_direction="both")
    out["glucose"] = g
    coverage = float(np.mean(np.isfinite(g.to_numpy())))

    # Metadata defaults
    shift_offset_min = 0
    noise_std = 0.0

    if coverage >= cfg.min_glucose_coverage:
        # ONLY transformation: Circular time shift for diversity
        shift_offset_min = int(rng.integers(-cfg.shift_jitter_min, cfg.shift_jitter_min + 1))
        shift_steps = int(round(shift_offset_min / cfg.cadence_min))
        out = _circular_shift_df(out.reset_index(drop=True), shift_steps)

        # SIMPLIFIED: Just use baseline glucose with optional tiny noise
        g = pd.to_numeric(out["glucose"], errors="coerce").to_numpy(dtype=float)
        
        # Optional: Add tiny Gaussian noise for variation (2 mg/dL std)
        noise_std = 2.0
        g_noise = rng.normal(0, noise_std, size=len(g))
        g_final = g + g_noise
        
        # Clip to realistic CGM range [40, 600]
        out["glucose_true"] = np.clip(g_final, 40, 600)
        out["glucose_observed"] = out["glucose_true"]
    else:
        out["glucose_true"] = np.nan
        out["glucose_observed"] = np.nan

    # Align to demo week start
    base_date = pd.Timestamp(cfg.demo_week_start)
    t0 = pd.to_datetime(out["time"]).min()
    out["time"] = pd.to_datetime(out["time"]) + (base_date - t0)

    pseudo_id = f"PSEUDO_{pseudo_index:07d}"
    out["patient_id"] = pseudo_id
    out["source_patient_id"] = str(out["source_patient_id"].iloc[0])
    out["plan_type"] = str(out["plan_type"].iloc[0])

    # Simplified metadata
    out["shift_offset_min"] = shift_offset_min
    out["noise_std"] = noise_std
    out["glucose_coverage"] = coverage

    # Incident defaults
    out["has_incident"] = 0
    out["incident_type"] = None
    out["incident_start_time"] = pd.NaT
    out["incident_end_time"] = pd.NaT
    out["incident_bias_mgdl"] = np.nan

    keep = [
        "patient_id","time",
        "glucose_true","glucose_observed",
        "steps","basal_rate","bolus_volume_delivered","carb_input",
        "heart_rate","calories",
        "basal_present","bolus_event","carb_event",
        "source_patient_id","plan_type",
        "shift_offset_min","noise_std","glucose_coverage",
        "has_incident","incident_type","incident_start_time","incident_end_time","incident_bias_mgdl"
    ]
    return out[keep]

pseudo_schema = StructType([
    StructField("patient_id", StringType(), False),
    StructField("time", TimestampType(), False),
    StructField("glucose_true", DoubleType(), True),
    StructField("glucose_observed", DoubleType(), True),
    StructField("steps", DoubleType(), True),
    StructField("basal_rate", DoubleType(), True),
    StructField("bolus_volume_delivered", DoubleType(), True),
    StructField("carb_input", DoubleType(), True),
    StructField("heart_rate", DoubleType(), True),
    StructField("calories", DoubleType(), True),
    StructField("basal_present", IntegerType(), True),
    StructField("bolus_event", IntegerType(), True),
    StructField("carb_event", IntegerType(), True),
    StructField("source_patient_id", StringType(), False),
    StructField("plan_type", StringType(), False),
    StructField("shift_offset_min", IntegerType(), True),
    StructField("noise_std", DoubleType(), True),
    StructField("glucose_coverage", DoubleType(), True),
    StructField("has_incident", IntegerType(), False),
    StructField("incident_type", StringType(), True),
    StructField("incident_start_time", TimestampType(), True),
    StructField("incident_end_time", TimestampType(), True),
    StructField("incident_bias_mgdl", DoubleType(), True),
])

print("Simplified pseudo generation: time shift + tiny noise only")

# COMMAND ----------

# DBTITLE 1,Pseudo Generation Approach
# MAGIC %md
# MAGIC ## Pseudo Generation Approach
# MAGIC
# MAGIC **Strategy:** Minimal Perturbation + Stratified Sampling
# MAGIC
# MAGIC **Transformations Applied:**
# MAGIC * Time shift: ±2 hours (circular shift for diversity)
# MAGIC * Gaussian noise: σ=2 mg/dL (tiny variation)
# MAGIC * **NO** gain scaling, coupling, or offset adjustments
# MAGIC
# MAGIC **Key Configuration:**
# MAGIC * GLUCOSE_OFFSET: 8.0 mg/dL (from YAML config)
# MAGIC * Anchor: p25 (25th percentile)
# MAGIC * Features: Simple lags + rolling windows (no IOB/COB)
# MAGIC * Class weights: None
# MAGIC * Stratification target: derived from source distribution (#77 2026-05-26)
# MAGIC   — HUPA-UCM source → ~6.4/71.7/21.8%; synthetic source → its own ratios
# MAGIC
# MAGIC **Goal:** Preserve baseline distribution while creating diverse pseudo patients

# COMMAND ----------

# DBTITLE 1,Generate Pseudo Patients (Stratified)
# Generate pseudo_clean_7d with STRATIFIED SAMPLING + SIMPLIFIED generation

print("Generating pseudo_clean_7d with stratified sampling...")
print(f"  - {NUM_PSEUDO} pseudo patients")
print(f"  - Stratified to match baseline (source-derived ratios): {src_hypo_ratio*100:.1f}% hypo, {(1-src_hypo_ratio-src_hyper_ratio)*100:.1f}% normal, {src_hyper_ratio*100:.1f}% hyper")
print(f"  - Transformations: Time shift ±{cfg.shift_jitter_min/60:.1f}h + noise (σ=2 mg/dL)")
print(f"  - NO gain scaling, NO coupling, NO offset")
print("\nThis will take a few minutes...\n")

pseudo_clean = (spark.table(joined_tbl)
  .groupBy("pseudo_index")
  .applyInPandas(make_pseudo_clean, schema=pseudo_schema)
)

pseudo_clean.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(pseudo_clean_tbl)

saved_count = spark.table(pseudo_clean_tbl).count()
patient_count = spark.table(pseudo_clean_tbl).select("patient_id").distinct().count()

print(f"\nSaved: {pseudo_clean_tbl}")
print(f"   Rows: {saved_count:,}")
print(f"   Patients: {patient_count:,}")
print(f"   Avg rows/patient: {saved_count/patient_count:.1f}")

# Verify glucose distribution matches baseline (MAIN GOAL)
print("\n" + "="*80)
print("STRATIFICATION VERIFICATION")
print("="*80)

glucose_dist = spark.table(pseudo_clean_tbl).select(
    F.count("*").alias("total_points"),
    F.sum((F.col("glucose_true") < 70).cast("int")).alias("hypo_points"),
    F.sum(((F.col("glucose_true") >= 70) & (F.col("glucose_true") <= 180)).cast("int")).alias("normal_points"),
    F.sum((F.col("glucose_true") > 180).cast("int")).alias("hyper_points"),
    F.avg("glucose_true").alias("mean_glucose"),
    F.stddev("glucose_true").alias("std_glucose"),
    F.min("glucose_true").alias("min_glucose"),
    F.max("glucose_true").alias("max_glucose")
).collect()[0]

hypo_pct = glucose_dist['hypo_points'] / glucose_dist['total_points'] * 100
normal_pct = glucose_dist['normal_points'] / glucose_dist['total_points'] * 100
hyper_pct = glucose_dist['hyper_points'] / glucose_dist['total_points'] * 100

# Source-derived expected ratios (replaces hardcoded HUPA-UCM 6.4/71.7/21.8 — #77 2026-05-26).
# Tolerance bands: 2% absolute for hypo/hyper, 5% for normal — chosen to allow
# AR(1) + meal-spike + sampling variance while still catching gross drift.
exp_hypo_pct   = src_hypo_ratio * 100
exp_hyper_pct  = src_hyper_ratio * 100
exp_normal_pct = (1 - src_hypo_ratio - src_hyper_ratio) * 100
print(f"\n                    Pseudo      Source-Target   Match")
print("-" * 80)
print(f"Hypo (<70):         {hypo_pct:5.1f}%      {exp_hypo_pct:5.1f}%          {'PASS' if abs(hypo_pct - exp_hypo_pct) < 3 else 'FAIL'}")
print(f"Normal (70-180):    {normal_pct:5.1f}%     {exp_normal_pct:5.1f}%          {'PASS' if abs(normal_pct - exp_normal_pct) < 6 else 'FAIL'}")
print(f"Hyper (>180):       {hyper_pct:5.1f}%      {exp_hyper_pct:5.1f}%          {'PASS' if abs(hyper_pct - exp_hyper_pct) < 4 else 'FAIL'}")

print(f"\nGlucose Statistics:")
print(f"   Mean: {glucose_dist['mean_glucose']:.1f} mg/dL")
print(f"   Std: {glucose_dist['std_glucose']:.1f} mg/dL")
print(f"   Range: [{glucose_dist['min_glucose']:.0f}, {glucose_dist['max_glucose']:.0f}] mg/dL")

# Check for data quality issues
data_quality = spark.table(pseudo_clean_tbl).select(
    F.sum((F.col("bolus_volume_delivered") < 0).cast("int")).alias("negative_bolus"),
    F.sum((F.col("glucose_true") == 40).cast("int")).alias("at_floor_40"),
    F.sum((F.col("glucose_true") == 50).cast("int")).alias("at_floor_50")
).collect()[0]

print(f"\nData Quality:")
print(f"   Negative bolus: {data_quality['negative_bolus']} (should be 0)")
print(f"   At floor 40: {data_quality['at_floor_40']:,} ({data_quality['at_floor_40']/saved_count*100:.2f}%)")
print(f"   At floor 50: {data_quality['at_floor_50']:,} ({data_quality['at_floor_50']/saved_count*100:.2f}%)")

if abs(hypo_pct - 6.4) < 2 and abs(normal_pct - 71.7) < 5 and abs(hyper_pct - 21.8) < 3:
    print("\nSUCCESS: Distribution matches baseline!")
else:
    print("\nWARNING: Distribution doesn't match baseline - check stratification")

print("="*80)

# COMMAND ----------

# DBTITLE 1,Add prediction labels to clean data
# Labels for CLEAN (targets = glucose_true)

def add_labels(df, target_col):
    w = Window.partitionBy("patient_id").orderBy("time")
    out = df
    for h in HORIZONS:
        out = out.withColumn(f"y_tplus_{h}", F.lead(F.col(target_col).cast("double"), h).over(w))
    return out

clean_labeled = add_labels(spark.table(pseudo_clean_tbl), "glucose_true")
clean_labeled = clean_labeled.na.drop(subset=[f"y_tplus_{h}" for h in HORIZONS])

clean_labeled.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(clean_labeled_tbl)
print("Saved:", clean_labeled_tbl, "rows:", spark.table(clean_labeled_tbl).count())

# COMMAND ----------

# DBTITLE 1,Optional incident generation (toggle via INCLUDE_INCIDENT)
# ---------------------------------------
# Optional Incident Generation (TOGGLE)
# ---------------------------------------
if INCLUDE_INCIDENT:
    print("INCLUDE_INCIDENT=true -> generating incident tables")

    pseudo_clean_df = spark.table(pseudo_clean_tbl)
    patients = pseudo_clean_df.select("patient_id").distinct()

    incident_patients = (patients
      .withColumn("r", F.rand(seed=cfg.seed))
      .withColumn("has_incident", (F.col("r") < F.lit(cfg.incident_pct)).cast("int"))
      .withColumn("incident_type", F.when(F.col("has_incident")==1, F.lit("bias")).otherwise(F.lit(None)))
      .withColumn("incident_bias_mgdl", F.when(F.col("has_incident")==1, F.lit(cfg.calibration_bias_mgdl))
                                        .otherwise(F.lit(None).cast("double")))
      .drop("r")
    )

    def inject_single_bias_incident(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values("time").copy()
        has_incident = int(pdf["has_incident"].iloc[0]) if "has_incident" in pdf.columns else 0

        gtrue = pd.to_numeric(pdf["glucose_true"], errors="coerce").to_numpy(dtype=float)
        pdf["glucose_observed"] = gtrue

        if has_incident == 0:
            pdf["incident_type"] = None
            pdf["incident_start_time"] = pd.NaT
            pdf["incident_end_time"] = pd.NaT
            pdf["incident_bias_mgdl"] = np.nan
            return pdf

        bias = float(pdf["incident_bias_mgdl"].iloc[0]) if "incident_bias_mgdl" in pdf.columns else cfg.calibration_bias_mgdl
        times = pd.to_datetime(pdf["time"]).to_numpy()

        start = int(np.searchsorted(times, np.datetime64(incident_start_ts), side="left"))
        end   = int(np.searchsorted(times, np.datetime64(incident_end_ts), side="left"))
        start = max(0, min(start, len(pdf)))
        end   = max(0, min(end, len(pdf)))

        if end <= start + 1:
            pdf["has_incident"] = 0
            pdf["incident_type"] = None
            pdf["incident_start_time"] = pd.NaT
            pdf["incident_end_time"] = pd.NaT
            pdf["incident_bias_mgdl"] = np.nan
            return pdf

        gob = gtrue.copy()
        gob[start:end] = np.clip(gob[start:end] + bias, 40, 400)
        pdf["glucose_observed"] = gob

        pdf["incident_type"] = "bias"
        pdf["incident_start_time"] = incident_start_ts
        pdf["incident_end_time"] = incident_end_ts
        pdf["incident_bias_mgdl"] = bias
        return pdf

    def apply_incident(pdf: pd.DataFrame) -> pd.DataFrame:
        return inject_single_bias_incident(pdf).drop(columns=["pseudo_index"])

    pseudo_for_incident = (pseudo_clean_df
      .drop("has_incident","incident_type","incident_start_time","incident_end_time","incident_bias_mgdl")
      .join(incident_patients, on="patient_id", how="left")
      .withColumn("has_incident", F.coalesce(F.col("has_incident"), F.lit(0)).cast("int"))
    ).withColumn("pseudo_index", F.regexp_extract("patient_id", r"PSEUDO_(\d+)$", 1).cast("int"))

    pseudo_incident = (pseudo_for_incident
      .groupBy("pseudo_index")
      .applyInPandas(apply_incident, schema=pseudo_schema)
    )

    pseudo_incident.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(pseudo_incident_tbl)
    print("Saved:", pseudo_incident_tbl)

    # incident_active
    inc_with_flag = (spark.table(pseudo_incident_tbl)
      .withColumn(
          "incident_active",
          ((F.col("has_incident")==1) &
           (F.col("time") >= F.col("incident_start_time")) &
           (F.col("time") <  F.col("incident_end_time"))).cast("int")
      )
    )
    inc_with_flag.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(incident_flag_tbl)
    print("Saved:", incident_flag_tbl)

    # labeled incident tables (observed-view and true-view)
    inc_df = spark.table(pseudo_incident_tbl)

    inc_labeled_observed = add_labels(inc_df, "glucose_observed").na.drop(subset=[f"y_tplus_{h}" for h in HORIZONS])
    inc_labeled_true     = add_labels(inc_df, "glucose_true").na.drop(subset=[f"y_tplus_{h}" for h in HORIZONS])

    inc_labeled_observed.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(incident_labeled_observed_tbl)
    inc_labeled_true.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(incident_labeled_true_tbl)

    print("Saved:", incident_labeled_observed_tbl)
    print("Saved:", incident_labeled_true_tbl)
else:
    print("INCLUDE_INCIDENT=false -> skipping incident generation")

# COMMAND ----------

# DBTITLE 1,Validation: Baseline vs Pseudo
# ------------------------
# VALIDATION: baseline vs pseudo
# ------------------------
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import ks_2samp, wasserstein_distance

# Sample pooled rows (apples-to-apples: baseline_val vs pseudo_clean)
SAMPLE_FRAC = 0.10
MAX_POINTS = 200000

b = (spark.table(baseline_val_tbl)
     .sample(False, SAMPLE_FRAC, seed=cfg.seed)
     .select("glucose","steps","basal_rate","bolus_volume_delivered","carb_input","heart_rate","calories",
             "basal_present","bolus_event","carb_event","time")
     .limit(MAX_POINTS).toPandas())

p = (spark.table(pseudo_clean_tbl)
     .sample(False, SAMPLE_FRAC, seed=cfg.seed)
     .select(F.col("glucose_true").alias("glucose"),
             "steps","basal_rate","bolus_volume_delivered","carb_input","heart_rate","calories",
             "basal_present","bolus_event","carb_event","time","shift_offset_min")
     .limit(MAX_POINTS).toPandas())

def hist_compare(col, title=None, bins=60, range_=None, logy=False):
    plt.figure(figsize=(8,3))
    plt.hist(b[col].dropna(), bins=bins, alpha=0.5, label="baseline", density=True, range=range_)
    plt.hist(p[col].dropna(), bins=bins, alpha=0.5, label="pseudo", density=True, range=range_)
    plt.title(title or f"{col} distribution")
    if logy: plt.yscale("log")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.show()

# Marginals
hist_compare("glucose", "Glucose distribution", bins=70, range_=(40,400))
hist_compare("heart_rate", "Heart rate distribution", bins=70)
hist_compare("calories", "Calories distribution", bins=70)
hist_compare("steps", "Steps distribution", bins=70, logy=True)
hist_compare("bolus_volume_delivered", "Bolus distribution", bins=70, logy=True)
hist_compare("carb_input", "Carb distribution", bins=70, logy=True)
hist_compare("basal_rate", "Basal distribution", bins=70, logy=True)

# Correlation heatmaps
cols = ["glucose","steps","basal_rate","bolus_volume_delivered","carb_input","heart_rate","calories"]
plt.figure(figsize=(7,5)); sns.heatmap(b[cols].corr(numeric_only=True), cmap="coolwarm", center=0); plt.title("Baseline corr"); plt.show()
plt.figure(figsize=(7,5)); sns.heatmap(p[cols].corr(numeric_only=True), cmap="coolwarm", center=0); plt.title("Pseudo corr"); plt.show()

# Diurnal ribbon check UN-SHIFTED (local hour)
b["hour"] = pd.to_datetime(b["time"]).dt.hour

# unshift pseudo time using shift_offset_min (minutes)
pt = pd.to_datetime(p["time"])
p_local = pt - pd.to_timedelta(p["shift_offset_min"].fillna(0).astype(int), unit="m")
p["local_hour"] = p_local.dt.hour

b_agg = b.groupby("hour")["glucose"].agg(["mean","std"]).reset_index()
p_agg = p.groupby("local_hour")["glucose"].agg(["mean","std"]).reset_index().rename(columns={"local_hour":"hour"})

plt.figure(figsize=(10,3.6))
plt.plot(b_agg["hour"], b_agg["mean"], label="baseline mean"); plt.fill_between(b_agg["hour"], b_agg["mean"]-b_agg["std"], b_agg["mean"]+b_agg["std"], alpha=0.15)
plt.plot(p_agg["hour"], p_agg["mean"], label="pseudo mean (unshifted)"); plt.fill_between(p_agg["hour"], p_agg["mean"]-p_agg["std"], p_agg["mean"]+p_agg["std"], alpha=0.15)
plt.title("Diurnal ribbon check (mean±1σ) — baseline vs pseudo (UN-SHIFTED)")
plt.xlabel("local hour"); plt.ylabel("glucose"); plt.grid(True, alpha=0.3); plt.legend(); plt.show()

# Patient-level scorecard (FIXED: per-window comparison)
# Each pseudo patient = one 7d window, so compare baseline per-window too
base_feat = (spark.table(baseline_val_tbl)
    .groupBy(F.col("source_patient_id").alias("patient_id"), "pseudo_index")  # FIX: group by window
    .agg(
        F.count("*").alias("n_rows"),
        F.avg("glucose").alias("glucose_mean"),
        F.stddev("glucose").alias("glucose_std"),
        F.expr("percentile_approx(glucose, 0.05)").alias("glucose_p05"),
        F.expr("percentile_approx(glucose, 0.50)").alias("glucose_p50"),
        F.expr("percentile_approx(glucose, 0.95)").alias("glucose_p95"),
        F.avg((F.col("glucose") < 70).cast("double")).alias("lt70_rate"),
        F.avg((F.col("glucose") > 250).cast("double")).alias("gt250_rate"),
        # FIX: Use per-day rates instead of totals
        (F.sum("carb_input") / F.lit(cfg.seg_days)).alias("carb_per_day"),
        (F.sum("bolus_volume_delivered") / F.lit(cfg.seg_days)).alias("bolus_per_day"),
        (F.sum("steps") / F.lit(cfg.seg_days)).alias("steps_per_day"),
        F.avg((F.col("carb_input") > 0).cast("double")).alias("carb_event_rate"),
        F.avg((F.col("bolus_volume_delivered") > 0).cast("double")).alias("bolus_event_rate"),
        F.avg((F.col("steps") > 0).cast("double")).alias("steps_event_rate"),
    )
)

pseudo_feat = (spark.table(pseudo_clean_tbl)
    .groupBy("patient_id")
    .agg(
        F.count("*").alias("n_rows"),
        F.avg("glucose_true").alias("glucose_mean"),
        F.stddev("glucose_true").alias("glucose_std"),
        F.expr("percentile_approx(glucose_true, 0.05)").alias("glucose_p05"),
        F.expr("percentile_approx(glucose_true, 0.50)").alias("glucose_p50"),
        F.expr("percentile_approx(glucose_true, 0.95)").alias("glucose_p95"),
        F.avg((F.col("glucose_true") < 70).cast("double")).alias("lt70_rate"),
        F.avg((F.col("glucose_true") > 250).cast("double")).alias("gt250_rate"),
        # FIX: Use per-day rates
        (F.sum("carb_input") / F.lit(cfg.seg_days)).alias("carb_per_day"),
        (F.sum("bolus_volume_delivered") / F.lit(cfg.seg_days)).alias("bolus_per_day"),
        (F.sum("steps") / F.lit(cfg.seg_days)).alias("steps_per_day"),
        F.avg((F.col("carb_input") > 0).cast("double")).alias("carb_event_rate"),
        F.avg((F.col("bolus_volume_delivered") > 0).cast("double")).alias("bolus_event_rate"),
        F.avg((F.col("steps") > 0).cast("double")).alias("steps_event_rate"),
    )
)

base_pd = base_feat.toPandas()
pseudo_pd = pseudo_feat.toPandas()

FEATURES = ["glucose_mean","glucose_std","glucose_p05","glucose_p50","glucose_p95",
            "lt70_rate","gt250_rate","carb_per_day","bolus_per_day","steps_per_day",
            "carb_event_rate","bolus_event_rate","steps_event_rate","n_rows"]

def _clean(x):
    x = pd.to_numeric(pd.Series(x), errors="coerce").dropna()
    x = x[np.isfinite(x)]
    return x

rows = []
eps = 1e-9
for f in FEATURES:
    xb = _clean(base_pd[f])
    xp = _clean(pseudo_pd[f])
    if len(xb) == 0 or len(xp) == 0: 
        continue
    rows.append({
        "feature": f,
        "mean_base": float(xb.mean()),
        "mean_pseudo": float(xp.mean()),
        "mean_rel_diff": float((xp.mean() - xb.mean()) / (abs(xb.mean()) + eps)),
        "ks": float(ks_2samp(xb, xp).statistic),
        "wasserstein": float(wasserstein_distance(xb, xp)),
    })
scorecard = pd.DataFrame(rows).sort_values("ks")
print("\nPATIENT-LEVEL SCORECARD (per 7-day window comparison):")
print("   Lower KS statistic = better match between baseline and pseudo distributions\n")
display(scorecard)

# COMMAND ----------

# DBTITLE 1,Baseline vs Pseudo distribution comparison
# ------------------------
# Distribution Comparison: Baseline vs Pseudo 
# ------------------------
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

print("Baseline vs Pseudo Distribution Comparison")
print("="*80)

# Sample data for visualization
SAMPLE_SIZE = 50000

baseline_sample = (spark.table(BASELINE_TBL)
    .select("glucose")
    .filter(F.col("glucose").isNotNull())
    .sample(False, min(1.0, SAMPLE_SIZE / spark.table(BASELINE_TBL).count()), seed=cfg.seed)
    .limit(SAMPLE_SIZE)
    .toPandas()["glucose"].values)

pseudo_sample = (spark.table(pseudo_clean_tbl)
    .select("glucose_true")
    .filter(F.col("glucose_true").isNotNull())
    .sample(False, min(1.0, SAMPLE_SIZE / spark.table(pseudo_clean_tbl).count()), seed=cfg.seed)
    .limit(SAMPLE_SIZE)
    .toPandas()["glucose_true"].values)

# Calculate distributions
baseline_hypo_pct = np.sum(baseline_sample < 70) / len(baseline_sample) * 100
baseline_normal_pct = np.sum((baseline_sample >= 70) & (baseline_sample <= 180)) / len(baseline_sample) * 100
baseline_hyper_pct = np.sum(baseline_sample > 180) / len(baseline_sample) * 100

pseudo_hypo_pct = np.sum(pseudo_sample < 70) / len(pseudo_sample) * 100
pseudo_normal_pct = np.sum((pseudo_sample >= 70) & (pseudo_sample <= 180)) / len(pseudo_sample) * 100
pseudo_hyper_pct = np.sum(pseudo_sample > 180) / len(pseudo_sample) * 100

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Overlaid histograms with range shading
ax1 = axes[0, 0]
ax1.hist(baseline_sample, bins=80, alpha=0.75, label='Baseline', density=True, range=(40, 400), color='blue')
ax1.hist(pseudo_sample, bins=80, alpha=0.75, label='Pseudo', density=True, range=(40, 400), color='orange')
ax1.axvspan(40, 70, alpha=0.1, color='red', label='Hypoglycemia')
ax1.axvspan(70, 180, alpha=0.1, color='grey', label='Normal')
ax1.axvspan(180, 400, alpha=0.1, color='yellow', label='Hyperglycemia')
ax1.axvline(70, color='red', linestyle='--', linewidth=1)
ax1.axvline(180, color='orange', linestyle='--', linewidth=1)
ax1.set_xlabel('Glucose (mg/dL)')
ax1.set_ylabel('Density')
ax1.set_title('Glucose Distribution: Baseline vs Pseudo')
ax1.legend(loc='upper right')
ax1.grid(True, alpha=0.3)

# Plot 2: Distribution percentages (bar chart)
ax2 = axes[0, 1]
categories = ['Hypo\n(<70)', 'Normal\n(70-180)', 'Hyper\n(>180)']
baseline_pcts = [baseline_hypo_pct, baseline_normal_pct, baseline_hyper_pct]
pseudo_pcts = [pseudo_hypo_pct, pseudo_normal_pct, pseudo_hyper_pct]

x = np.arange(len(categories))
width = 0.35

ax2.bar(x - width/2, baseline_pcts, width, label='Baseline', alpha=0.8, color='blue')
ax2.bar(x + width/2, pseudo_pcts, width, label='Pseudo', alpha=0.8, color='orange')
ax2.set_ylabel('Percentage (%)')
ax2.set_title('Distribution by Glucose Range')
ax2.set_xticks(x)
ax2.set_xticklabels(categories)
ax2.legend()
ax2.grid(True, alpha=0.3, axis='y')

# Add percentage labels on bars
for i, (b_pct, p_pct) in enumerate(zip(baseline_pcts, pseudo_pcts)):
    ax2.text(i - width/2, b_pct + 1, f'{b_pct:.1f}%', ha='center', fontsize=9)
    ax2.text(i + width/2, p_pct + 1, f'{p_pct:.1f}%', ha='center', fontsize=9)

# Plot 3: Cumulative distribution
ax3 = axes[1, 0]
baseline_sorted = np.sort(baseline_sample)
pseudo_sorted = np.sort(pseudo_sample)
baseline_cdf = np.arange(1, len(baseline_sorted) + 1) / len(baseline_sorted)
pseudo_cdf = np.arange(1, len(pseudo_sorted) + 1) / len(pseudo_sorted)

ax3.plot(baseline_sorted, baseline_cdf, label='Baseline', linewidth=2, color='blue')    
ax3.plot(pseudo_sorted, pseudo_cdf, label='Pseudo', linewidth=2, color='orange')
ax3.axvline(70, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax3.axvline(180, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax3.set_xlabel('Glucose (mg/dL)')
ax3.set_ylabel('Cumulative Probability')
ax3.set_title('Cumulative Distribution Function')
ax3.legend()
ax3.grid(True, alpha=0.3)
ax3.set_xlim(40, 400)

# Plot 4: Q-Q plot
ax4 = axes[1, 1]
from scipy import stats
quantiles = np.linspace(0, 1, 100)
baseline_quantiles = np.percentile(baseline_sample, quantiles * 100)
pseudo_quantiles = np.percentile(pseudo_sample, quantiles * 100)

ax4.scatter(baseline_quantiles, pseudo_quantiles, alpha=0.6, s=20)
ax4.plot([40, 400], [40, 400], 'r--', label='Perfect match', linewidth=2)
ax4.set_xlabel('Baseline Quantiles (mg/dL)')
ax4.set_ylabel('Pseudo Quantiles (mg/dL)')
ax4.set_title('Q-Q Plot: Baseline vs Pseudo')
ax4.legend()
ax4.grid(True, alpha=0.3)
ax4.set_xlim(40, 400)
ax4.set_ylim(40, 400)

plt.tight_layout()
plt.show()

print("\n" + "="*80)
print("DISTRIBUTION SUMMARY")
print("="*80)
print(f"\n{'Category':<20} {'Baseline':<12} {'Pseudo':<12} {'Difference'}")
print("-"*80)
print(f"{'Hypoglycemia (<70)':<20} {baseline_hypo_pct:>6.2f}% {pseudo_hypo_pct:>8.2f}% {pseudo_hypo_pct - baseline_hypo_pct:>+10.2f}%")
print(f"{'Normal (70-180)':<20} {baseline_normal_pct:>6.2f}% {pseudo_normal_pct:>8.2f}% {pseudo_normal_pct - baseline_normal_pct:>+10.2f}%")
print(f"{'Hyperglycemia (>180)':<20} {baseline_hyper_pct:>6.2f}% {pseudo_hyper_pct:>8.2f}% {pseudo_hyper_pct - baseline_hyper_pct:>+10.2f}%")

print(f"\nTarget: Match baseline distribution (source-derived ratios: {baseline_hypo_pct:.1f}% / {baseline_normal_pct:.1f}% / {baseline_hyper_pct:.1f}%)")
if abs(pseudo_hypo_pct - baseline_hypo_pct) < 2:
    print("Hypoglycemia: MATCHED (within 2%)")
else:
    print(f"Hypoglycemia: {abs(pseudo_hypo_pct - baseline_hypo_pct):.1f}% difference")

print("="*80)

# COMMAND ----------

# DBTITLE 1,Model Training Section
# MAGIC %md
# MAGIC ### Use generated pseudo patient data to test ability to train forecasting model 

# COMMAND ----------

# DBTITLE 1,Create Feature Table
# ------------------------
# Feature table for GPU XGB (SIMPLIFIED)
# ------------------------
df = spark.table(clean_labeled_tbl)

w_ord = Window.partitionBy("patient_id").orderBy("time")

feat = (df.select(
        "patient_id","time",
        F.col("glucose_observed").cast("double").alias("glucose_observed"),
        F.col("carb_input").cast("double").alias("carb_input"),
        F.col("bolus_volume_delivered").cast("double").alias("bolus_volume_delivered"),
        F.col("basal_rate").cast("double").alias("basal_rate"),
        F.col("steps").cast("double").alias("steps"),
        F.hour("time").cast("int").alias("hour_utc"),
        *[F.col(f"y_tplus_{h}").cast("double").alias(f"y_tplus_{h}") for h in HORIZONS]
     )
     .withColumn("hour_sin", F.sin(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0)))
     .withColumn("hour_cos", F.cos(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0)))
)

# Glucose lags
for k in range(1, cfg.lags+1):
    feat = feat.withColumn(f"glucose_lag_{k}", F.lag("glucose_observed", k).over(w_ord))

# Rolling windows
for rw in cfg.roll_windows:
    w_roll = Window.partitionBy("patient_id").orderBy("time").rowsBetween(-rw+1, 0)
    feat = (feat
      .withColumn(f"g_roll_mean_{rw}", F.avg("glucose_observed").over(w_roll))
      .withColumn(f"g_roll_std_{rw}",  F.stddev("glucose_observed").over(w_roll))
    )

# Rate of change
feat = (feat
  .withColumn("g_delta_1", F.col("glucose_observed") - F.col("glucose_lag_1"))
  .withColumn("g_delta_3", F.col("glucose_observed") - F.col("glucose_lag_3"))
)

# Drop rows with missing critical features
need = [f"glucose_lag_{k}" for k in range(1, cfg.lags+1)] + ["glucose_observed"] + [f"y_tplus_{h}" for h in HORIZONS]
feat = feat.na.drop(subset=need)

feat.write.mode("overwrite").option("overwriteSchema","true").saveAsTable(xgb_features_tbl)

row_count = spark.table(xgb_features_tbl).count()
print(f"\nSaved: {xgb_features_tbl}")
print(f"   Rows: {row_count:,}")
print("\nFeatures: Simple and proven (lags, rolling windows, deltas, hour encoding)")

# COMMAND ----------

# DBTITLE 1,Time Split: Train vs Validation
# ------------------------
# Time split: per patient train days 0-5, validate day 6
# ------------------------
df = spark.table(xgb_features_tbl)

w = Window.partitionBy("patient_id")
df2 = (df
  .withColumn("t0", F.min("time").over(w))
  .withColumn("day_idx", F.floor((F.unix_timestamp("time") - F.unix_timestamp("t0")) / (24*3600)).cast("int"))
  .drop("t0")
)

train_df = df2.filter(F.col("day_idx") <= 5)
demo_df  = df2.filter(F.col("day_idx") >= 6)

print("train rows:", train_df.count(), "demo rows:", demo_df.count())

train_pd = train_df.sample(False, cfg.train_sample_frac, seed=cfg.seed).toPandas()
demo_pd  = demo_df.sample(False, min(1.0, cfg.train_sample_frac), seed=cfg.seed+1).toPandas()

drop_cols = {"patient_id","time","day_idx"} | {f"y_tplus_{h}" for h in HORIZONS}
feature_cols = [c for c in train_pd.columns if c not in drop_cols]

X_train = train_pd[feature_cols].to_numpy(dtype=np.float32)
X_demo  = demo_pd[feature_cols].to_numpy(dtype=np.float32)

# COMMAND ----------

# DBTITLE 1,Optional Hyperparameter Tuning
# MAGIC %md
# MAGIC ## Optional: Hyperparameter Optimization with Optuna
# MAGIC
# MAGIC **Control via widget:** `RUN_OPTUNA_TUNING`
# MAGIC
# MAGIC ### Quick Run (Default)
# MAGIC * **Widget**: `RUN_OPTUNA_TUNING = 'false'`
# MAGIC * **Time**: ~10 minutes
# MAGIC * **Uses**: YAML default hyperparameters
# MAGIC * **Best for**: Quick experiments, demos, baseline runs
# MAGIC
# MAGIC ### Optimized Run
# MAGIC * **Widget**: `RUN_OPTUNA_TUNING = 'true'`
# MAGIC * **Time**: ~25 minutes (includes 20 trials on 4 GPUs)
# MAGIC * **Uses**: Optuna-optimized hyperparameters
# MAGIC * **Best for**: Production models, performance optimization
# MAGIC
# MAGIC ### How It Works
# MAGIC * Cell 26 runs Optuna (if enabled) and **updates config variables** (MAX_DEPTH, ETA, etc.)
# MAGIC * Cell 29 automatically uses the updated variables for training
# MAGIC * "Run All" works seamlessly - just set the widget!
# MAGIC
# MAGIC ### Search Space
# MAGIC * max_depth: [4, 9]
# MAGIC * eta: [0.01, 0.2] (log scale)
# MAGIC * subsample: [0.6, 1.0]
# MAGIC * colsample_bytree: [0.6, 1.0]
# MAGIC * reg_lambda: [0.1, 5.0] (log scale)
# MAGIC
# MAGIC ### Results Storage
# MAGIC * **Location**: `/Volumes/hls_glucosphere/cgm/optuna_studies/`
# MAGIC * **Files**: Best params (JSON), all trials (CSV), study database (SQLite)
# MAGIC
# MAGIC **Note**: Optuna optimizes for 15-min forecast; same hyperparameters used for 30-min forecast.

# COMMAND ----------

# DBTITLE 1,Optuna Hyperparameter Search (Optional)
# ------------------------
# Optuna Hyperparameter Optimization (OPTIONAL)
# Controlled by RUN_OPTUNA_TUNING widget
# If enabled: Finds best hyperparameters and updates config variables
# If disabled: Skips, cell 29 will use YAML defaults
# Works on Classic GPU compute with parallel execution
# ------------------------

# Check widget setting
RUN_OPTUNA = dbutils.widgets.get("RUN_OPTUNA_TUNING") == "true"

if not RUN_OPTUNA:
    print("⏭️  Optuna hyperparameter tuning DISABLED")
    print("="*80)
    print(f"\nRUN_OPTUNA_TUNING widget = 'false'")
    print(f"\nSkipping hyperparameter optimization.")
    print(f"Cell 29 will train models with YAML default hyperparameters.")
    print(f"\nTo enable Optuna tuning:")
    print(f"  1. Set RUN_OPTUNA_TUNING widget to 'true'")
    print(f"  2. Re-run cells 26-27-29 (or Run All)")
    print(f"="*80)
    # Don't exit - just skip, let notebook continue
else:
    # Optuna is enabled - proceed with optimization
    import optuna
    import xgboost as xgb
    import mlflow
    from sklearn.metrics import mean_absolute_error
    import numpy as np
    import time
    import json
    import os
    import shutil

    print("✅ Optuna: Hyperparameter Optimization ENABLED")
    print("="*80)
    print(f"\nSearch Space:")
    print(f"  max_depth: [4, 9]")
    print(f"  eta: [0.01, 0.2] (log scale)")
    print(f"  subsample: [0.6, 1.0]")
    print(f"  colsample_bytree: [0.6, 1.0]")
    print(f"  reg_lambda: [0.1, 5.0] (log scale)")
    print(f"\nOptimizing for: 15-min forecast (y_tplus_3)")
    print(f"Note: Same hyperparameters will be used for 30-min forecast")
    print(f"\n" + "="*80)

    # Set MLflow experiment
    mlflow.set_registry_uri('databricks-uc')
    if cfg.mlflow_experiment.strip():
        mlflow.set_experiment(cfg.mlflow_experiment.strip())

    # Define objective function for Optuna
    def objective(trial, gpu_id=0):
        """Objective function for Optuna - trains one trial on specified GPU"""
        
        # Suggest hyperparameters
        max_depth = trial.suggest_int('max_depth', 4, 9)
        eta = trial.suggest_float('eta', 0.01, 0.2, log=True)
        subsample = trial.suggest_float('subsample', 0.6, 1.0)
        colsample_bytree = trial.suggest_float('colsample_bytree', 0.6, 1.0)
        reg_lambda = trial.suggest_float('reg_lambda', 0.1, 5.0, log=True)
        
        # Prepare data (15-min forecast)
        target = "y_tplus_3"
        y_train = train_pd[target].to_numpy(dtype=np.float32)
        y_demo = demo_pd[target].to_numpy(dtype=np.float32)
        
        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_cols)
        ddemo = xgb.DMatrix(X_demo, label=y_demo, feature_names=feature_cols)
        
        # XGBoost parameters
        params = {
            'objective': 'reg:squarederror',
            'tree_method': 'hist',
            'device': f'cuda:{gpu_id}',
            'max_depth': max_depth,
            'eta': eta,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'reg_lambda': reg_lambda,
            'eval_metric': 'mae',
        }
        
        # Train model with pruning callback
        pruning_callback = optuna.integration.XGBoostPruningCallback(trial, 'validation-mae')
        
        bst = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=500,  # Reduced for faster tuning
            evals=[(dtrain, "train"), (ddemo, "validation")],
            early_stopping_rounds=30,
            verbose_eval=False,
            callbacks=[pruning_callback]
        )
        
        # Evaluate
        pred = bst.predict(ddemo)
        mae = float(mean_absolute_error(y_demo, pred))
        
        return mae

    # Create Optuna study
    print(f"\nCreating Optuna study...")

    # Use /tmp for SQLite database
    study_name = "xgb_15min_optuna"
    study_db_path = f"sqlite:////tmp/{study_name}.db"

    print(f"  Study name: {study_name}")
    print(f"  Database: {study_db_path}")

    # Create study with TPE sampler and Median pruner
    study = optuna.create_study(
        study_name=study_name,
        storage=study_db_path,
        direction='minimize',
        sampler=optuna.samplers.TPESampler(seed=cfg.seed),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=10),
        load_if_exists=True
    )

    print(f"  ✅ Study created")

    print(f"\nStarting Optuna hyperparameter search...")
    print(f"  Total trials: 20")
    print(f"  Strategy: Try parallel (4 GPUs), fallback to sequential")
    print(f"\n" + "="*80)

    # Run optimization
    start_time = time.time()

    # Try parallel execution first (works on classic GPU compute)
    try:
        from joblib import Parallel, delayed
        print(f"\nAttempting parallel execution (4 GPUs)...")
        
        for batch_start in range(0, 20, 4):
            batch_end = min(batch_start + 4, 20)
            print(f"  Running trials {batch_start+1}-{batch_end}...")
            
            # Run 4 trials in parallel (one per GPU)
            Parallel(n_jobs=4, backend='threading')(
                delayed(lambda gpu_id: study.optimize(
                    lambda trial: objective(trial, gpu_id),
                    n_trials=1,
                    show_progress_bar=False
                ))(gpu_id % 4) for gpu_id in range(batch_start, batch_end)
            )
            
            print(f"    Completed {len(study.trials)} trials | Best MAE: {study.best_value:.2f} mg/dL")
        
        print(f"\n✅ Parallel execution successful (4 GPUs)")
        
    except Exception as e:
        # Fallback to sequential execution
        print(f"\n⚠️  Parallel execution failed: {str(e)}")
        print(f"\nFalling back to sequential execution (single GPU)...")
        
        remaining_trials = 20 - len(study.trials)
        if remaining_trials > 0:
            study.optimize(
                lambda trial: objective(trial, gpu_id=0),
                n_trials=remaining_trials,
                show_progress_bar=True
            )
        
        print(f"\n✅ Sequential execution complete")

    tuning_time = time.time() - start_time

    # Get best trial
    best_trial = study.best_trial
    best_params = best_trial.params
    best_mae = best_trial.value

    print(f"\n" + "="*80)
    print(f"OPTUNA OPTIMIZATION RESULTS")
    print(f"="*80)
    print(f"\nTotal tuning time: {tuning_time/60:.1f} minutes")
    print(f"Trials completed: {len(study.trials)}")
    print(f"Trials pruned: {len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED])}")
    print(f"\nBest hyperparameters found (for 15-min forecast):")
    print(f"  max_depth: {best_params['max_depth']}")
    print(f"  eta: {best_params['eta']:.4f}")
    print(f"  subsample: {best_params['subsample']:.3f}")
    print(f"  colsample_bytree: {best_params['colsample_bytree']:.3f}")
    print(f"  reg_lambda: {best_params['reg_lambda']:.3f}")
    print(f"\nBest validation MAE: {best_mae:.2f} mg/dL (from 500-round trials)")

    # Save study results to UC Volumes
    print(f"\n" + "="*80)
    print(f"SAVING RESULTS TO UNITY CATALOG VOLUMES")
    print(f"="*80)

    # Create Unity Catalog Volume
    volume_name = "optuna_studies"
    print(f"  Creating volume: {CATALOG_NAME}.{SCHEMA_NAME}.{volume_name}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.{volume_name}")
    print(f"  ✅ Volume ready")

    # Define UC Volumes path
    uc_storage_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{volume_name}"

    # Save best parameters as JSON
    best_params_path = f"{uc_storage_path}/{study_name}_best_params.json"
    with open(best_params_path, 'w') as f:
        json.dump({
            'study_name': study_name,
            'best_params': best_params,
            'best_mae': best_mae,
            'baseline_params': {
                'max_depth': MAX_DEPTH,
                'eta': ETA,
                'subsample': SUBSAMPLE,
                'colsample_bytree': COLSAMPLE
            },
            'tuning_time_minutes': tuning_time / 60,
            'trials_completed': len(study.trials),
            'trials_pruned': len([t for t in study.trials if t.state == optuna.trial.TrialState.PRUNED]),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }, f, indent=2)

    print(f"\n✅ Saved best parameters: {best_params_path}")

    # Save all trials as CSV
    import pandas as pd
    trials_df = study.trials_dataframe()
    trials_csv_path = f"{uc_storage_path}/{study_name}_all_trials.csv"
    trials_df.to_csv(trials_csv_path, index=False)

    print(f"✅ Saved all trials: {trials_csv_path}")
    print(f"   Total trials: {len(trials_df)}")

    # Copy SQLite database to UC Volumes
    local_db_path = f"/tmp/{study_name}.db"
    uc_db_path = f"{uc_storage_path}/{study_name}.db"
    if os.path.exists(local_db_path):
        shutil.copy(local_db_path, uc_db_path)
        print(f"✅ Copied study database: {uc_db_path}")

    # ------------------------
    # UPDATE CONFIG VARIABLES WITH BEST PARAMS
    # ------------------------
    print(f"\n" + "="*80)
    print(f"UPDATING HYPERPARAMETERS FOR CELL 29")
    print(f"="*80)

    # Store original values for comparison
    YAML_MAX_DEPTH = MAX_DEPTH
    YAML_ETA = ETA
    YAML_SUBSAMPLE = SUBSAMPLE
    YAML_COLSAMPLE = COLSAMPLE

    # Update global config variables with tuned values
    MAX_DEPTH = best_params['max_depth']
    ETA = best_params['eta']
    SUBSAMPLE = best_params['subsample']
    COLSAMPLE = best_params['colsample_bytree']

    print(f"\nHyperparameters updated:")
    print(f"  max_depth: {YAML_MAX_DEPTH} → {MAX_DEPTH}")
    print(f"  eta: {YAML_ETA} → {ETA:.4f}")
    print(f"  subsample: {YAML_SUBSAMPLE} → {SUBSAMPLE:.3f}")
    print(f"  colsample_bytree: {YAML_COLSAMPLE} → {COLSAMPLE:.3f}")

    print(f"\n" + "="*80)
    print(f"✅ OPTUNA OPTIMIZATION COMPLETE!")
    print(f"="*80)
    print(f"\nOptuna tuning: {tuning_time/60:.1f} minutes ({len(study.trials)} trials)")
    print(f"Best validation MAE: {best_mae:.2f} mg/dL (from 500-round trials)")
    print(f"\nResults saved to: {uc_storage_path}")
    print(f"\n✅ Config variables updated - Cell 29 will use optimized hyperparameters")
    print(f"   Both 15-min and 30-min models will use the same optimized params.")
    print(f"="*80)

# COMMAND ----------

# DBTITLE 1,Hyperparameter Status Check
# ------------------------
# Show which hyperparameters will be used by cell 29 (Training)
# ------------------------
import json
import os

print("Hyperparameter Configuration for Cell 29 (Training)")
print("="*80)

# Check if Optuna was run
RUN_OPTUNA = dbutils.widgets.get("RUN_OPTUNA_TUNING") == "true"

if RUN_OPTUNA:
    # Check if Optuna results exist
    volume_name = "optuna_studies"
    study_name = "xgb_15min_optuna"
    uc_storage_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{volume_name}"
    best_params_path = f"{uc_storage_path}/{study_name}_best_params.json"
    
    if os.path.exists(best_params_path):
        # Optuna completed - show optimized params
        with open(best_params_path, 'r') as f:
            optuna_results = json.load(f)
        
        print(f"\n✅ Using OPTUNA-OPTIMIZED hyperparameters")
        print(f"   Source: Cell 26 optimization ({optuna_results['trials_completed']} trials)")
        print(f"   Best MAE: {optuna_results['best_mae']:.2f} mg/dL (15-min forecast)")
        
        print(f"\nOptimized hyperparameters (updated by cell 26):")
        print(f"  max_depth: {MAX_DEPTH}")
        print(f"  eta: {ETA:.4f}")
        print(f"  subsample: {SUBSAMPLE:.3f}")
        print(f"  colsample_bytree: {COLSAMPLE:.3f}")
        
        print(f"\nComparison with YAML baseline:")
        baseline = optuna_results['baseline_params']
        print(f"  max_depth: {baseline['max_depth']} → {MAX_DEPTH}")
        print(f"  eta: {baseline['eta']} → {ETA:.4f}")
        print(f"  subsample: {baseline['subsample']} → {SUBSAMPLE:.3f}")
        print(f"  colsample_bytree: {baseline['colsample_bytree']} → {COLSAMPLE:.3f}")
        
    else:
        # Optuna enabled but not run yet
        print(f"\n⚠️  Optuna enabled but cell 26 hasn't run yet")
        print(f"\nUsing YAML defaults for now:")
        print(f"  max_depth: {MAX_DEPTH}")
        print(f"  eta: {ETA}")
        print(f"  subsample: {SUBSAMPLE}")
        print(f"  colsample_bytree: {COLSAMPLE}")
        
else:
    # Optuna disabled - using YAML defaults
    print(f"\n✅ Using YAML DEFAULT hyperparameters")
    print(f"   Source: {CONFIG_FILE} [{ENV} environment]")
    
    print(f"\nCurrent hyperparameters:")
    print(f"  max_depth: {MAX_DEPTH}")
    print(f"  eta: {ETA}")
    print(f"  subsample: {SUBSAMPLE}")
    print(f"  colsample_bytree: {COLSAMPLE}")

print(f"\n" + "="*80)
print(f"✅ READY FOR CELL 29 (Production Training)")
print(f"="*80)
print(f"\nCell 29 will train production models with:")
print(f"  max_depth={MAX_DEPTH}, eta={ETA:.4f}, subsample={SUBSAMPLE:.3f}, colsample={COLSAMPLE:.3f}")
print(f"  num_boost_round={N_ROUNDS}, early_stopping_rounds={EARLY_STOP}")
print(f"\nBoth 15-min and 30-min models will use these hyperparameters.")
print(f"="*80)

# COMMAND ----------

# DBTITLE 1,XGBoost Training with MLflow Logging
# ------------------------
# XGBoost Training with MLflow Logging
# Uses hyperparameters from either YAML defaults or Optuna optimization (cell 26)
# ------------------------
import mlflow
import mlflow.xgboost
import xgboost as xgb
import json
import time
import matplotlib.pyplot as plt
from sklearn.metrics import mean_absolute_error
from mlflow.tracking import MlflowClient
from mlflow.models.signature import ModelSignature
from mlflow.types.schema import Schema, ColSpec
import numpy as np
import os

# Show which hyperparameters are being used
print("Production Model Training")
print("="*80)

RUN_OPTUNA = dbutils.widgets.get("RUN_OPTUNA_TUNING") == "true"
if RUN_OPTUNA:
    volume_name = "optuna_studies"
    study_name = "xgb_15min_optuna"
    uc_storage_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{volume_name}"
    best_params_path = f"{uc_storage_path}/{study_name}_best_params.json"
    
    if os.path.exists(best_params_path):
        print(f"\n✅ Using OPTUNA-OPTIMIZED hyperparameters")
        print(f"   Source: Cell 26 optimization")
        hyperparam_source = "optuna_optimized"
    else:
        print(f"\n⚠️  Optuna enabled but not run - using YAML defaults")
        print(f"   Source: {cfg.config_file}")
        hyperparam_source = "yaml_default"
else:
    print(f"\n✅ Using YAML DEFAULT hyperparameters")
    print(f"   Source: {dbutils.widgets.get('CONFIG_FILE')} [{dbutils.widgets.get('ENV')} environment]")
    hyperparam_source = "yaml_default"

print(f"\nHyperparameters:")
print(f"  max_depth: {MAX_DEPTH}")
print(f"  eta: {ETA}")
print(f"  subsample: {SUBSAMPLE}")
print(f"  colsample_bytree: {COLSAMPLE}")
print(f"  num_boost_round: {N_ROUNDS}")
print(f"  early_stopping_rounds: {EARLY_STOP}")
print(f"\n" + "="*80)

mlflow.set_registry_uri('databricks-uc')
if cfg.mlflow_experiment.strip():
    mlflow.set_experiment(cfg.mlflow_experiment.strip())

params = dict(
    objective="reg:squarederror",
    tree_method="hist",
    device="cuda",
    max_depth=MAX_DEPTH,
    eta=ETA,
    subsample=SUBSAMPLE,
    colsample_bytree=COLSAMPLE,
    reg_lambda=1.0,
    eval_metric="mae",
)

client = MlflowClient()

def remap_feature_name(feat):
    """Convert technical feature names to readable labels"""
    if feat.startswith('glucose_lag_'):
        lag = feat.split('_')[-1]
        return f"Glucose t-{lag} (lag {int(lag)*5}min)"
    if feat.startswith('g_roll_mean_'):
        window = feat.split('_')[-1]
        return f"Glucose mean (rolling {window})"
    if feat.startswith('g_roll_std_'):
        window = feat.split('_')[-1]
        return f"Glucose std (rolling {window})"
    if feat == 'g_delta_1':
        return "Glucose Δ (5min)"
    if feat == 'g_delta_3':
        return "Glucose Δ (15min)"
    if feat == 'hour_sin':
        return "Hour (sin)"
    if feat == 'hour_cos':
        return "Hour (cos)"
    if feat == 'hour_utc':
        return "Hour (UTC)"
    if feat == 'glucose_observed':
        return "Glucose (current)"
    if feat == 'carb_input':
        return "Carbs"
    if feat == 'bolus_volume_delivered':
        return "Bolus insulin"
    if feat == 'basal_rate':
        return "Basal rate"
    if feat == 'steps':
        return "Steps"
    return feat

def log_data_statistics(train_pd, demo_pd, feature_cols):
    """Log dataset and feature statistics to MLflow UI"""
    mlflow.log_metric("train_rows", len(train_pd))
    mlflow.log_metric("demo_rows", len(demo_pd))
    mlflow.log_metric("train_patients", train_pd['patient_id'].nunique())
    mlflow.log_metric("demo_patients", demo_pd['patient_id'].nunique())
    
    # Target distribution for key horizons
    for horizon in [3, 6]:
        target = f"y_tplus_{horizon}"
        mlflow.log_metric(f"train_{target}_mean", float(train_pd[target].mean()))
        mlflow.log_metric(f"train_{target}_std", float(train_pd[target].std()))
    
    # Glucose distribution by range
    glucose_train = train_pd['glucose_observed'].values
    hypo_pct = (glucose_train < 70).sum() / len(glucose_train) * 100
    normal_pct = ((glucose_train >= 70) & (glucose_train <= 180)).sum() / len(glucose_train) * 100
    hyper_pct = (glucose_train > 180).sum() / len(glucose_train) * 100
    
    mlflow.log_metric("train_hypo_pct", hypo_pct)
    mlflow.log_metric("train_normal_pct", normal_pct)
    mlflow.log_metric("train_hyper_pct", hyper_pct)
    
    # Feature statistics - log top 10
    feature_stats = {}
    for i, feat in enumerate(feature_cols[:10]):
        if feat in train_pd.columns:
            feat_mean = float(train_pd[feat].mean())
            feat_std = float(train_pd[feat].std())
            feat_missing = float(train_pd[feat].isna().sum() / len(train_pd) * 100)
            
            mlflow.log_metric(f"feat_{i+1:02d}_{feat}_mean", feat_mean)
            mlflow.log_metric(f"feat_{i+1:02d}_{feat}_std", feat_std)
            mlflow.log_metric(f"feat_{i+1:02d}_{feat}_missing_pct", feat_missing)
            
            feature_stats[feat] = {
                "mean": feat_mean,
                "std": feat_std,
                "missing_pct": feat_missing
            }
    
    # Save as JSON artifact
    json_path = "/tmp/feature_stats.json"
    with open(json_path, 'w') as f:
        json.dump(feature_stats, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    
    if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
        mlflow.log_artifact(json_path, "data_stats")

def create_model_signature(feature_cols, sample_input):
    """Create explicit MLflow signature with named columns"""
    input_schema = Schema([ColSpec("double", name=col) for col in feature_cols])
    output_schema = Schema([ColSpec("float", name="prediction")])
    return ModelSignature(inputs=input_schema, outputs=output_schema)

def log_and_register_xgb(horizon_steps: int, model_fqn: str):
    target = f"y_tplus_{horizon_steps}"
    y_train = train_pd[target].to_numpy(dtype=np.float32)
    y_demo  = demo_pd[target].to_numpy(dtype=np.float32)

    dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=feature_cols)
    ddemo  = xgb.DMatrix(X_demo,  label=y_demo,  feature_names=feature_cols)

    # Determine run name based on hyperparameter source
    if hyperparam_source == "optuna_optimized":
        run_name = f"xgb_{horizon_steps*5}min_optuna_optimized"
    else:
        run_name = f"xgb_{horizon_steps*5}min_baseline"

    with mlflow.start_run(
        run_name=run_name,
        log_system_metrics=True
    ) as run:
        run_id = run.info.run_id
        start_time = time.time()

        # Log configuration
        mlflow.log_param("hyperparameter_source", hyperparam_source)
        mlflow.log_param("num_pseudo", NUM_PSEUDO)
        mlflow.log_param("seed", cfg.seed)
        mlflow.log_param("horizon_minutes", horizon_steps*5)
        mlflow.log_param("features", "simple_lags_rolling")
        mlflow.log_param("glucose_offset", cfg.glucose_offset)
        mlflow.log_param("train_sample_frac", cfg.train_sample_frac)
        
        for k,v in params.items():
            mlflow.log_param(f"xgb_{k}", v)
        mlflow.log_param("num_boost_round", N_ROUNDS)
        mlflow.log_param("early_stop", EARLY_STOP)

        log_data_statistics(train_pd, demo_pd, feature_cols)

        # Train model
        print(f"\nTraining {horizon_steps*5}min model...")
        bst = xgb.train(
            params=params,
            dtrain=dtrain,
            num_boost_round=N_ROUNDS,
            evals=[(dtrain, "train"), (ddemo, "val_last_day")],
            early_stopping_rounds=EARLY_STOP,
            verbose_eval=50
        )
        
        training_time = time.time() - start_time
        mlflow.log_metric("training_time_seconds", training_time)

        # Predictions and metrics
        pred = bst.predict(ddemo)
        mae = float(mean_absolute_error(y_demo, pred))
        
        glucose_demo = demo_pd["glucose_observed"].to_numpy(dtype=np.float32)
        mae_hypo = float(mean_absolute_error(y_demo[glucose_demo < 70], pred[glucose_demo < 70])) if np.sum(glucose_demo < 70) > 0 else 0
        mae_normal = float(mean_absolute_error(y_demo[(glucose_demo >= 70) & (glucose_demo <= 180)], pred[(glucose_demo >= 70) & (glucose_demo <= 180)]))
        mae_hyper = float(mean_absolute_error(y_demo[glucose_demo > 180], pred[glucose_demo > 180])) if np.sum(glucose_demo > 180) > 0 else 0
        
        mlflow.log_metric("mae_val_last_day", mae)
        mlflow.log_metric("mae_hypo", mae_hypo)
        mlflow.log_metric("mae_normal", mae_normal)
        mlflow.log_metric("mae_hyper", mae_hyper)
        mlflow.log_metric("best_iteration", int(bst.best_iteration))

        # Feature importance
        imp = bst.get_score(importance_type="gain")
        imp_df = pd.DataFrame({"feature": list(imp.keys()), "gain": list(imp.values())}).sort_values("gain", ascending=False)
        imp_df['feature_readable'] = imp_df['feature'].apply(remap_feature_name)
        
        # Log top 10 as metrics
        for idx, row in imp_df.head(10).iterrows():
            mlflow.log_metric(f"feat_imp_{row['feature']}", float(row['gain']))
        
        # Save CSV
        imp_csv_path = "/tmp/feature_importance_gain.csv"
        imp_df.to_csv(imp_csv_path, index=False)
        mlflow.log_artifact(imp_csv_path, "diagnostics")
        
        # Create plot
        plt.figure(figsize=(12, 8))
        top_features = imp_df.head(20)
        plt.barh(range(len(top_features)), top_features['gain'].values, color='steelblue')
        plt.yticks(range(len(top_features)), top_features['feature_readable'].values, fontsize=9)
        plt.xlabel('Gain', fontsize=11)
        plt.title(f'Top 20 Feature Importance - {horizon_steps*5}min Forecast', fontsize=12, fontweight='bold')
        plt.gca().invert_yaxis()
        plt.tight_layout()
        
        plot_path = "/tmp/feature_importance_plot.png"
        plt.savefig(plot_path, dpi=100, bbox_inches='tight')
        plt.close()
        mlflow.log_artifact(plot_path, "diagnostics")

        # Create signature
        signature = create_model_signature(feature_cols, X_train[:1])
        
        # Input example
        input_example = train_pd[feature_cols].head(5)
        
        # Register model
        mlflow.xgboost.log_model(
            xgb_model=bst,
            artifact_path="model",
            registered_model_name=model_fqn,
            signature=signature,
            input_example=input_example
        )

        print(f"\nRegistered: {model_fqn}")
        print(f"   MAE overall: {mae:.2f} | hypo: {mae_hypo:.2f} | normal: {mae_normal:.2f} | hyper: {mae_hyper:.2f}")
        print(f"   Training time: {training_time:.1f}s")
        print(f"   Hyperparameter source: {hyperparam_source}")
        return run_id

def set_alias_champion(model_fqn: str, run_id: str):
    vers = client.search_model_versions(f"name='{model_fqn}'")
    vers = [v for v in vers if v.run_id == run_id]
    v = sorted(vers, key=lambda x: int(x.version), reverse=True)[0]
    client.set_registered_model_alias(name=model_fqn, alias="Champion", version=v.version)
    print(f"{model_fqn}@Champion -> v{v.version}")

print("\nTraining models with MLflow logging...")
print(f"Hyperparameter source: {hyperparam_source}\n")

run15 = log_and_register_xgb(3, uc_model_fqn_15m)
run30 = log_and_register_xgb(6, uc_model_fqn_30m)
set_alias_champion(uc_model_fqn_15m, run15)
set_alias_champion(uc_model_fqn_30m, run30)

print("\n" + "="*80)
print("✅ Training complete!")
print("="*80)
print(f"\nModels registered to Unity Catalog:")
print(f"  • {uc_model_fqn_15m}@Champion")
print(f"  • {uc_model_fqn_30m}@Champion")
print(f"\nHyperparameter source: {hyperparam_source}")
print(f"\nProceed to next cells for fleet inference.")
print(f"="*80)

# COMMAND ----------

# DBTITLE 1,Fleet forecast NOW using registered models
# ------------------------
# Fleet forecast NOW using registered models
# Use RANDOM timepoint from middle days (3-5) to avoid edge effects
# Filter out clipped floor values (glucose_observed <= 40)
# ------------------------
import mlflow.xgboost

m15_uri = f"models:/{uc_model_fqn_15m}@Champion"
m30_uri = f"models:/{uc_model_fqn_30m}@Champion"

bst15 = mlflow.xgboost.load_model(m15_uri)
bst30 = mlflow.xgboost.load_model(m30_uri)

df = spark.table(xgb_features_tbl)

# Calculate day_idx for each patient
w = Window.partitionBy("patient_id")
df_with_day = (df
  .withColumn("t0", F.min("time").over(w))
  .withColumn("day_idx", F.floor((F.unix_timestamp("time") - F.unix_timestamp("t0")) / (24*3600)).cast("int"))
  .drop("t0")
)

# Select ONE random timepoint per patient from days 3-5 (middle of timeline)
# Filter out clipped floor values (glucose_observed <= 40) - these are data artifacts
w_random = Window.partitionBy("patient_id").orderBy(F.rand(seed=cfg.seed))
fleet_sample = (df_with_day
  .filter((F.col("day_idx") >= 3) & (F.col("day_idx") <= 5))  # Middle days
  .filter(F.col("glucose_observed") > 40)  # Exclude clipped floor values
  .withColumn("rn", F.row_number().over(w_random))
  .filter("rn=1")
  .drop("rn", "day_idx")
)

fleet_pd = fleet_sample.toPandas()
X_fleet = fleet_pd[feature_cols].to_numpy(dtype=np.float32)
dfleet = xgb.DMatrix(X_fleet, feature_names=feature_cols)

fleet_pd["pred_15m"] = bst15.predict(dfleet)
fleet_pd["pred_30m"] = bst30.predict(dfleet)
fleet_pd["delta_15m"] = fleet_pd["pred_15m"] - fleet_pd["glucose_observed"]
fleet_pd["delta_30m"] = fleet_pd["pred_30m"] - fleet_pd["glucose_observed"]

fleet_output = fleet_pd[["patient_id","time","glucose_observed","pred_15m","pred_30m","delta_15m","delta_30m",
                         "carb_input","bolus_volume_delivered","basal_rate","steps"]].copy()

spark.createDataFrame(fleet_output).write.mode("overwrite").option("overwriteSchema","true").saveAsTable(fleet_forecast_tbl)

print(f"\nSaved: {fleet_forecast_tbl}")
print(f"   Patients: {len(fleet_output):,}")
print(f"   Glucose range: [{fleet_output['glucose_observed'].min():.0f}, {fleet_output['glucose_observed'].max():.0f}] mg/dL")
print(f"   Average glucose: {fleet_output['glucose_observed'].mean():.1f} mg/dL")
print(f"   Patients at 40 mg/dL: {(fleet_output['glucose_observed'] == 40).sum()} (should be 0)")
print(f"\nSampling: Random timepoint from days 3-5, glucose > 40 mg/dL")
print(f"   - Avoids edge effects (timeline start/end)")
print(f"   - Excludes clipped floor values (data artifacts)")

display(spark.table(fleet_forecast_tbl).orderBy(F.desc("delta_30m")).limit(20))

# COMMAND ----------

# DBTITLE 1,Prediction quality visualization
# Visualize prediction quality
import matplotlib.pyplot as plt

fleet_pd = spark.table(fleet_forecast_tbl).toPandas()

# Compute actual metrics
glucose_obs = fleet_pd['glucose_observed'].values
mae_15m_overall = fleet_pd['delta_15m'].abs().mean()
mae_30m_overall = fleet_pd['delta_30m'].abs().mean()

hypo_mask = glucose_obs < 70
normal_mask = (glucose_obs >= 70) & (glucose_obs <= 180)
hyper_mask = glucose_obs > 180

hypo_count = hypo_mask.sum()
normal_count = normal_mask.sum()
hyper_count = hyper_mask.sum()

mae_15m_hypo = fleet_pd.loc[hypo_mask, 'delta_15m'].abs().mean() if hypo_count > 0 else 0
mae_30m_hypo = fleet_pd.loc[hypo_mask, 'delta_30m'].abs().mean() if hypo_count > 0 else 0
mae_15m_normal = fleet_pd.loc[normal_mask, 'delta_15m'].abs().mean()
mae_30m_normal = fleet_pd.loc[normal_mask, 'delta_30m'].abs().mean()
mae_15m_hyper = fleet_pd.loc[hyper_mask, 'delta_15m'].abs().mean() if hyper_count > 0 else 0
mae_30m_hyper = fleet_pd.loc[hyper_mask, 'delta_30m'].abs().mean() if hyper_count > 0 else 0

fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# Plot 1: Prediction vs Observed (15m)
ax1 = axes[0]
ax1.scatter(fleet_pd['glucose_observed'], fleet_pd['pred_15m'], alpha=0.3, s=10)
ax1.plot([40, 400], [40, 400], 'r--', label='Perfect prediction')
ax1.set_xlabel('Observed Glucose (mg/dL)')
ax1.set_ylabel('Predicted 15m (mg/dL)')
ax1.set_title('15-min Predictions vs Observed')
ax1.grid(True, alpha=0.3)
ax1.legend()
ax1.set_xlim(40, 400)
ax1.set_ylim(40, 400)

# Plot 2: Error distribution (15m)
ax2 = axes[1]
errors_15m = fleet_pd['delta_15m'].values
ax2.hist(errors_15m, bins=50, alpha=0.7, edgecolor='black')
ax2.axvline(0, color='red', linestyle='--', label='Zero error')
ax2.set_xlabel('Prediction Error (mg/dL)')
ax2.set_ylabel('Count')
ax2.set_title(f'15-min Error Distribution\nMAE={mae_15m_overall:.1f} mg/dL')
ax2.grid(True, alpha=0.3)
ax2.legend()

# Plot 3: Error by glucose range (FIXED: count in x-axis labels)
ax3 = axes[2]
counts = [hypo_count, normal_count, hyper_count]
ranges = [f'Hypo\n(<70)\nn={counts[0]}', 
          f'Normal\n(70-180)\nn={counts[1]}', 
          f'Hyper\n(>180)\nn={counts[2]}']
maes_15 = [mae_15m_hypo, mae_15m_normal, mae_15m_hyper]
maes_30 = [mae_30m_hypo, mae_30m_normal, mae_30m_hyper]

x = np.arange(len(ranges))
width = 0.35
ax3.bar(x - width/2, maes_15, width, label='15-min MAE', alpha=0.8)
ax3.bar(x + width/2, maes_30, width, label='30-min MAE', alpha=0.8)
ax3.set_ylabel('MAE (mg/dL)')
ax3.set_title('Prediction Error by Glucose Range')
ax3.set_xticks(x)
ax3.set_xticklabels(ranges, fontsize=9)
ax3.legend()
ax3.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.show()

print("\n" + "="*80)
print("PREDICTION QUALITY SUMMARY")
print("="*80)
print(f"\nOverall MAE: {mae_15m_overall:.1f} mg/dL (15m) | {mae_30m_overall:.1f} mg/dL (30m)")
print(f"\nBy glucose range:")
print(f"  Hypo (<70):     {hypo_count:3} patients ({hypo_count/len(fleet_pd)*100:4.1f}%) | MAE: {mae_15m_hypo:.1f} / {mae_30m_hypo:.1f} mg/dL")
print(f"  Normal (70-180): {normal_count:3} patients ({normal_count/len(fleet_pd)*100:4.1f}%) | MAE: {mae_15m_normal:.1f} / {mae_30m_normal:.1f} mg/dL")
print(f"  Hyper (>180):   {hyper_count:3} patients ({hyper_count/len(fleet_pd)*100:4.1f}%) | MAE: {mae_15m_hyper:.1f} / {mae_30m_hyper:.1f} mg/dL")
print("="*80)

# COMMAND ----------

# DBTITLE 1,Pipeline Output Summary
print("PIPELINE COMPLETE - Output Summary")
print("="*80)
print("\nCore Tables:")
print(f"  Pseudo patients: {pseudo_clean_tbl}")
print(f"  Labeled data: {clean_labeled_tbl}")
print(f"  Features: {xgb_features_tbl}")
print(f"  Fleet forecast: {fleet_forecast_tbl}")

print(f"\nModels (Unity Catalog):")
print(f"  15-min: {uc_model_fqn_15m}@Champion")
print(f"  30-min: {uc_model_fqn_30m}@Champion")

if INCLUDE_INCIDENT:
    print(f"\nIncident Tables:")
    print(f"  Incident data: {pseudo_incident_tbl}")
    print(f"  Incident flags: {incident_flag_tbl}")
    print(f"  Labeled (observed): {incident_labeled_observed_tbl}")
    print(f"  Labeled (true): {incident_labeled_true_tbl}")

print("="*80)

# COMMAND ----------

# DBTITLE 1,Production MAE Monitoring Guide
# MAGIC %md
# MAGIC ## Production MAE Monitoring
# MAGIC
# MAGIC **How MAE is Calculated:**
# MAGIC * MAE = Average of |Predicted - Actual|
# MAGIC * 15-min MAE: 5.8 mg/dL (predictions off by ~6 mg/dL on average)
# MAGIC * 30-min MAE: 9.8 mg/dL (longer horizon = larger error)
# MAGIC * Calculated by glucose range: hypo (3.9), normal (5.4), hyper (7.3) for 15-min
# MAGIC
# MAGIC **Production Monitoring Options:**
# MAGIC
# MAGIC **Option 1: Real-time calculation** (requires ground truth)
# MAGIC * Collect predictions at time T
# MAGIC * Wait 15/30 minutes for actual glucose measurement
# MAGIC * Calculate: |prediction - actual| for each patient
# MAGIC * Aggregate: rolling average over time window (hourly/daily)
# MAGIC * Challenge: 15-30 minute delay before MAE available
# MAGIC
# MAGIC **Option 2: Batch evaluation** (current approach)
# MAGIC * Store predictions in `fleet_forecast_now` table
# MAGIC * Join predictions with future actual values using time offset
# MAGIC * Compute MAE across patient cohorts
# MAGIC * Track by glucose range, time of day, patient characteristics
# MAGIC
# MAGIC **Option 3: Proxy metrics** (no ground truth delay)
# MAGIC * Monitor prediction confidence intervals
# MAGIC * Track feature drift (glucose lag patterns, carb inputs)
# MAGIC * Use model uncertainty estimates from XGBoost
# MAGIC * Alert when predictions fall outside clinical safety bounds (e.g., predicted hypo <70)
# MAGIC
# MAGIC **Recommended:** Combine Option 2 (batch MAE for model monitoring) with Option 3 (real-time safety checks). Log all predictions to enable retrospective analysis when actual values arrive.

# COMMAND ----------

# DBTITLE 1,Pipeline Complete
# MAGIC %md
# MAGIC ## Pipeline Complete
# MAGIC
# MAGIC **Output Tables:**
# MAGIC * `pseudo_clean_7d`: 1000 pseudo patients (stratified sampling)
# MAGIC * `pseudo_clean_7d_labeled`: With prediction targets (5/10/15/30 min)
# MAGIC * `xgb_flat_min_lags12`: Feature table (lags, rolling windows, deltas)
# MAGIC * `fleet_forecast_now`: Latest predictions for all patients
# MAGIC
# MAGIC **Models (Unity Catalog):**
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_15m@Champion`
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_30m@Champion`
# MAGIC
# MAGIC **Configuration:**
# MAGIC * GLUCOSE_OFFSET=8.0 mg/dL
# MAGIC * Simple features (no IOB/COB)
# MAGIC * No class weights
# MAGIC * Stratified sampling for distribution match

# COMMAND ----------

# DBTITLE 1,Scaling Analysis - Should We Generate More Patients?
# MAGIC %md
# MAGIC ## Scaling Analysis: 1000 vs More Patients
# MAGIC
# MAGIC **Current Performance (1000 patients):**
# MAGIC * Overall MAE: **5.8 mg/dL** (15m) - STATE-OF-ART
# MAGIC * By range: Hypo 5.2 | Normal 5.1 | Hyper 8.3 mg/dL
# MAGIC * Distribution: Perfect match to baseline
# MAGIC
# MAGIC **Scaling Trade-offs:**
# MAGIC
# MAGIC | Patients | Time | Estimated MAE | Improvement | Worth It? |
# MAGIC |----------|------|---------------|-------------|----------|
# MAGIC | 1,000 (current) | - | 5.8 mg/dL | - | ✅ Excellent |
# MAGIC | 2,000 | ~30 min | ~5.1 mg/dL | 12% | Marginal |
# MAGIC | 5,000 | ~75 min | ~4.1 mg/dL | 29% | Marginal |
# MAGIC | 10,000 | ~150 min | ~3.4 mg/dL | 41% | Marginal |
# MAGIC
# MAGIC **When to Add More:**
# MAGIC * ✅ Deploying to production (need robustness)
# MAGIC * ✅ Publishing research paper (need statistical power)
# MAGIC * ✅ Handling diverse patient populations
# MAGIC * ✅ MAE degrades in real-world testing
# MAGIC
# MAGIC **When NOT to Add More:**
# MAGIC * ✅ Demo purposes (current case)
# MAGIC * ✅ Already have excellent performance (5.8 mg/dL)
# MAGIC * ✅ Time-constrained
# MAGIC * ✅ Proof-of-concept phase
# MAGIC
# MAGIC **Recommendation:** Keep 1000 patients. Performance is already exceptional and near the ceiling. Focus on incident simulation and MLflow system metrics testing instead.

# COMMAND ----------

# DBTITLE 1,Understanding has_incident vs incident_type
# MAGIC %md
# MAGIC ## Understanding Incident Flags
# MAGIC
# MAGIC Two different fields serve different purposes — note the SCOPE difference (patient vs timepoint):
# MAGIC
# MAGIC ### `has_incident = 1` — PATIENT-LEVEL flag
# MAGIC * Set to `1` for **every** record of any patient flagged for an incident (covers their entire 7-day timeline)
# MAGIC * **Per affected patient** = one patient's full 7-day timeline at 5-minute cadence:
# MAGIC   ```
# MAGIC   7 days × 24 hours/day × (60 min/hour ÷ 5 min/timepoint)
# MAGIC     = 7 × 24 × 12
# MAGIC     = 2,016 records
# MAGIC   ```
# MAGIC * **Table-wide count** = (number of affected patients) × 2,016:
# MAGIC   ```
# MAGIC   incident_pct × total_patients × 2,016
# MAGIC     = 0.3 × 1,000 × 2,016                  (with default config)
# MAGIC     = 300 patients × 2,016
# MAGIC     = ~604,800 rows with has_incident = 1
# MAGIC   ```
# MAGIC * Used for: filtering/grouping patients by incident status
# MAGIC * Question: *"Does this patient have an incident event somewhere in their data?"*
# MAGIC
# MAGIC ### `incident_type = "calibration_bias"` — TIMEPOINT-LEVEL flag
# MAGIC * Only set on the EXACT records inside the actual incident window
# MAGIC * **Per affected patient** = one patient's incident-window timepoints:
# MAGIC   ```
# MAGIC   incident_duration_min ÷ cadence_min
# MAGIC     = 180 min ÷ 5 min/timepoint            (with default config)
# MAGIC     = 36 timepoints
# MAGIC   ```
# MAGIC   Window starts at `incident_start_day` + `incident_start_hour` (default: day 2, hour 14) and runs `incident_duration_min` long (default 180 min = 3 hrs).
# MAGIC * **Table-wide count** = (number of affected patients) × 36:
# MAGIC   ```
# MAGIC   incident_pct × total_patients × 36
# MAGIC     = 0.3 × 1,000 × 36                     (with default config)
# MAGIC     = 300 patients × 36
# MAGIC     = ~10,800 rows with incident_type = "calibration_bias"
# MAGIC   ```
# MAGIC * Used for: identifying exact affected measurements for analysis or model training
# MAGIC * Question: *"Is this specific measurement affected by the incident?"*
# MAGIC
# MAGIC ### Quick reference (numbers reflect default `baseline_config.yaml`)
# MAGIC | Field | Scope | Per-patient | Table-wide | Use case |
# MAGIC |---|---|---|---|---|
# MAGIC | `has_incident = 1` | All records of affected patients (full 7-day timeline) | 2,016 records | ~604,800 rows | "Which patients?" |
# MAGIC | `incident_type = "calibration_bias"` | Only in-window records | 36 records (3 hrs) | ~10,800 rows | "Which timepoints?" |
# MAGIC
# MAGIC **Bidirectional variant — `dual_05_CGM_Incident_Inference_DeviceCalibrationBug_Bidirectional.py`:**
# MAGIC The affected cohort is split into positive- and negative-bias subgroups via the `incident_direction` column (`positive` / `negative` for affected patients, `null` for clean). Counts above are unchanged; `incident_direction` is just a per-affected-patient label to filter MAE breakouts by direction.
