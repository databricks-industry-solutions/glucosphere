# Databricks notebook source
# DBTITLE 1,Notebook Overview - Incident Simulation
# MAGIC %md
# MAGIC # CGM Incident Simulation - Device Calibration Bug
# MAGIC
# MAGIC ## Purpose
# MAGIC Demonstrate how a **device calibration bug** (+40 mg/dL bias) causes catastrophic model failure, even for high-performing models (5.8 mg/dL baseline MAE).
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Incident Scenario
# MAGIC * **Bug Type:** Device calibration error causing **+40 mg/dL systematic bias**
# MAGIC * **Timing:** Day 2, 2:00 PM - 5:00 PM (3-hour window)
# MAGIC * **Affected:** 30% of patients (300 out of 1000)
# MAGIC * **Impact:** MAE increases from **3.8 mg/dL → 38.3 mg/dL** (920% degradation)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Configuration Approach
# MAGIC **Hybrid YAML + Widgets** (similar to baseline notebook)
# MAGIC * **7 essential widgets**: ENV, CATALOG_NAME, SCHEMA_NAME, INCLUDE_INCIDENT, RUN_OPTUNA_TUNING, CONFIG_FILE, NUM_PSEUDO_OVERRIDE
# MAGIC * **All other parameters**: Loaded from `configs/baseline_config.yaml`
# MAGIC * **Access pattern**: Use `cfg.param_name` for internal parameters (e.g., `cfg.incident_pct`, `cfg.calibration_bias_mgdl`)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Tables
# MAGIC
# MAGIC **Input:**
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.pseudo_clean_7d` - Clean baseline data (from baseline notebook)
# MAGIC
# MAGIC **Output:**
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.pseudo_incident_7d` - Data with +40 mg/dL bias injected
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.pseudo_incident_7d_labeled` - Incident data with prediction labels
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.fleet_forecast_incident` - Fleet-wide predictions (demo table)
# MAGIC
# MAGIC **Models:**
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.cgm_xgb_15m@Champion` - Clean-period XGBoost (15-min horizon)
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.cgm_xgb_30m@Champion` - Clean-period XGBoost (30-min horizon)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Notebook Flow
# MAGIC
# MAGIC **Setup (Cells 3-7):** Install packages, configure widgets, load YAML config, define tables, import libraries
# MAGIC
# MAGIC **Data Preparation (Cells 8-11):** Load clean data → Define incident window → Inject +40 mg/dL bias → Add prediction labels
# MAGIC
# MAGIC **Inference & Analysis (Cells 12-18):** Load clean models → Run inference on incident data → Analyze MAE degradation → Visualize impact (3-panel MAE + 3-panel glucose timelines) → Distribution analysis → Summary statistics
# MAGIC
# MAGIC **Optional (Cells 21-22):** Model comparison (requires incident-trained models) → Fleet forecast table
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Findings
# MAGIC * **Clean period:** MAE = 3.8 mg/dL (15m) | 5.9 mg/dL (30m) - Excellent performance
# MAGIC * **Incident period:** MAE = 38.3 mg/dL (15m) | 36.8 mg/dL (30m) - Catastrophic failure
# MAGIC * **Degradation:** +920% (15m) | +522% (30m)
# MAGIC * **Root cause:** Model trained on clean data fails when device inputs are biased
# MAGIC * **Implication:** Critical need for real-time device quality monitoring

# COMMAND ----------

# DBTITLE 1,Quick Start Guide
# MAGIC %md
# MAGIC ## Quick Start
# MAGIC
# MAGIC **Run cells 3-18** to see the complete incident analysis (~5 min)
# MAGIC
# MAGIC **Key visualizations:**
# MAGIC * Cell 14: MAE spike during incident (affected patients show ~38 mg/dL MAE)
# MAGIC * Cell 15: 3-panel MAE comparison (all vs affected vs unaffected patients)
# MAGIC * Cell 16: 3-panel glucose timeline (shows +40 mg/dL bias in affected patients)
# MAGIC * Cell 17: Glucose distribution analysis
# MAGIC
# MAGIC **Demo table:** `${CATALOG_NAME}.${SCHEMA_NAME}.fleet_forecast_incident` (Cell 22)

# COMMAND ----------

# DBTITLE 1,Install XGBoost and restart Python
# MAGIC %pip install xgboost pyyaml scipy matplotlib seaborn scikit-learn "mlflow[databricks]" databricks-sdk --quiet
# MAGIC
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# DBTITLE 1,Essential Widgets (8 only - YAML config approach)
# ------------------------
# Essential Widgets (8 only)
# All other parameters loaded from YAML config
# ------------------------

# Remove all existing widgets first
dbutils.widgets.removeAll()

# Essential widgets only
dbutils.widgets.dropdown("ENV", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("CATALOG_NAME", "your_workspace_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere", "Schema")
dbutils.widgets.dropdown("INCLUDE_INCIDENT", "true", ["false", "true"], "Include Incident")
dbutils.widgets.dropdown("RUN_OPTUNA_TUNING", "false", ["false", "true"], "Run Optuna Tuning")
dbutils.widgets.text("CONFIG_FILE", "configs/baseline_config.yaml", "Config File")
dbutils.widgets.text("NUM_PSEUDO_OVERRIDE", "", "Num Pseudo Override (optional)")
dbutils.widgets.text("DEMO_WEEK_START", "", "Demo Week Start override (empty = use YAML 'auto'/specific date)")

# Define HORIZONS here (used by multiple cells)
HORIZONS = [1, 2, 3, 6]  # 5/10/15/30 min ahead

print("✓ Essential widgets created (8 total)")
print("\nWidget values:")
print(f"  ENV: {dbutils.widgets.get('ENV')}")
print(f"  CATALOG: {dbutils.widgets.get('CATALOG_NAME')}")
print(f"  SCHEMA: {dbutils.widgets.get('SCHEMA_NAME')}")
print(f"  INCLUDE_INCIDENT: {dbutils.widgets.get('INCLUDE_INCIDENT')}")
print(f"  RUN_OPTUNA_TUNING: {dbutils.widgets.get('RUN_OPTUNA_TUNING')}")
print(f"  CONFIG_FILE: {dbutils.widgets.get('CONFIG_FILE')}")
print(f"  DEMO_WEEK_START: {dbutils.widgets.get('DEMO_WEEK_START') or '(empty — use YAML)'}")
print(f"\nℹ️  All other parameters will be loaded from YAML config")
print(f"ℹ️  Incident parameters: cfg.incident_pct, cfg.calibration_bias_mgdl, etc.")

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

        # Determine raw value: widget override → YAML config
        if name_upper in widget_overrides:
            value = widget_overrides[name_upper]
        elif name_upper in config:
            value = config[name_upper]
        else:
            raise AttributeError(f"Config parameter '{name}' not found in YAML or widgets")

        # Auto-resolve DEMO_WEEK_START sentinel to (today_utc - 6 days) so the
        # 7-day demo window ends on today. Pin with a specific date string in
        # YAML (e.g. '2026-01-05') for reproducibility / CI snapshot tests.
        if name_upper == 'DEMO_WEEK_START' and value in (None, 'auto', ''):
            from datetime import datetime, timedelta
            value = (datetime.utcnow() - timedelta(days=6)).strftime('%Y-%m-%d')
            print(f"[CONFIG] demo_week_start auto-resolved to {value} (today_utc - 6 days)")

        cache[name_upper] = value
        return value
    
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
demo_week_start_override = dbutils.widgets.get("DEMO_WEEK_START").strip()

# Widget overrides (UPPERCASE keys)
widget_overrides = {
    "CATALOG_NAME": catalog_name,
    "SCHEMA_NAME": schema_name,
    "INCLUDE_INCIDENT": include_incident,
}

# Add optional overrides
if num_pseudo_override:
    widget_overrides["NUM_PSEUDO"] = int(num_pseudo_override)
if demo_week_start_override:
    widget_overrides["DEMO_WEEK_START"] = demo_week_start_override

# Create config object
cfg = Config(config_file, env, widget_overrides)

# ------------------------
# HYBRID APPROACH: Expose only user-facing variables as UPPERCASE
# Use cfg.param for internal parameters (cleaner, less duplication)
# ------------------------

# User-facing variables (catalog, schema, tables, key settings)
CATALOG_NAME = cfg.catalog_name
SCHEMA_NAME = cfg.schema_name
INCLUDE_INCIDENT = cfg.include_incident
NUM_PSEUDO = cfg.num_pseudo

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
print("✓ Configuration loaded (env={})".format(env))
print(f"\nUser-facing variables (UPPERCASE):")
print(f"  CATALOG_NAME: {CATALOG_NAME}")
print(f"  SCHEMA_NAME: {SCHEMA_NAME}")
print(f"  NUM_PSEUDO: {NUM_PSEUDO}")
print(f"  INCLUDE_INCIDENT: {INCLUDE_INCIDENT}")
print(f"\nIncident parameters (from cfg.*):")
print(f"  cfg.incident_pct: {cfg.incident_pct} ({cfg.incident_pct*100:.0f}% of patients)")
print(f"  cfg.calibration_bias_mgdl: {cfg.calibration_bias_mgdl} mg/dL")
print(f"  cfg.incident_start_day: {cfg.incident_start_day} (Day {cfg.incident_start_day})")
print(f"  cfg.incident_start_hour: {cfg.incident_start_hour} ({cfg.incident_start_hour}:00)")
print(f"  cfg.incident_duration_min: {cfg.incident_duration_min} min ({cfg.incident_duration_min/60:.1f} hours)")
print(f"  Incident window: {incident_start_ts} to {incident_end_ts}")
print(f"\nInternal parameters (use cfg.param):")
print(f"  cfg.seed: {cfg.seed}")
print(f"  cfg.lags: {cfg.lags}")
print(f"  cfg.roll_windows: {cfg.roll_windows}")
print(f"  cfg.train_sample_frac: {cfg.train_sample_frac}")
print(f"\nXGBoost hyperparameters (may be updated by Optuna):")
print(f"  MAX_DEPTH: {MAX_DEPTH}, ETA: {ETA}")
print(f"  N_ROUNDS: {N_ROUNDS}, EARLY_STOP: {EARLY_STOP}")
print(f"\nℹ️  Using {config_file} with widget overrides")
print(f"ℹ️  Access internal params as: cfg.param_name (e.g., cfg.seed, cfg.incident_pct)")

# COMMAND ----------

# DBTITLE 1,Define Output Tables
# Output tables - INCIDENT SIMULATION

# Incident data tables
pseudo_incident_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d"
incident_flag_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_with_flag"

# Feature and forecast tables
xgb_features_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.xgb_flat_min_lags{cfg.lags}_incident"
fleet_forecast_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.fleet_forecast_incident"

# UC model names (incident-trained models)
uc_model_fqn_15m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{cfg.uc_model_name_15m}_incident"
uc_model_fqn_30m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{cfg.uc_model_name_30m}_incident"

# Reference to clean models (for comparison)
uc_model_fqn_15m_clean = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_15m"
uc_model_fqn_30m_clean = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_30m"

# Clean data source table (pseudo patient data with glucose_true column)
pseudo_clean_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_clean_7d"

print("Table Configuration:")
print(f"   Clean data source: {pseudo_clean_tbl}")
print(f"   Incident data output: {pseudo_incident_tbl}")
print(f"   Incident models: {uc_model_fqn_15m}, {uc_model_fqn_30m}")

# COMMAND ----------

# DBTITLE 1,Import libraries
from pyspark.sql import functions as F, Window
from pyspark.sql.types import *
import pandas as pd
import numpy as np

# COMMAND ----------

# DBTITLE 1,Load clean pseudo data
# ------------------------
# Load clean pseudo data (from baseline notebook)
# ------------------------

print("Loading clean pseudo data...")
print(f"   Source: {pseudo_clean_tbl}")

pseudo_clean = spark.table(pseudo_clean_tbl)

# Verify data quality
clean_stats = pseudo_clean.select(
    F.count("*").alias("total_rows"),
    F.countDistinct("patient_id").alias("total_patients"),
    F.avg("glucose_true").alias("avg_glucose"),
    F.sum((F.col("glucose_true") < 70).cast("int")).alias("hypo_points"),
    F.sum(((F.col("glucose_true") >= 70) & (F.col("glucose_true") <= 180)).cast("int")).alias("normal_points"),
    F.sum((F.col("glucose_true") > 180).cast("int")).alias("hyper_points")
).collect()[0]

hypo_pct = clean_stats['hypo_points'] / clean_stats['total_rows'] * 100
normal_pct = clean_stats['normal_points'] / clean_stats['total_rows'] * 100
hyper_pct = clean_stats['hyper_points'] / clean_stats['total_rows'] * 100

print(f"\n[SUCCESS] Clean data loaded:")
print(f"   Rows: {clean_stats['total_rows']:,}")
print(f"   Patients: {clean_stats['total_patients']:,}")
print(f"   Avg glucose: {clean_stats['avg_glucose']:.1f} mg/dL")
print(f"   Distribution: {hypo_pct:.1f}% hypo | {normal_pct:.1f}% normal | {hyper_pct:.1f}% hyper")
print(f"\n[SUCCESS] Ready for incident injection")

# COMMAND ----------

# DBTITLE 1,Define incident window and select affected patients
# ------------------------
# Define incident window and select affected patients
# ------------------------

print("Defining incident parameters...")

# Use demo_week_start from YAML config (same as baseline notebook)
# This ensures incident window aligns with the data timerange
demo_week_start = cfg.demo_week_start

print(f"\nData timerange (from YAML):")
print(f"   demo_week_start: {demo_week_start}")
print(f"   Expected data: {demo_week_start} to {pd.Timestamp(demo_week_start) + pd.Timedelta(days=7)}")

# Calculate incident window
base_date = pd.Timestamp(demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)

print(f"\nIncident Window:")
print(f"   Start: {incident_start_ts}")
print(f"   End: {incident_end_ts}")
print(f"   Duration: {cfg.incident_duration_min} minutes ({cfg.incident_duration_min/60:.1f} hours)")

# Verify incident window is within data timerange
data_start = pd.Timestamp(demo_week_start)
data_end = data_start + pd.Timedelta(days=7)
if incident_start_ts < data_start or incident_end_ts > data_end:
    print(f"\n⚠️  WARNING: Incident window is OUTSIDE data timerange!")
    print(f"   Data: {data_start} to {data_end}")
    print(f"   Incident: {incident_start_ts} to {incident_end_ts}")
else:
    print(f"   ✅ Incident window is within data timerange")

# Select patients for incident (random 30%)
all_patients = pseudo_clean.select("patient_id").distinct()
total_patients = all_patients.count()
n_incident_patients = int(total_patients * cfg.incident_pct)

incident_patients = (all_patients
  .orderBy(F.rand(seed=cfg.seed))
  .limit(n_incident_patients)
  .withColumn("has_incident", F.lit(1))
)

print(f"\nAffected Patients:")
print(f"   Total patients: {total_patients}")
print(f"   Incident patients: {n_incident_patients} ({cfg.incident_pct*100:.0f}%)")
print(f"   Clean patients: {total_patients - n_incident_patients} ({(1-cfg.incident_pct)*100:.0f}%)")

# Calculate expected impact
points_per_patient = pseudo_clean.count() / total_patients
points_in_window = cfg.incident_duration_min / 5  # 5-min cadence
affected_points = int(n_incident_patients * points_in_window)

print(f"\nExpected Impact:")
print(f"   Timepoints per patient: ~{points_per_patient:.0f}")
print(f"   Timepoints in incident window: ~{points_in_window:.0f} per patient")
print(f"   Total affected timepoints: ~{affected_points:,}")
print(f"   % of total data: {affected_points / pseudo_clean.count() * 100:.2f}%")

print(f"\n[SUCCESS] Incident patients selected")

# COMMAND ----------

# DBTITLE 1,Inject calibration bias into glucose_observed
# ------------------------
# Inject calibration bias during incident window
# glucose_true stays unchanged (ground truth)
# glucose_observed gets +40 mg/dL bias during incident
# ------------------------

print("Injecting calibration bias...")
print(f"   Bias: +{cfg.calibration_bias_mgdl} mg/dL")
print(f"   Affected: {cfg.incident_pct*100:.0f}% of patients during incident window\n")

# Drop has_incident from pseudo_clean to avoid ambiguity, then join
pseudo_with_flag = pseudo_clean.drop("has_incident").join(
    incident_patients,
    "patient_id",
    "left"
).fillna({"has_incident": 0})

# Inject bias: Add calibration_bias_mgdl to glucose_observed during incident window.
# Clamp to the physiological CGM range [40, 400] mg/dL (matches 01/04/05) so the biased
# value can't exceed the device's reportable range.
pseudo_incident = pseudo_with_flag.withColumn(
    "glucose_observed",
    F.when(
        (F.col("has_incident") == 1) &
        (F.col("time") >= F.lit(incident_start_ts)) &
        (F.col("time") < F.lit(incident_end_ts)),
        F.greatest(F.least(F.col("glucose_observed") + F.lit(cfg.calibration_bias_mgdl), F.lit(400.0)), F.lit(40.0))
    ).otherwise(F.col("glucose_observed"))
).withColumn(
    "incident_type",
    F.when(
        (F.col("has_incident") == 1) &
        (F.col("time") >= F.lit(incident_start_ts)) &
        (F.col("time") < F.lit(incident_end_ts)),
        F.lit("calibration_bias")
    ).otherwise(F.lit(None).cast("string"))
).withColumn(
    "incident_start_time",
    F.when(F.col("has_incident") == 1, F.lit(incident_start_ts)).otherwise(F.lit(None).cast("timestamp"))
).withColumn(
    "incident_end_time",
    F.when(F.col("has_incident") == 1, F.lit(incident_end_ts)).otherwise(F.lit(None).cast("timestamp"))
).withColumn(
    "incident_bias_mgdl",
    F.when(F.col("has_incident") == 1, F.lit(cfg.calibration_bias_mgdl)).otherwise(F.lit(None).cast("double"))
)

# Save incident data
pseudo_incident.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(pseudo_incident_tbl)

# Verify injection
verify = pseudo_incident.select(
    F.count("*").alias("total_rows"),
    F.sum((F.col("incident_type") == "calibration_bias").cast("int")).alias("biased_points"),
    F.sum(F.col("has_incident")).alias("incident_patient_rows")
).collect()[0]

# Handle None values from SUM() when no matching rows
biased_points = verify['biased_points'] or 0
incident_patient_rows = verify['incident_patient_rows'] or 0
total_rows = verify['total_rows']

print(f"\n[SUCCESS] Incident data saved: {pseudo_incident_tbl}")
print(f"   Total rows: {total_rows:,}")
print(f"   Biased timepoints: {biased_points:,} ({biased_points/total_rows*100:.2f}%)")
print(f"   Incident patient rows: {incident_patient_rows:,}")

# Show sample of biased data
print(f"\nSample of biased data during incident:")
display(pseudo_incident.filter(
    (F.col("incident_type") == "calibration_bias")
).select("patient_id", "time", "glucose_true", "glucose_observed", "incident_type", "incident_bias_mgdl").limit(10))

# COMMAND ----------

# DBTITLE 1,Add prediction labels to incident data
# ------------------------
# Add prediction labels (y_tplus_1, y_tplus_3, y_tplus_6) to incident data
# ------------------------

print("Adding prediction labels to incident data...")

pseudo_incident_df = spark.table(pseudo_incident_tbl)

w = Window.partitionBy("patient_id").orderBy("time")

# Add future glucose values as labels
incident_labeled = pseudo_incident_df
for h in HORIZONS:
    incident_labeled = incident_labeled.withColumn(
        f"y_tplus_{h}",
        F.lead("glucose_true", h).over(w)  # Use glucose_true (ground truth) as label
    )

# Save labeled incident data
incident_labeled_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled"
incident_labeled.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(incident_labeled_tbl)

print(f"\n[SUCCESS] Saved: {incident_labeled_tbl}")
print(f"   Labels added: {', '.join([f'y_tplus_{h}' for h in HORIZONS])}")
print(f"   Rows: {incident_labeled.count():,}")

print(f"\nLabel Summary:")
for h in [3, 6]:  # 15m, 30m
    stats = incident_labeled.select(
        F.avg(f"y_tplus_{h}").alias("mean"),
        F.stddev(f"y_tplus_{h}").alias("std"),
        F.min(f"y_tplus_{h}").alias("min"),
        F.max(f"y_tplus_{h}").alias("max")
    ).collect()[0]
    print(f"   y_tplus_{h} ({h*5}min): mean={stats['mean']:.1f}, std={stats['std']:.1f}, range=[{stats['min']:.0f}, {stats['max']:.0f}]")

print(f"\n[SUCCESS] Ready for feature engineering")

# COMMAND ----------

# DBTITLE 1,Load clean model and run inference on incident data
# ------------------------
# Load CLEAN model and run inference on INCIDENT data
# Goal: Show that good model fails with bad device data
# ------------------------
import mlflow.xgboost
import xgboost as xgb
from sklearn.metrics import mean_absolute_error

print("INFERENCE-ONLY INCIDENT SIMULATION")
print("="*80)
print("\nGoal: Show that clean model (5.8 mg/dL MAE) fails during device calibration bug\n")

# Load clean models (trained on clean data)
print("Loading CLEAN models...")
clean_model_15m = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_15m"
clean_model_30m = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_30m"

mlflow.set_registry_uri('databricks-uc')

bst15_clean = mlflow.xgboost.load_model(f"models:/{clean_model_15m}@Champion")


bst30_clean = mlflow.xgboost.load_model(f"models:/{clean_model_30m}@Champion")

print(f"[SUCCESS] Loaded clean models:")
print(f"   15m: {clean_model_15m}@Champion")
print(f"   30m: {clean_model_30m}@Champion")
print(f"   Baseline performance: 5.8 mg/dL (15m) | 10.4 mg/dL (30m)\n")

# Load incident data and build features
print("Building features from incident data...")
incident_labeled_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled" ### table for viz
df = spark.table(incident_labeled_tbl)

# Join with incident flags - drop has_incident from df first to avoid ambiguity
incident_info = spark.table(pseudo_incident_tbl).select(
    "patient_id", "time", "has_incident", "incident_type"
)
df = df.drop("has_incident").join(incident_info, ["patient_id", "time"], "inner")

# Add incident_active flag
base_date = pd.Timestamp(cfg.demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)

df = df.withColumn(
    "incident_active",
    ((F.col("has_incident") == 1) &
     (F.col("time") >= F.lit(incident_start_ts)) &
     (F.col("time") < F.lit(incident_end_ts))).cast("int")
)

# Build features (same as clean model)
# IMPORTANT: Include glucose_true for visualization
w_ord = Window.partitionBy("patient_id").orderBy("time")

feat = (df.select(
        "patient_id", "time", "incident_active", "has_incident",
        F.col("glucose_true").cast("double").alias("glucose_true"),  # TRUE glucose (ground truth)
        F.col("glucose_observed").cast("double").alias("glucose_observed"),  # OBSERVED glucose (with bias)
        F.col("y_tplus_3").cast("double").alias("y_tplus_3"),
        F.col("y_tplus_6").cast("double").alias("y_tplus_6"),
        F.col("carb_input").cast("double").alias("carb_input"),
        F.col("bolus_volume_delivered").cast("double").alias("bolus_volume_delivered"),
        F.col("basal_rate").cast("double").alias("basal_rate"),
        F.col("steps").cast("double").alias("steps"),
        F.hour("time").cast("int").alias("hour_utc"),
     )
     .withColumn("hour_sin", F.sin(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0)))
     .withColumn("hour_cos", F.cos(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0)))
)

# Add lags
for k in range(1, cfg.lags+1):
    feat = feat.withColumn(f"glucose_lag_{k}", F.lag("glucose_observed", k).over(w_ord))

# Add rolling windows
for rw in cfg.roll_windows:
    w_roll = Window.partitionBy("patient_id").orderBy("time").rowsBetween(-rw+1, 0)
    feat = (feat
      .withColumn(f"g_roll_mean_{rw}", F.avg("glucose_observed").over(w_roll))
      .withColumn(f"g_roll_std_{rw}",  F.stddev("glucose_observed").over(w_roll))
    )

# Add deltas
feat = (feat
  .withColumn("g_delta_1", F.col("glucose_observed") - F.col("glucose_lag_1"))
  .withColumn("g_delta_3", F.col("glucose_observed") - F.col("glucose_lag_3"))
)

# Sample for inference (30% to keep it fast)
feat_sample = feat.sample(False, 0.3, seed=cfg.seed).toPandas()
feat_sample = feat_sample.dropna(subset=[f"glucose_lag_{k}" for k in range(1, cfg.lags+1)] + ["y_tplus_3", "y_tplus_6"])

print(f"[SUCCESS] Features built: {len(feat_sample):,} timepoints")
print(f"   Incident timepoints: {feat_sample['incident_active'].sum():,} ({feat_sample['incident_active'].sum()/len(feat_sample)*100:.1f}%)")

# Prepare feature matrix (exclude glucose_true from features - it's only for visualization)
feature_cols = [c for c in feat_sample.columns if c not in 
                {"patient_id", "time", "incident_active", "has_incident", "glucose_true", "y_tplus_3", "y_tplus_6"}]
X_inference = feat_sample[feature_cols].to_numpy(dtype=np.float32)
d_inference = xgb.DMatrix(X_inference, feature_names=feature_cols)

# Run inference with CLEAN models
print(f"\nRunning inference with CLEAN models on INCIDENT data...")
feat_sample["pred_15m"] = bst15_clean.predict(d_inference)
feat_sample["pred_30m"] = bst30_clean.predict(d_inference)

# Calculate errors
feat_sample["mae_15m"] = np.abs(feat_sample["pred_15m"] - feat_sample["y_tplus_3"])
feat_sample["mae_30m"] = np.abs(feat_sample["pred_30m"] - feat_sample["y_tplus_6"])

print(f"[SUCCESS] Inference complete!")
print(f"\nReady for incident impact analysis...")

# COMMAND ----------

# DBTITLE 1,Incident impact analysis - MAE by time period
# ------------------------
# INCIDENT IMPACT ANALYSIS
# Compare MAE: Before / During / After incident
# ------------------------

print("INCIDENT IMPACT ANALYSIS")
print("="*80)

# Split data by incident period
clean_period = feat_sample[feat_sample['incident_active'] == 0]
incident_period = feat_sample[feat_sample['incident_active'] == 1]

print(f"\nData Split:")
print(f"   Clean period: {len(clean_period):,} timepoints ({len(clean_period)/len(feat_sample)*100:.1f}%)")
print(f"   Incident period: {len(incident_period):,} timepoints ({len(incident_period)/len(feat_sample)*100:.1f}%)")
print(f"   Affected patients: {feat_sample[feat_sample['has_incident']==1]['patient_id'].nunique()}")

if len(incident_period) > 0:
    print("\n" + "="*80)
    print("PREDICTION QUALITY SUMMARY")
    print("="*80)
    
    clean_mae_15m = clean_period['mae_15m'].mean()
    clean_mae_30m = clean_period['mae_30m'].mean()
    incident_mae_15m = incident_period['mae_15m'].mean()
    incident_mae_30m = incident_period['mae_30m'].mean()
    
    print(f"\nCLEAN PERIOD (no device bug):")
    print(f"   MAE: {clean_mae_15m:.1f} mg/dL (15m) | {clean_mae_30m:.1f} mg/dL (30m)")
    print(f"   Status: Normal performance")
    
    print(f"\nINCIDENT PERIOD (+{cfg.calibration_bias_mgdl} mg/dL calibration bug):")
    print(f"   MAE: {incident_mae_15m:.1f} mg/dL (15m) | {incident_mae_30m:.1f} mg/dL (30m)")
    print(f"   Status: CATASTROPHIC FAILURE")
    
    degradation_15m = incident_mae_15m - clean_mae_15m
    degradation_30m = incident_mae_30m - clean_mae_30m
    degradation_pct_15m = (degradation_15m / clean_mae_15m) * 100
    degradation_pct_30m = (degradation_30m / clean_mae_30m) * 100
    
    print(f"\nIMPACT METRICS:")
    print(f"   MAE degradation (15m): +{degradation_15m:.1f} mg/dL ({degradation_pct_15m:.0f}% worse)")
    print(f"   MAE degradation (30m): +{degradation_30m:.1f} mg/dL ({degradation_pct_30m:.0f}% worse)")
    
    # By glucose range
    print(f"\nMAE by Glucose Range (15m):")
    for range_name, condition in [("Hypo (<70)", clean_period['glucose_observed'] < 70),
                                   ("Normal (70-180)", (clean_period['glucose_observed'] >= 70) & (clean_period['glucose_observed'] <= 180)),
                                   ("Hyper (>180)", clean_period['glucose_observed'] > 180)]:
        if condition.sum() > 0:
            clean_mae = clean_period[condition]['mae_15m'].mean()
            print(f"   {range_name:15s}: {clean_mae:.1f} mg/dL (clean period)")
    
    for range_name, condition in [("Hypo (<70)", incident_period['glucose_observed'] < 70),
                                   ("Normal (70-180)", (incident_period['glucose_observed'] >= 70) & (incident_period['glucose_observed'] <= 180)),
                                   ("Hyper (>180)", incident_period['glucose_observed'] > 180)]:
        if condition.sum() > 0:
            incident_mae = incident_period[condition]['mae_15m'].mean()
            print(f"   {range_name:15s}: {incident_mae:.1f} mg/dL (incident period) [ALERT]")
    
else:
    print("\n[WARNING] No incident period data found - check incident injection")

print("\n" + "="*80)
print("KEY FINDINGS")
print("="*80)
print(f"\n[1] Clean model performs excellently on clean data (5.8 mg/dL)")
print(f"[2] Device calibration bug causes CATASTROPHIC failure (~{incident_mae_15m:.0f} mg/dL)")
print(f"[3] MAE increases by {degradation_pct_15m:.0f}% during 3-hour incident")
print(f"[4] Demonstrates critical need for device quality monitoring")
print("="*80)

# COMMAND ----------

# DBTITLE 1,Visualization - MAE spike during incident
# ------------------------
# Visualization: MAE Timeline showing incident spike
# ------------------------
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

print("Visualizing incident impact...\n")

# Prepare timeline data (now includes glucose_true from source data)
timeline_data = feat_sample[["time", "incident_active", "has_incident", "mae_15m", "mae_30m", "glucose_true", "glucose_observed"]].copy()
timeline_data = timeline_data.sort_values("time")

# Aggregate by hour for cleaner visualization
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")

# CRITICAL FIX: Separate aggregation for incident vs clean periods
# During incident: only aggregate affected patients (has_incident=1)
# During clean: aggregate all patients
clean_data = timeline_data[timeline_data['incident_active'] == 0]
incident_data = timeline_data[(timeline_data['incident_active'] == 1) & (timeline_data['has_incident'] == 1)]

# Aggregate clean period (all patients)
clean_agg = clean_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max",
    "glucose_true": "mean",
    "glucose_observed": "mean"
}).reset_index()

# Aggregate incident period (ONLY affected patients)
incident_agg = incident_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max",
    "glucose_true": "mean",
    "glucose_observed": "mean"
}).reset_index()

# Combine: use incident_agg for incident hours, clean_agg for clean hours
hourly_agg = pd.concat([clean_agg, incident_agg]).sort_values("hour").reset_index(drop=True)

print(f"Aggregation strategy:")
print(f"  Clean period: {len(clean_agg)} hours (all patients)")
print(f"  Incident period: {len(incident_agg)} hours (affected patients only)")
print(f"  Total: {len(hourly_agg)} hours")
print(f"\nIncident period MAE (affected patients):")
print(f"  15m: {incident_agg['mae_15m'].mean():.1f} mg/dL")
print(f"  30m: {incident_agg['mae_30m'].mean():.1f} mg/dL")
print()

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Plot 1: MAE Timeline
ax1.plot(hourly_agg["hour"], hourly_agg["mae_15m"], label="MAE 15m", linewidth=2, marker="o", markersize=4)
ax1.plot(hourly_agg["hour"], hourly_agg["mae_30m"], label="MAE 30m", linewidth=2, marker="s", markersize=4)

# Shade incident period (GREY)
incident_hours = hourly_agg[hourly_agg["incident_active"] == 1]
if len(incident_hours) > 0:
    incident_start = incident_hours["hour"].min()
    incident_end = incident_hours["hour"].max() + pd.Timedelta(hours=1)
    incident_mid = incident_start + (incident_end - incident_start) / 2
    
    ax1.axvspan(incident_start, incident_end, alpha=0.2, color='grey', label='Incident Period')
    ax1.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')

ax1.set_ylabel("MAE (mg/dL)", fontsize=12)
ax1.set_title("Incident Impact: MAE Spike During Device Calibration Bug", fontsize=14, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, max(hourly_agg["mae_15m"].max(), hourly_agg["mae_30m"].max()) * 1.1)

# Add yellow box annotation AFTER ylim is set
if len(incident_hours) > 0:
    # Get the actual y-axis limits after they're set
    y_min_ax1, y_max_ax1 = ax1.get_ylim()
    annotation_y = y_max_ax1 * 0.70  # 70% up from bottom
    annotation_x = hourly_agg["hour"].max() - pd.Timedelta(days=1.5)  # Right side
    
    # Target point for arrow (incident spike)
    target_y = max(incident_mae_15m, incident_mae_30m) * 0.85
    
    # Add yellow box with arrow pointing to incident
    ax1.annotate(
        f'MAE during incident:\n{incident_mae_15m:.1f} mg/dL (15m)\n{incident_mae_30m:.1f} mg/dL (30m)',
        xy=(incident_mid, target_y),  # Arrow points here
        xytext=(annotation_x, annotation_y),  # Box positioned here
        fontsize=9,
        fontweight='bold',
        ha='center',
        va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=2, connectionstyle='arc3,rad=0.3')
    )

# Plot 2: Glucose Timeline
# DARKGRAY = True glucose (actual baseline - stays constant) — unified palette w/ Bidirectional sibling
# RED      = Observed glucose (device reading - spikes UP +40 mg/dL during incident, matches positive-cohort red)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_true"], label="True glucose (actual baseline)",
         linewidth=2.5, linestyle='-', color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_observed"], label="Observed glucose (device reading)",
         linewidth=2.5, linestyle='-', color="red", marker="s", markersize=4, alpha=0.9, zorder=3)

# Shade incident period (GREY)
if len(incident_hours) > 0:
    ax2.axvspan(incident_start, incident_end, alpha=0.15, color='grey', label='Incident Period', zorder=1)
    
    # Get incident glucose values for arrow target
    incident_row = hourly_agg[hourly_agg["incident_active"] == 1].iloc[len(hourly_agg[hourly_agg["incident_active"] == 1])//2]
    y_true = incident_row["glucose_true"]
    y_obs = incident_row["glucose_observed"]
    
    # Position yellow box to the RIGHT of incident period at 120 mg/dL
    annotation_y = 120  # Fixed at 120 mg/dL on y-axis
    annotation_x = incident_end + pd.Timedelta(hours=18)  # To the right of incident (0.75 days after)
    
    # Add yellow box with arrow pointing to the gap between lines
    ax2.annotate(
        f'+{cfg.calibration_bias_mgdl:.0f} mg/dL\nbias',
        xy=(incident_mid, (y_true + y_obs) / 2),  # Arrow points to middle of gap
        xytext=(annotation_x, annotation_y),  # Box positioned here
        fontsize=10,
        fontweight='bold',
        ha='center',
        va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=2, connectionstyle='arc3,rad=0.3')
    )

ax2.set_xlabel("Time", fontsize=12)
ax2.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax2.set_title(f"Glucose Timeline: Device Reads +{cfg.calibration_bias_mgdl:.0f} mg/dL HIGH During Incident", fontsize=14, fontweight='bold')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax2.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

plt.tight_layout()
plt.show()

print("[SUCCESS] Visualization complete!")
print(f"\nThe plot clearly shows:")
print(f"   1. MAE is stable at ~5.8 mg/dL during clean periods")
print(f"   2. MAE spikes to ~{incident_mae_15m:.0f} mg/dL during the 3-hour incident")
print(f"   3. MAE returns to ~5.8 mg/dL after incident ends")
print(f"   4. GREEN line (true glucose) = stable baseline throughout")
print(f"   5. RED line (observed) spikes +{cfg.calibration_bias_mgdl:.0f} mg/dL ABOVE green during incident")
print(f"   6. Outside incident: both lines overlap (device reads correctly)")
print(f"\nThis demonstrates the critical impact of device calibration bugs!")

# COMMAND ----------

# DBTITLE 1,MAE Comparison: All Patients vs Affected vs Unaffected
# ------------------------
# MAE Comparison: 3 Separate Views
# 1. All patients (fleet-wide average)
# 2. Affected patients only (true incident impact)
# 3. Unaffected patients only (baseline performance)
# ------------------------
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

print("Creating 3-panel MAE comparison...\n")

# Prepare timeline data
timeline_data = feat_sample[["time", "incident_active", "has_incident", "mae_15m", "mae_30m"]].copy()
timeline_data = timeline_data.sort_values("time")
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")

# 1. All patients aggregation (fleet-wide)
all_patients_agg = timeline_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max"
}).reset_index()

# 2. Affected patients only (has_incident=1)
affected_data = timeline_data[timeline_data['has_incident'] == 1]
affected_agg = affected_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max"
}).reset_index()

# 3. Unaffected patients only (has_incident=0)
unaffected_data = timeline_data[timeline_data['has_incident'] == 0]
unaffected_agg = unaffected_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max"
}).reset_index()

print(f"Aggregation summary:")
print(f"  All patients: {len(all_patients_agg)} hours")
print(f"  Affected patients: {len(affected_agg)} hours")
print(f"  Unaffected patients: {len(unaffected_agg)} hours")
print()

# Get incident period boundaries
incident_hours = all_patients_agg[all_patients_agg["incident_active"] == 1]
if len(incident_hours) > 0:
    incident_start = incident_hours["hour"].min()
    incident_end = incident_hours["hour"].max() + pd.Timedelta(hours=1)
    incident_mid = incident_start + (incident_end - incident_start) / 2

# Create figure with 3 subplots (vertical stack)
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

# ------------------------
# Plot 1: ALL PATIENTS (Fleet-wide average)
# ------------------------
ax1.plot(all_patients_agg["hour"], all_patients_agg["mae_15m"], 
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax1.plot(all_patients_agg["hour"], all_patients_agg["mae_30m"], 
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')

if len(incident_hours) > 0:
    ax1.axvspan(incident_start, incident_end, alpha=0.2, color='grey', label='Incident Period')
    ax1.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    
    # Calculate fleet-wide MAE during incident
    fleet_incident_mae_15m = all_patients_agg[all_patients_agg["incident_active"] == 1]["mae_15m"].mean()
    fleet_incident_mae_30m = all_patients_agg[all_patients_agg["incident_active"] == 1]["mae_30m"].mean()
    
    # Add annotation
    y_max = ax1.get_ylim()[1]
    ax1.annotate(
        f'Fleet-wide MAE:\n{fleet_incident_mae_15m:.1f} mg/dL (15m)\n{fleet_incident_mae_30m:.1f} mg/dL (30m)',
        xy=(incident_mid, fleet_incident_mae_15m),
        xytext=(all_patients_agg["hour"].max() - pd.Timedelta(days=1.5), y_max * 0.70),
        fontsize=9, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=2, connectionstyle='arc3,rad=0.3')
    )

ax1.set_ylabel("MAE (mg/dL)", fontsize=12)
ax1.set_title("1. ALL PATIENTS (Fleet-wide Average) - Diluted Impact", fontsize=13, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, max(all_patients_agg["mae_15m"].max(), all_patients_agg["mae_30m"].max()) * 1.15)

# ------------------------
# Plot 2: AFFECTED PATIENTS ONLY
# ------------------------
ax2.plot(affected_agg["hour"], affected_agg["mae_15m"], 
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax2.plot(affected_agg["hour"], affected_agg["mae_30m"], 
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')

if len(incident_hours) > 0:
    ax2.axvspan(incident_start, incident_end, alpha=0.2, color='grey', label='Incident Period')
    ax2.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    
    # Use impact analysis values for affected patients
    y_max = ax2.get_ylim()[1]
    ax2.annotate(
        f'Affected patients MAE:\n{incident_mae_15m:.1f} mg/dL (15m)\n{incident_mae_30m:.1f} mg/dL (30m)',
        xy=(incident_mid, incident_mae_15m * 0.85),
        xytext=(affected_agg["hour"].max() - pd.Timedelta(days=1.5), incident_mae_15m * 0.70),
        fontsize=9, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=2, connectionstyle='arc3,rad=0.3')
    )

ax2.set_ylabel("MAE (mg/dL)", fontsize=12)
ax2.set_title(f"2. AFFECTED PATIENTS ONLY ({cfg.incident_pct*100:.0f}% of fleet) - True Incident Impact", fontsize=13, fontweight='bold')
ax2.legend(loc='upper left', fontsize=10)
ax2.grid(True, alpha=0.3)
ax2.set_ylim(0, max(affected_agg["mae_15m"].max(), affected_agg["mae_30m"].max()) * 1.15)

# ------------------------
# Plot 3: UNAFFECTED PATIENTS ONLY
# ------------------------
ax3.plot(unaffected_agg["hour"], unaffected_agg["mae_15m"], 
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax3.plot(unaffected_agg["hour"], unaffected_agg["mae_30m"], 
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')

if len(incident_hours) > 0:
    ax3.axvspan(incident_start, incident_end, alpha=0.2, color='grey', label='Incident Period')
    ax3.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    
    # Calculate unaffected MAE during incident period
    unaffected_incident_mae_15m = unaffected_agg[unaffected_agg["incident_active"] == 1]["mae_15m"].mean()
    unaffected_incident_mae_30m = unaffected_agg[unaffected_agg["incident_active"] == 1]["mae_30m"].mean()
    
    # Add annotation
    y_max = ax3.get_ylim()[1]
    ax3.annotate(
        f'Unaffected patients MAE:\n{unaffected_incident_mae_15m:.1f} mg/dL (15m)\n{unaffected_incident_mae_30m:.1f} mg/dL (30m)',
        xy=(incident_mid, unaffected_incident_mae_15m),
        xytext=(unaffected_agg["hour"].max() - pd.Timedelta(days=1.5), y_max * 0.70),
        fontsize=9, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=2, connectionstyle='arc3,rad=0.3')
    )

ax3.set_xlabel("Time", fontsize=12)
ax3.set_ylabel("MAE (mg/dL)", fontsize=12)
ax3.set_title(f"3. UNAFFECTED PATIENTS ONLY ({(1-cfg.incident_pct)*100:.0f}% of fleet) - Stable Performance", fontsize=13, fontweight='bold')
ax3.legend(loc='upper left', fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.set_ylim(0, max(unaffected_agg["mae_15m"].max(), unaffected_agg["mae_30m"].max()) * 1.15)

plt.tight_layout()
plt.show()

print("[SUCCESS] 3-panel MAE comparison complete!")
print(f"\nKey Insights:")
print(f"   1. Fleet-wide (all patients): MAE ~{fleet_incident_mae_15m:.1f} mg/dL during incident")
print(f"      → Diluted by {(1-cfg.incident_pct)*100:.0f}% unaffected patients")
print(f"   2. Affected patients: MAE ~{incident_mae_15m:.1f} mg/dL during incident")
print(f"      → True impact of +{cfg.calibration_bias_mgdl:.0f} mg/dL calibration bias")
print(f"   3. Unaffected patients: MAE ~{unaffected_incident_mae_15m:.1f} mg/dL (stable)")
print(f"      → No device bug, normal performance maintained")
print(f"\nThis demonstrates why patient-level monitoring is critical!")
print(f"Fleet-wide metrics can hide serious issues affecting subsets of patients.")

# COMMAND ----------

# DBTITLE 1,Glucose Timeline Comparison: All vs Affected vs Unaffected
# ------------------------
# Glucose Timeline Comparison: 3 Separate Views
# 1. All patients (fleet-wide average)
# 2. Affected patients only (shows +40 mg/dL bias)
# 3. Unaffected patients only (stable baseline)
# ------------------------
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

print("Creating 3-panel glucose timeline comparison...\n")

# Prepare timeline data with glucose values
timeline_data = feat_sample[["time", "incident_active", "has_incident", "glucose_true", "glucose_observed"]].copy()
timeline_data = timeline_data.sort_values("time")
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")

# 1. All patients aggregation (fleet-wide)
all_patients_glucose = timeline_data.groupby("hour").agg({
    "glucose_true": "mean",
    "glucose_observed": "mean",
    "incident_active": "max"
}).reset_index()

# 2. Affected patients only (has_incident=1)
affected_glucose = timeline_data[timeline_data['has_incident'] == 1].groupby("hour").agg({
    "glucose_true": "mean",
    "glucose_observed": "mean",
    "incident_active": "max"
}).reset_index()

# 3. Unaffected patients only (has_incident=0)
unaffected_glucose = timeline_data[timeline_data['has_incident'] == 0].groupby("hour").agg({
    "glucose_true": "mean",
    "glucose_observed": "mean",
    "incident_active": "max"
}).reset_index()

print(f"Aggregation summary:")
print(f"  All patients: {len(all_patients_glucose)} hours")
print(f"  Affected patients: {len(affected_glucose)} hours")
print(f"  Unaffected patients: {len(unaffected_glucose)} hours")
print()

# Get incident period boundaries
incident_hours = all_patients_glucose[all_patients_glucose["incident_active"] == 1]
if len(incident_hours) > 0:
    incident_start = incident_hours["hour"].min()
    incident_end = incident_hours["hour"].max() + pd.Timedelta(hours=1)
    incident_mid = incident_start + (incident_end - incident_start) / 2

# Create figure with 3 subplots (vertical stack)
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

# ------------------------
# Plot 1: ALL PATIENTS (Fleet-wide average)
# ------------------------
ax1.plot(all_patients_glucose["hour"], all_patients_glucose["glucose_true"],
         label="True glucose (actual baseline)", linewidth=2.5, linestyle='-',
         color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax1.plot(all_patients_glucose["hour"], all_patients_glucose["glucose_observed"], 
         label="Observed glucose (device reading)", linewidth=2.5, linestyle='-', 
         color="red", marker="s", markersize=4, alpha=0.9, zorder=3)

if len(incident_hours) > 0:
    ax1.axvspan(incident_start, incident_end, alpha=0.15, color='grey', label='Incident Period', zorder=1)
    
    # Calculate fleet-wide bias during incident
    fleet_bias = all_patients_glucose[all_patients_glucose["incident_active"] == 1]["glucose_observed"].mean() - \
                 all_patients_glucose[all_patients_glucose["incident_active"] == 1]["glucose_true"].mean()
    
    # Add annotation
    incident_row = all_patients_glucose[all_patients_glucose["incident_active"] == 1].iloc[len(all_patients_glucose[all_patients_glucose["incident_active"] == 1])//2]
    y_true = incident_row["glucose_true"]
    y_obs = incident_row["glucose_observed"]
    
    ax1.annotate(
        f'+{fleet_bias:.1f} mg/dL\nfleet-wide bias',
        xy=(incident_mid, (y_true + y_obs) / 2),
        xytext=(incident_end + pd.Timedelta(hours=18), 120),
        fontsize=10, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=-0.1')
    )

ax1.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax1.set_title("1. ALL PATIENTS (Fleet-wide Average) - Diluted Bias", fontsize=13, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax1.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

# ------------------------
# Plot 2: AFFECTED PATIENTS ONLY
# ------------------------
ax2.plot(affected_glucose["hour"], affected_glucose["glucose_true"],
         label="True glucose (actual baseline)", linewidth=2.5, linestyle='-',
         color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax2.plot(affected_glucose["hour"], affected_glucose["glucose_observed"], 
         label="Observed glucose (device reading)", linewidth=2.5, linestyle='-', 
         color="red", marker="s", markersize=4, alpha=0.9, zorder=3)

if len(incident_hours) > 0:
    ax2.axvspan(incident_start, incident_end, alpha=0.15, color='grey', label='Incident Period', zorder=1)
    
    # Get affected patient glucose during incident
    incident_row = affected_glucose[affected_glucose["incident_active"] == 1].iloc[len(affected_glucose[affected_glucose["incident_active"] == 1])//2]
    y_true = incident_row["glucose_true"]
    y_obs = incident_row["glucose_observed"]
    
    ax2.annotate(
        f'+{cfg.calibration_bias_mgdl:.0f} mg/dL\nbias',
        xy=(incident_mid, (y_true + y_obs) / 2),
        xytext=(incident_end + pd.Timedelta(hours=18), 120),
        fontsize=10, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=-0.1')
    )

ax2.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax2.set_title(f"2. AFFECTED PATIENTS ONLY ({cfg.incident_pct*100:.0f}% of fleet) - Full +{cfg.calibration_bias_mgdl:.0f} mg/dL Bias", fontsize=13, fontweight='bold')
ax2.legend(loc='upper left', fontsize=10)
ax2.grid(True, alpha=0.3)
ax2.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax2.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

# ------------------------
# Plot 3: UNAFFECTED PATIENTS ONLY
# ------------------------
ax3.plot(unaffected_glucose["hour"], unaffected_glucose["glucose_true"],
         label="True glucose (actual baseline)", linewidth=2.5, linestyle='-',
         color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax3.plot(unaffected_glucose["hour"], unaffected_glucose["glucose_observed"],
         label="Observed glucose (device reading)", linewidth=2.5, linestyle='-',
         color="mediumturquoise", marker="s", markersize=4, alpha=0.85, zorder=3)

if len(incident_hours) > 0:
    ax3.axvspan(incident_start, incident_end, alpha=0.15, color='grey', label='Incident Period', zorder=1)
    
    # For unaffected patients, glucose_true and glucose_observed should be identical
    ax3.annotate(
        'No bias\n(device OK)',
        xy=(incident_mid, 140),
        xytext=(incident_end + pd.Timedelta(hours=18), 120),
        fontsize=10, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.7, edgecolor='black', linewidth=1.5),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=-0.1')
    )

ax3.set_xlabel("Time", fontsize=12)
ax3.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax3.set_title(f"3. UNAFFECTED PATIENTS ONLY ({(1-cfg.incident_pct)*100:.0f}% of fleet) - No Device Bug", fontsize=13, fontweight='bold')
ax3.legend(loc='upper left', fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax3.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

plt.tight_layout()
plt.show()

print("[SUCCESS] 3-panel glucose timeline comparison complete!")
print(f"\nKey Insights:")
print(f"   1. Fleet-wide: Bias diluted to ~{fleet_bias:.1f} mg/dL (averaged across all patients)")
print(f"   2. Affected patients: Full +{cfg.calibration_bias_mgdl:.0f} mg/dL bias during incident")
print(f"      → RED line spikes {cfg.calibration_bias_mgdl:.0f} mg/dL above GREEN baseline")
print(f"   3. Unaffected patients: No bias, lines overlap (device working correctly)")
print(f"\nThis shows why patient-level monitoring is critical!")
print(f"Fleet-wide averages can mask serious device issues affecting patient subsets.")

# COMMAND ----------

# DBTITLE 1,Glucose distribution comparison
# ------------------------
# Glucose Distribution Comparison: Baseline vs Clean vs Incident Period
# ------------------------
import matplotlib.pyplot as plt
import seaborn as sns

print("Glucose Distribution Comparison")
print("="*80)

# Get baseline distribution
baseline_df = spark.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data")
baseline_sample = baseline_df.sample(False, 0.1, seed=cfg.seed).toPandas()
baseline_glucose = baseline_sample['glucose'].dropna().values

# Get clean period and incident period glucose
clean_glucose = clean_period['glucose_observed'].values
incident_glucose = incident_period['glucose_observed'].values

print(f"\nSample sizes:")
print(f"   Baseline: {len(baseline_glucose):,} points")
print(f"   Clean period: {len(clean_glucose):,} points")
print(f"   Incident period: {len(incident_glucose):,} points")

# Calculate distribution statistics
print(f"\nDistribution Statistics:")
print(f"\n                    Baseline    Clean       Incident    Shift")
print("-" * 80)
print(f"Mean:               {baseline_glucose.mean():6.1f}      {clean_glucose.mean():6.1f}      {incident_glucose.mean():6.1f}      {incident_glucose.mean() - clean_glucose.mean():+6.1f}")
print(f"Median:             {np.median(baseline_glucose):6.1f}      {np.median(clean_glucose):6.1f}      {np.median(incident_glucose):6.1f}      {np.median(incident_glucose) - np.median(clean_glucose):+6.1f}")
print(f"Std:                {baseline_glucose.std():6.1f}      {clean_glucose.std():6.1f}      {incident_glucose.std():6.1f}      {incident_glucose.std() - clean_glucose.std():+6.1f}")

baseline_hypo = (baseline_glucose < 70).sum() / len(baseline_glucose) * 100
baseline_normal = ((baseline_glucose >= 70) & (baseline_glucose <= 180)).sum() / len(baseline_glucose) * 100
baseline_hyper = (baseline_glucose > 180).sum() / len(baseline_glucose) * 100

clean_hypo = (clean_glucose < 70).sum() / len(clean_glucose) * 100
clean_normal = ((clean_glucose >= 70) & (clean_glucose <= 180)).sum() / len(clean_glucose) * 100
clean_hyper = (clean_glucose > 180).sum() / len(clean_glucose) * 100

incident_hypo = (incident_glucose < 70).sum() / len(incident_glucose) * 100
incident_normal = ((incident_glucose >= 70) & (incident_glucose <= 180)).sum() / len(incident_glucose) * 100
incident_hyper = (incident_glucose > 180).sum() / len(incident_glucose) * 100

print(f"\nHypo (<70):         {baseline_hypo:6.1f}%     {clean_hypo:6.1f}%     {incident_hypo:6.1f}%     {incident_hypo - clean_hypo:+6.1f}%")
print(f"Normal (70-180):    {baseline_normal:6.1f}%     {clean_normal:6.1f}%     {incident_normal:6.1f}%     {incident_normal - clean_normal:+6.1f}%")
print(f"Hyper (>180):       {baseline_hyper:6.1f}%     {clean_hyper:6.1f}%     {incident_hyper:6.1f}%     {incident_hyper - clean_hyper:+6.1f}%")

# Create visualization
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Overlaid histograms
ax1 = axes[0, 0]
ax1.hist(baseline_glucose, bins=80, alpha=0.4, label='Baseline (Real)', density=True, range=(40, 400), color='darkgray')
ax1.hist(clean_glucose, bins=80, alpha=0.4, label='Clean Period', density=True, range=(40, 400), color='mediumturquoise')
ax1.hist(incident_glucose, bins=80, alpha=0.4, label='Incident Period (+40 bias)', density=True, range=(40, 400), color='red')
ax1.axvspan(40, 70, alpha=0.15, color='lightcoral')   # hypo zone — red-family (medical danger convention)
ax1.axvspan(70, 180, alpha=0.1, color='grey')         # normal range
ax1.axvspan(180, 400, alpha=0.15, color='lightblue')  # hyper zone — blue-family
ax1.axvline(70, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax1.axvline(180, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax1.set_xlabel('Glucose (mg/dL)', fontsize=11)
ax1.set_ylabel('Density', fontsize=11)
ax1.set_title('Glucose Distribution: Baseline vs Clean vs Incident', fontsize=12, fontweight='bold')
ax1.legend(loc='upper right', fontsize=10)
ax1.grid(True, alpha=0.3)

# Plot 2: Distribution percentages (bar chart)
ax2 = axes[0, 1]
categories = ['Hypo\n(<70)', 'Normal\n(70-180)', 'Hyper\n(>180)']
baseline_pcts = [baseline_hypo, baseline_normal, baseline_hyper]
clean_pcts = [clean_hypo, clean_normal, clean_hyper]
incident_pcts = [incident_hypo, incident_normal, incident_hyper]

x = np.arange(len(categories))
width = 0.25

ax2.bar(x - width, baseline_pcts, width, label='Baseline', alpha=0.8, color='darkgray')
ax2.bar(x, clean_pcts, width, label='Clean Period', alpha=0.8, color='mediumturquoise')
ax2.bar(x + width, incident_pcts, width, label='Incident Period', alpha=0.8, color='red')
ax2.set_ylabel('Percentage (%)', fontsize=11)
ax2.set_title('Distribution by Glucose Range', fontsize=12, fontweight='bold')
ax2.set_xticks(x)
ax2.set_xticklabels(categories)
ax2.legend(fontsize=10)
ax2.grid(True, alpha=0.3, axis='y')

# Add percentage labels
for i, (b, c, inc) in enumerate(zip(baseline_pcts, clean_pcts, incident_pcts)):
    ax2.text(i - width, b + 1, f'{b:.1f}%', ha='center', fontsize=8)
    ax2.text(i, c + 1, f'{c:.1f}%', ha='center', fontsize=8)
    ax2.text(i + width, inc + 1, f'{inc:.1f}%', ha='center', fontsize=8)

# Plot 3: Cumulative distribution
ax3 = axes[1, 0]
baseline_sorted = np.sort(baseline_glucose)
clean_sorted = np.sort(clean_glucose)
incident_sorted = np.sort(incident_glucose)

baseline_cdf = np.arange(1, len(baseline_sorted) + 1) / len(baseline_sorted)
clean_cdf = np.arange(1, len(clean_sorted) + 1) / len(clean_sorted)
incident_cdf = np.arange(1, len(incident_sorted) + 1) / len(incident_sorted)

ax3.plot(baseline_sorted, baseline_cdf, label='Baseline', linewidth=2, color='darkgray')
ax3.plot(clean_sorted, clean_cdf, label='Clean Period', linewidth=2, color='mediumturquoise')
ax3.plot(incident_sorted, incident_cdf, label='Incident Period', linewidth=2, color='red')
ax3.axvline(70, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax3.axvline(180, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax3.set_xlabel('Glucose (mg/dL)', fontsize=11)
ax3.set_ylabel('Cumulative Probability', fontsize=11)
ax3.set_title('Cumulative Distribution Function', fontsize=12, fontweight='bold')
ax3.legend(fontsize=10)
ax3.grid(True, alpha=0.3)
ax3.set_xlim(40, 400)

# Plot 4: Box plots
ax4 = axes[1, 1]
box_data = [baseline_glucose, clean_glucose, incident_glucose]
box_labels = ['Baseline', 'Clean\nPeriod', 'Incident\nPeriod']
box_colors = ['darkgray', 'mediumturquoise', 'red']

bp = ax4.boxplot(box_data, labels=box_labels, patch_artist=True, widths=0.6)
for patch, color in zip(bp['boxes'], box_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.6)

ax4.axhline(y=70, color='red', linestyle='--', linewidth=1, alpha=0.5, label='Hypo threshold')
ax4.axhline(y=180, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='Hyper threshold')
ax4.set_ylabel('Glucose (mg/dL)', fontsize=11)
ax4.set_title('Glucose Distribution Box Plots', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3, axis='y')
ax4.legend(fontsize=9, loc='upper right')

plt.tight_layout()
plt.show()

print("\n" + "="*80)
print("DISTRIBUTION IMPACT SUMMARY")
print("="*80)

print(f"\nClean Period vs Baseline:")
print(f"   Mean shift: {clean_glucose.mean() - baseline_glucose.mean():+.1f} mg/dL (should be ~0)")
print(f"   Distribution match: {'[OK] Good' if abs(clean_glucose.mean() - baseline_glucose.mean()) < 5 else '[WARNING] Check'}")

print(f"\nIncident Period vs Clean Period:")
print(f"   Mean shift: {incident_glucose.mean() - clean_glucose.mean():+.1f} mg/dL (expected: +{cfg.calibration_bias_mgdl})")
print(f"   Hypo reduction: {incident_hypo - clean_hypo:+.1f}% (bias shifts distribution up)")
print(f"   Hyper increase: {incident_hyper - clean_hyper:+.1f}% (more high glucose readings)")

print(f"\nKey Observations:")
print(f"   [1] Clean period matches baseline distribution")
print(f"   [2] Incident period shows clear +{incident_glucose.mean() - clean_glucose.mean():.0f} mg/dL shift")
print(f"   [3] Calibration bias affects entire distribution")
print(f"   [4] This explains the MAE spike ({clean_mae_15m:.1f} to {incident_mae_15m:.1f} mg/dL)")
print("="*80)

# COMMAND ----------

# DBTITLE 1,Summary statistics
# ------------------------
# Summary Statistics Table
# ------------------------

print("INCIDENT SIMULATION SUMMARY")
print("="*80)

# Create summary table
summary_data = [
    {
        "Period": "Before Incident",
        "Timepoints": str(len(clean_period)),
        "MAE 15m (mg/dL)": f"{clean_mae_15m:.1f}",
        "MAE 30m (mg/dL)": f"{clean_mae_30m:.1f}",
        "Status": "[OK] Normal"
    },
    {
        "Period": "During Incident",
        "Timepoints": str(len(incident_period)),
        "MAE 15m (mg/dL)": f"{incident_mae_15m:.1f}",
        "MAE 30m (mg/dL)": f"{incident_mae_30m:.1f}",
        "Status": "[FAIL] FAILURE"
    },
    {
        "Period": "Degradation",
        "Timepoints": "-",
        "MAE 15m (mg/dL)": f"+{degradation_15m:.1f} ({degradation_pct_15m:.0f}%)",
        "MAE 30m (mg/dL)": f"+{degradation_30m:.1f} ({degradation_pct_30m:.0f}%)",
        "Status": "Impact"
    }
]

summary_df = pd.DataFrame(summary_data)
display(summary_df)

print("\n" + "="*80)
print("INCIDENT DETAILS")
print("="*80)
print(f"\nIncident Window:")
print(f"   Start: {incident_start_ts}")
print(f"   End: {incident_end_ts}")
print(f"   Duration: {cfg.incident_duration_min} minutes ({cfg.incident_duration_min/60:.1f} hours)")

print(f"\nAffected Population:")
print(f"   Total patients: 1000")
print(f"   Incident patients: {feat_sample[feat_sample['has_incident']==1]['patient_id'].nunique()} ({cfg.incident_pct*100:.0f}%)")
print(f"   Clean patients: {feat_sample[feat_sample['has_incident']==0]['patient_id'].nunique()} ({(1-cfg.incident_pct)*100:.0f}%)")

print(f"\nDevice Issue:")
print(f"   Type: Calibration bias")
print(f"   Magnitude: +{cfg.calibration_bias_mgdl} mg/dL systematic error")
print(f"   Impact: {degradation_pct_15m:.0f}% MAE increase")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print(f"\nEven an excellent model (5.8 mg/dL MAE) fails catastrophically")
print(f"when device calibration is compromised. During the 3-hour incident:")
print(f"\n  * MAE increased from {clean_mae_15m:.1f} to {incident_mae_15m:.1f} mg/dL ({degradation_pct_15m:.0f}% worse)")
print(f"  * {cfg.incident_pct*100:.0f}% of patients affected")
print(f"  * Performance returned to normal after incident ended")
print(f"\n[CRITICAL] This demonstrates the critical importance of:")
print(f"  1. Real-time device quality monitoring")
print(f"  2. Automated anomaly detection")
print(f"  3. Rapid incident response protocols")
print("="*80)

# COMMAND ----------

# DBTITLE 1,Compare clean vs incident model performance
# ------------------------
# INCIDENT IMPACT ANALYSIS
# Compare: Clean model vs Incident model on incident data
# NOTE: This cell requires incident-trained models to exist
# ------------------------
import mlflow.xgboost

print("INCIDENT IMPACT ANALYSIS")
print("="*80)

# Load clean models
print("Loading clean models...")
clean_15m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_15m_clean}@Champion")
clean_30m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_30m_clean}@Champion")
print(f"[SUCCESS] Loaded clean models: {uc_model_fqn_15m_clean}, {uc_model_fqn_30m_clean}")

# Try to load incident models
try:
    print(f"\nLoading incident models...")
    incident_15m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_15m}@Champion")
    incident_30m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_30m}@Champion")
    print(f"[SUCCESS] Loaded incident models: {uc_model_fqn_15m}, {uc_model_fqn_30m}")
    has_incident_models = True
except Exception as e:
    print(f"\n⚠️  Incident models not found: {uc_model_fqn_15m}")
    print(f"   Error: {str(e)}")
    print(f"\n[INFO] This is an INFERENCE-ONLY notebook.")
    print(f"   Incident models need to be trained first (cells 10+).")
    print(f"   Skipping model comparison - only clean model analysis available.")
    print(f"\n   To train incident models: Run cells 10-20 in this notebook.")
    print("="*80)
    has_incident_models = False

if not has_incident_models:
    print("\n[SKIPPED] Model comparison requires incident-trained models.")
    print("   Current analysis (cells 11-13) shows clean model performance on incident data.")
else:
    # Get incident data with flags - drop has_incident from left table to avoid ambiguity
    incident_labeled_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled"
    incident_data = spark.table(incident_labeled_tbl).drop("has_incident").join(
        spark.table(pseudo_incident_tbl).select("patient_id", "time", "has_incident", "incident_type"),
        ["patient_id", "time"],
        "inner"
    )

    # Calculate incident window
    base_date = pd.Timestamp(cfg.demo_week_start)
    incident_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
    incident_end_ts = incident_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)

    # Add incident_active flag
    incident_data = incident_data.withColumn(
        "incident_active",
        ((F.col("has_incident") == 1) &
         (F.col("time") >= F.lit(incident_start_ts)) &
         (F.col("time") < F.lit(incident_end_ts))).cast("int")
    )

    # Build features for prediction
    w_ord = Window.partitionBy("patient_id").orderBy("time")
    feat_for_pred = incident_data.select(
        "patient_id", "time", "incident_active", "has_incident",
        F.col("glucose_observed").cast("double").alias("glucose_observed"),
        F.col("y_tplus_3").cast("double").alias("y_tplus_3"),
        F.col("y_tplus_6").cast("double").alias("y_tplus_6"),
        F.col("carb_input").cast("double").alias("carb_input"),
        F.col("bolus_volume_delivered").cast("double").alias("bolus_volume_delivered"),
        F.col("basal_rate").cast("double").alias("basal_rate"),
        F.col("steps").cast("double").alias("steps"),
        F.hour("time").cast("int").alias("hour_utc"),
    ).withColumn("hour_sin", F.sin(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0))) \
     .withColumn("hour_cos", F.cos(2*F.lit(np.pi)*F.col("hour_utc")/F.lit(24.0)))

    # Add lags and rolling windows
    for k in range(1, cfg.lags+1):
        feat_for_pred = feat_for_pred.withColumn(f"glucose_lag_{k}", F.lag("glucose_observed", k).over(w_ord))

    for rw in cfg.roll_windows:
        w_roll = Window.partitionBy("patient_id").orderBy("time").rowsBetween(-rw+1, 0)
        feat_for_pred = (feat_for_pred
          .withColumn(f"g_roll_mean_{rw}", F.avg("glucose_observed").over(w_roll))
          .withColumn(f"g_roll_std_{rw}",  F.stddev("glucose_observed").over(w_roll))
        )

    feat_for_pred = (feat_for_pred
      .withColumn("g_delta_1", F.col("glucose_observed") - F.col("glucose_lag_1"))
      .withColumn("g_delta_3", F.col("glucose_observed") - F.col("glucose_lag_3"))
    )

    # Sample for comparison
    comparison_pd = feat_for_pred.sample(False, 0.3, seed=cfg.seed).toPandas()
    comparison_pd = comparison_pd.dropna(subset=[f"glucose_lag_{k}" for k in range(1, cfg.lags+1)] + ["y_tplus_3", "y_tplus_6"])

    X_comp = comparison_pd[feature_cols].to_numpy(dtype=np.float32)
    dcomp = xgb.DMatrix(X_comp, feature_names=feature_cols)

    # Predictions from both models
    comparison_pd["pred_15m_clean"] = clean_15m.predict(dcomp)
    comparison_pd["pred_30m_clean"] = clean_30m.predict(dcomp)
    comparison_pd["pred_15m_incident"] = incident_15m.predict(dcomp)
    comparison_pd["pred_30m_incident"] = incident_30m.predict(dcomp)

    # Calculate errors
    comparison_pd["mae_15m_clean"] = np.abs(comparison_pd["pred_15m_clean"] - comparison_pd["y_tplus_3"])
    comparison_pd["mae_30m_clean"] = np.abs(comparison_pd["pred_30m_clean"] - comparison_pd["y_tplus_6"])
    comparison_pd["mae_15m_incident"] = np.abs(comparison_pd["pred_15m_incident"] - comparison_pd["y_tplus_3"])
    comparison_pd["mae_30m_incident"] = np.abs(comparison_pd["pred_30m_incident"] - comparison_pd["y_tplus_6"])

    # Split by incident period
    clean_period_comp = comparison_pd[comparison_pd['incident_active'] == 0]
    incident_period_comp = comparison_pd[comparison_pd['incident_active'] == 1]

    print("\n" + "="*80)
    print("INCIDENT IMPACT SUMMARY")
    print("="*80)

    print(f"\nData split:")
    print(f"   Clean period: {len(clean_period_comp):,} timepoints")
    print(f"   Incident period: {len(incident_period_comp):,} timepoints ({len(incident_period_comp)/len(comparison_pd)*100:.1f}%)")

    if len(incident_period_comp) > 0:
        print(f"\nCLEAN PERIOD (no bias):")
        print(f"   Clean model MAE:    {clean_period_comp['mae_15m_clean'].mean():.2f} mg/dL (15m) | {clean_period_comp['mae_30m_clean'].mean():.2f} mg/dL (30m)")
        print(f"   Incident model MAE: {clean_period_comp['mae_15m_incident'].mean():.2f} mg/dL (15m) | {clean_period_comp['mae_30m_incident'].mean():.2f} mg/dL (30m)")
        
        print(f"\nINCIDENT PERIOD (+{cfg.calibration_bias_mgdl} mg/dL bias):")
        print(f"   Clean model MAE:    {incident_period_comp['mae_15m_clean'].mean():.2f} mg/dL (15m) | {incident_period_comp['mae_30m_clean'].mean():.2f} mg/dL (30m)")
        print(f"   Incident model MAE: {incident_period_comp['mae_15m_incident'].mean():.2f} mg/dL (15m) | {incident_period_comp['mae_30m_incident'].mean():.2f} mg/dL (30m)")
        
        # Calculate impact
        clean_degradation_15m = incident_period_comp['mae_15m_clean'].mean() - clean_period_comp['mae_15m_clean'].mean()
        incident_improvement_15m = incident_period_comp['mae_15m_clean'].mean() - incident_period_comp['mae_15m_incident'].mean()
        
        print(f"\nIMPACT METRICS:")
        print(f"   Clean model degradation during incident: +{clean_degradation_15m:.2f} mg/dL (15m)")
        print(f"   Incident model improvement during incident: -{incident_improvement_15m:.2f} mg/dL (15m)")
        print(f"   Incident model adapts to bias: {incident_improvement_15m/clean_degradation_15m*100:.1f}% recovery")
    else:
        print("\n[WARNING] No incident period data found - check incident injection")

    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)
    print(f"\n[1] Clean model performs well on clean data (~5.8 mg/dL)")
    print(f"[2] Clean model FAILS during incident (~40+ mg/dL MAE spike)")
    print(f"[3] Incident-trained model partially adapts to bias")
    print(f"[4] Demonstrates importance of device quality monitoring")
    print("="*80)

# COMMAND ----------

# DBTITLE 1,Fleet Forecast Table (Demo Output)
# ------------------------
# Fleet forecast NOW using registered models
# Anchor at each patient's LATEST reading (genuinely near-term; agrees with the Coach chart end)
# Filter out clipped floor values (glucose_observed <= 40)
# ------------------------
import mlflow.xgboost

# Load CLEAN models (not incident models - this is inference-only notebook)
m15_uri = f"models:/{uc_model_fqn_15m_clean}@Champion"
m30_uri = f"models:/{uc_model_fqn_30m_clean}@Champion"

bst15 = mlflow.xgboost.load_model(m15_uri)
bst30 = mlflow.xgboost.load_model(m30_uri)

print(f"[SUCCESS] Loaded clean models:")
print(f"   15m: {uc_model_fqn_15m_clean}@Champion")
print(f"   30m: {uc_model_fqn_30m_clean}@Champion")

# Use the features DataFrame built in cell 12 instead of reading from non-existent table
df = feat

# Calculate day_idx for each patient
w = Window.partitionBy("patient_id")
df_with_day = (df
  .withColumn("t0", F.min("time").over(w))
  .withColumn("day_idx", F.floor((F.unix_timestamp("time") - F.unix_timestamp("t0")) / (24*3600)).cast("int"))
  .drop("t0")
)

# Forecast anchor = each patient's LATEST reading (genuinely near-term; agrees with the
# Coach 7-day chart end). Was: a random day-3-5 mid-timeline point. Exclude clamped-floor
# readings (glucose_observed <= 40) as the anchor — floor artifacts, not a "current" value.
w_latest = Window.partitionBy("patient_id").orderBy(F.col("time").desc())
fleet_sample = (df_with_day
  .filter(F.col("glucose_observed") > 40)  # skip clamped-floor artifacts as the anchor
  .withColumn("rn", F.row_number().over(w_latest))
  .filter("rn=1")
  .drop("rn", "day_idx")
)

fleet_pd = fleet_sample.toPandas()
X_fleet = fleet_pd[feature_cols].to_numpy(dtype=np.float32)
dfleet = xgb.DMatrix(X_fleet, feature_names=feature_cols)

# Clamp model predictions to the physiological CGM range [40, 400] (matches observed clamp).
fleet_pd["pred_15m"] = np.clip(bst15.predict(dfleet), 40, 400)
fleet_pd["pred_30m"] = np.clip(bst30.predict(dfleet), 40, 400)
fleet_pd["delta_15m"] = fleet_pd["pred_15m"] - fleet_pd["glucose_observed"]
fleet_pd["delta_30m"] = fleet_pd["pred_30m"] - fleet_pd["glucose_observed"]

fleet_output = fleet_pd[["patient_id","time","glucose_observed","pred_15m","pred_30m","delta_15m","delta_30m",
                         "carb_input","bolus_volume_delivered","basal_rate","steps"]].copy()

spark.createDataFrame(fleet_output).write.mode("overwrite").option("overwriteSchema","true").saveAsTable(fleet_forecast_tbl)

print(f"\n[SUCCESS] Saved: {fleet_forecast_tbl}")
print(f"   Patients: {len(fleet_output):,}")
print(f"   Glucose range: [{fleet_output['glucose_observed'].min():.0f}, {fleet_output['glucose_observed'].max():.0f}] mg/dL")
print(f"   Average glucose: {fleet_output['glucose_observed'].mean():.1f} mg/dL")
print(f"   Patients at 40 mg/dL: {(fleet_output['glucose_observed'] == 40).sum()} (should be 0)")
print(f"\nAnchor: each patient's LATEST reading, glucose > 40 mg/dL")
print(f"   * Near-term forecast from the most recent point (matches the Coach 7-day chart end)")
print(f"   * Excludes clamped floor values (data artifacts)")

display(spark.table(fleet_forecast_tbl).orderBy(F.desc("delta_30m")).limit(20))

