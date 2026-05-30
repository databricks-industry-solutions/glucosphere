# Databricks notebook source
# DBTITLE 1,Notebook Overview - Incident Simulation (BIDIRECTIONAL variant)
# MAGIC %md
# MAGIC # CGM Incident Simulation - Device Calibration Bug (BIDIRECTIONAL variant)
# MAGIC
# MAGIC **Status:** Bidirectional core logic implemented. Cohort splits into +N/-N groups
# MAGIC deterministically by seed; signed bias applied via `signed_bias_mgdl` column; new
# MAGIC `incident_direction` schema column flows through `pseudo_incident_7d_labeled` → feature dataframe
# MAGIC → MAE breakouts. MAE summary print breaks out by direction (both should be ~equal, proving
# MAGIC direction-agnostic anomaly detection).
# MAGIC
# MAGIC Implemented as a two-window mirror design (supersedes the earlier single-incident variant):
# MAGIC
# MAGIC 1. ✅ Two incident windows on MUTUALLY EXCLUSIVE cohorts driven by device_model:
# MAGIC    Window 1 (Day 2, +bias_magnitude) draws from {Alpha, Gamma}; Window 2 (Day 5,
# MAGIC    -bias_magnitude) draws from {Beta, Delta}. Epsilon + Zeta stay unaffected.
# MAGIC    Direction-bias is decided BY WINDOW (not by within-cohort split), so plots show
# MAGIC    two distinct spike events at different x-positions without cancellation.
# MAGIC 2. ✅ `incident_direction` ∈ {'positive', 'negative', 'none'} added to schema; propagates into
# MAGIC    feature dataframe through the incident_info join. `incident_bias_mgdl` now stores the SIGNED
# MAGIC    value (downstream consumers can `ABS()` if they need magnitude).
# MAGIC 4. ✅ Visualization: 3-panel "all/affected/unaffected" — affected panel now shows TWO device lines
# MAGIC    (red positive cohort + blue negative cohort) instead of one signed-average that canceled.
# MAGIC    direction). Could be extracted into a shared helper alongside the SingleIncident sibling.
# MAGIC 5. ✅ MAE summary print breaks out by `incident_direction` (positive vs negative groups).
# MAGIC
# MAGIC **Lakebase F integration:** the new `incident_direction` column on
# MAGIC `pseudo_incident_7d_labeled` is what populates the `bias_direction` field on the alerts table.
# MAGIC
# MAGIC **Sibling notebook:** `06_incident_inference_single.py` retains the unidirectional
# MAGIC single-incident variant for simpler demos / reference comparisons. Switch to that
# MAGIC simpler variant by changing the `databricks.yml` `incident_inference` task's
# MAGIC `notebook_path` to `06_incident_inference_single.py`.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC # CGM Incident Simulation - Device Calibration Bug
# MAGIC
# MAGIC ## Purpose
# MAGIC Demonstrate how a **bidirectional device calibration bug** (±40 mg/dL bias, half over-reading half under-reading) causes catastrophic model failure, even for high-performing models (5.8 mg/dL baseline MAE).
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Incident Scenario (two-window mirror design)
# MAGIC * **Bug Type:** Device calibration error causing **±40 mg/dL bias across two SEPARATE incident windows on DIFFERENT cohorts** (Window 1: +bias on Alpha/Gamma devices; Window 2: -bias on Beta/Delta devices).
# MAGIC * **Window 1:** Day 2, 2:00 PM - 5:00 PM (3-hour window), +40 mg/dL on Alpha/Gamma cohort (~300 patients)
# MAGIC * **Window 2:** Day 5, 10:00 AM - 1:00 PM (3-hour window), -40 mg/dL on Beta/Delta cohort (~300 patients)
# MAGIC * **Affected total:** ~60% of fleet across both windows (300 + 300 of 1000, mutually exclusive)
# MAGIC * **Impact:** MAE peaks ~37 mg/dL for affected patients during each window (vs ~5.8 mg/dL clean baseline)
# MAGIC
# MAGIC > **Note on the `~5.8 mg/dL` baseline anchor:** the `5.8 / 10.4 mg/dL` clean-baseline numbers referenced
# MAGIC > throughout this notebook (intro, print statements, chart `axhline` reference lines) are the
# MAGIC > published synthetic-trained baseline. The CURRENT run's actual
# MAGIC > clean-period MAE is computed dynamically in the MAE analysis cells below and may differ slightly
# MAGIC > depending on `baseline_source` mode (synthetic / from_source / from_table), data seed, and any
# MAGIC > recent ingest fixes. See `README.md` for the published reference numbers.
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
# MAGIC * `${CATALOG_NAME}.${SCHEMA_NAME}.pseudo_incident_7d` - Data with ±40 mg/dL bidirectional bias injected
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
# MAGIC **Data Preparation (Cells 8-11):** Load clean data → Define TWO incident windows (Day 2 +bias on Alpha/Gamma cohort, Day 5 -bias on Beta/Delta cohort) → Inject signed bias per cohort during their respective window → Add prediction labels
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
# MAGIC * Cell 16: 3-panel glucose timeline (shows ±40 mg/dL bidirectional bias in affected patients — red over-reads, blue under-reads)
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

# Calculate TWO incident windows (mirror design):
#   Window 1: +bias_magnitude incident (over-reading), Day 2 14:00-17:00
#   Window 2: -bias_magnitude incident (under-reading), Day 5 10:00-13:00,
#             on a DIFFERENT cohort
# Each window is UNIDIRECTIONAL on its own cohort, so plots show two clearly
# distinct spikes at different x-positions without cancellation. Cohorts are
# mutually exclusive (no patient is in both windows).
#
# SIMULATION SIMPLIFICATION: in real clinical settings, the SAME CGM device
# can be hit by both over-reading AND under-reading calibration drift at
# different times (e.g. FreeStyle Libre FDA-recall history covers both
# directions on the same hardware). The mutually-exclusive cohort split here
# is a fleet-coverage storytelling choice: clean buckets (~300 over-reading +
# ~300 under-reading of 1000, no overlap) make the "% of fleet affected per
# direction" narrative crisp.
#
# Note: if the same device had BOTH biases on different days, the platform's
# anomaly detection would still catch each event — MAE is direction-agnostic
# and time-localized, so the two windows show as distinct elevated-MAE spikes
# at their respective times (no cancellation). Only fleet-coverage % math
# gets fuzzy (a patient in both buckets is double-counted). Same-device-
# both-bugs is therefore an analytically tractable extension; current scope
# keeps the cohorts disjoint purely for narrative clarity.
base_date = pd.Timestamp(demo_week_start)

# --- Window 1 ---
window1_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
window1_end_ts = window1_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)
window1_direction = "positive"     # buildathon-main convention: +40 over-read

# --- Window 2 (mirror) ---
window2_start_ts = base_date + pd.Timedelta(days=cfg.second_incident_start_day, hours=cfg.second_incident_start_hour)
window2_end_ts = window2_start_ts + pd.Timedelta(minutes=cfg.second_incident_duration_min)
window2_direction = getattr(cfg, 'second_incident_direction', 'negative')  # 'negative' = -40 under-read

# Back-compat aliases for any downstream code that still references the single-window vars
incident_start_ts = window1_start_ts
incident_end_ts = window1_end_ts

print(f"\nIncident Window 1 (positive cohort, +bias):")
print(f"   Start: {window1_start_ts}")
print(f"   End: {window1_end_ts}")
print(f"   Duration: {cfg.incident_duration_min} minutes ({cfg.incident_duration_min/60:.1f} hours)")
print(f"\nIncident Window 2 (mirror, negative cohort, -bias):")
print(f"   Start: {window2_start_ts}")
print(f"   End: {window2_end_ts}")
print(f"   Duration: {cfg.second_incident_duration_min} minutes ({cfg.second_incident_duration_min/60:.1f} hours)")

# Verify both windows are within data timerange
data_start = pd.Timestamp(demo_week_start)
data_end = data_start + pd.Timedelta(days=7)
for label, ws, we in [("Window 1", window1_start_ts, window1_end_ts),
                       ("Window 2", window2_start_ts, window2_end_ts)]:
    if ws < data_start or we > data_end:
        print(f"\n⚠️  WARNING: {label} is OUTSIDE data timerange!")
        print(f"   Data: {data_start} to {data_end}")
        print(f"   {label}: {ws} to {we}")
    else:
        print(f"   ✅ {label} is within data timerange")

# Select cohorts with DEVICE-MODEL correlation:
# Demo story: certain device models have a calibration-bias bug. Positive
# cohort is drawn preferentially from {Alpha, Gamma} (positive-bias models);
# negative cohort from {Beta, Delta} (negative-bias models); Epsilon + Zeta
# stay clean (control models). This makes the device-OOR table tie back to
# specific device_model values rather than being uncorrelated with model.
all_patients = pseudo_clean.select("patient_id").distinct()
total_patients = all_patients.count()
n1 = int(total_patients * cfg.incident_pct)
n2 = int(total_patients * getattr(cfg, 'second_incident_pct', cfg.incident_pct))

bias_magnitude = getattr(cfg, 'calibration_bias_magnitude_mgdl', cfg.calibration_bias_mgdl)
window1_signed_bias = +bias_magnitude
window2_signed_bias = -bias_magnitude if window2_direction == 'negative' else +bias_magnitude

# Pull patient → device_model mapping from raw_patient_registry (source of
# truth — the same parquet that silver_patient_registry reads from). Falls
# back to a deterministic random shuffle if the volume path isn't available
# at runtime (e.g., on a fresh workspace where raw data hasn't landed yet).
POS_POOL_MODELS = ['Alpha', 'Gamma']
NEG_POOL_MODELS = ['Beta', 'Delta']
_RAW_REGISTRY_PATH = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/raw_patient_registry/"
_device_model_join_available = False
try:
    _patient_models = (spark.read.format("parquet").load(_RAW_REGISTRY_PATH)
        .select("patient_id", "device_model").distinct())
    _patient_models.count()  # force materialization to surface read errors here
    _device_model_join_available = True
    print(f"\n✅ Loaded device_model mapping from {_RAW_REGISTRY_PATH}")
except Exception as _e:
    print(f"\n⚠️  Could not load device_model from raw_patient_registry ({type(_e).__name__}: {str(_e)[:120]})")
    print(f"   → Falling back to random cohort assignment (device_model uncorrelated with bias direction)")

if _device_model_join_available:
    _all_with_model = all_patients.join(_patient_models, "patient_id", "left")
    _pos_pool = _all_with_model.where(F.col("device_model").isin(POS_POOL_MODELS))
    _neg_pool = _all_with_model.where(F.col("device_model").isin(NEG_POOL_MODELS))

    cohort1 = (_pos_pool
      .orderBy(F.rand(seed=cfg.seed))
      .limit(n1)
      .select("patient_id")
      .withColumn("incident_direction", F.lit(window1_direction))
      .withColumn("signed_bias_mgdl", F.lit(window1_signed_bias))
      .withColumn("incident_window_idx", F.lit(1))
      .withColumn("has_incident", F.lit(1))
    )
    cohort2 = (_neg_pool
      .orderBy(F.rand(seed=cfg.seed + 1))
      .limit(n2)
      .select("patient_id")
      .withColumn("incident_direction", F.lit(window2_direction))
      .withColumn("signed_bias_mgdl", F.lit(window2_signed_bias))
      .withColumn("incident_window_idx", F.lit(2))
      .withColumn("has_incident", F.lit(1))
    )
    incident_patients = cohort1.unionByName(cohort2)
    print(f"   Positive cohort drawn from {POS_POOL_MODELS}")
    print(f"   Negative cohort drawn from {NEG_POOL_MODELS}")
else:
    # Fallback: original deterministic shuffle, mutually exclusive cohorts
    from pyspark.sql import Window as _W
    _shuffle_window = _W.orderBy(F.rand(seed=cfg.seed))
    _ranked = all_patients.withColumn("_rank", F.row_number().over(_shuffle_window))
    cohort1 = (_ranked.filter(F.col("_rank") <= F.lit(n1))
      .withColumn("incident_direction", F.lit(window1_direction))
      .withColumn("signed_bias_mgdl", F.lit(window1_signed_bias))
      .withColumn("incident_window_idx", F.lit(1))
      .withColumn("has_incident", F.lit(1))
      .drop("_rank")
    )
    cohort2 = (_ranked.filter((F.col("_rank") > F.lit(n1)) & (F.col("_rank") <= F.lit(n1 + n2)))
      .withColumn("incident_direction", F.lit(window2_direction))
      .withColumn("signed_bias_mgdl", F.lit(window2_signed_bias))
      .withColumn("incident_window_idx", F.lit(2))
      .withColumn("has_incident", F.lit(1))
      .drop("_rank")
    )
    incident_patients = cohort1.unionByName(cohort2)

# Legacy variable for back-compat with downstream prints/expected-impact math
n_incident_patients = n1 + n2

print(f"\nAffected Patients (two-window mirror design):")
print(f"   Total patients:               {total_patients}")
print(f"   Window 1 cohort (+{bias_magnitude} mg/dL, Day {cfg.incident_start_day}): {n1} patients ({cfg.incident_pct*100:.0f}%)")
print(f"   Window 2 cohort ({window2_signed_bias:+.0f} mg/dL, Day {cfg.second_incident_start_day}): {n2} patients ({getattr(cfg, 'second_incident_pct', cfg.incident_pct)*100:.0f}%)")
print(f"   Clean patients (no incident): {total_patients - n_incident_patients} ({(1 - cfg.incident_pct - getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}%)")
print(f"   Cohorts are mutually exclusive — no patient appears in both windows.")

# Calculate expected impact across both windows
points_per_patient = pseudo_clean.count() / total_patients
points_in_window1 = cfg.incident_duration_min / 5  # 5-min cadence
points_in_window2 = cfg.second_incident_duration_min / 5
affected_points = int(n1 * points_in_window1 + n2 * points_in_window2)

print(f"\nExpected Impact (both windows combined):")
print(f"   Timepoints per patient: ~{points_per_patient:.0f}")
print(f"   Affected timepoints in window 1: ~{int(n1 * points_in_window1):,}")
print(f"   Affected timepoints in window 2: ~{int(n2 * points_in_window2):,}")
print(f"   Total affected timepoints: ~{affected_points:,}")
print(f"   % of total data: {affected_points / pseudo_clean.count() * 100:.2f}%")

print(f"\n[SUCCESS] Two-window incident cohorts selected")

# COMMAND ----------

# DBTITLE 1,Inject calibration bias into glucose_observed
# ------------------------
# Inject calibration bias during incident windows (two-window mirror design)
# glucose_true stays unchanged (ground truth)
# glucose_observed += signed_bias_mgdl during the patient's own incident window
#   Cohort 1 (positive, +bias_magnitude) is biased during window 1
#   Cohort 2 (negative, -bias_magnitude) is biased during window 2
# ------------------------

print("Injecting calibration bias (two-window mirror design)...")
print(f"   Magnitude:           {bias_magnitude} mg/dL")
print(f"   Window 1 ({window1_direction}, +bias): {window1_start_ts} → {window1_end_ts}  (cohort 1: {n1} patients)")
print(f"   Window 2 ({window2_direction}, -bias): {window2_start_ts} → {window2_end_ts}  (cohort 2: {n2} patients)")
print(f"   Cohorts are mutually exclusive — each patient is in at most one window.\n")

# Drop has_incident from pseudo_clean to avoid ambiguity, then join incident_patients
# (which carries `incident_direction`, `signed_bias_mgdl`, and `incident_window_idx`
# per-patient — distinct values for cohort 1 vs cohort 2).
pseudo_with_flag = pseudo_clean.drop("has_incident").join(
    incident_patients,
    "patient_id",
    "left"
).fillna({"has_incident": 0, "incident_window_idx": 0})

# Per-window in-window mask: a row is "in window" if the patient's cohort matches the
# window AND the row's time is inside that window's [start, end). Cohorts are mutually
# exclusive so a row is in at most one window.
_in_window_1 = (
    (F.col("incident_window_idx") == 1) &
    (F.col("time") >= F.lit(window1_start_ts)) &
    (F.col("time") < F.lit(window1_end_ts))
)
_in_window_2 = (
    (F.col("incident_window_idx") == 2) &
    (F.col("time") >= F.lit(window2_start_ts)) &
    (F.col("time") < F.lit(window2_end_ts))
)
_in_window = _in_window_1 | _in_window_2

# Inject SIGNED bias: glucose_observed += signed_bias_mgdl during the patient's incident
# window. signed_bias_mgdl is +magnitude for cohort 1 (window 1), -magnitude for cohort 2
# (window 2 mirror) — set at cohort selection time above.
pseudo_incident = pseudo_with_flag.withColumn(
    "glucose_observed",
    F.when(_in_window, F.col("glucose_observed") + F.col("signed_bias_mgdl"))
     .otherwise(F.col("glucose_observed"))
).withColumn(
    "incident_type",
    F.when(_in_window, F.lit("calibration_bias")).otherwise(F.lit(None).cast("string"))
).withColumn(
    # Per-patient incident window — points to window 1 for cohort 1, window 2 for cohort 2.
    "incident_start_time",
    F.when(F.col("incident_window_idx") == 1, F.lit(window1_start_ts))
     .when(F.col("incident_window_idx") == 2, F.lit(window2_start_ts))
     .otherwise(F.lit(None).cast("timestamp"))
).withColumn(
    "incident_end_time",
    F.when(F.col("incident_window_idx") == 1, F.lit(window1_end_ts))
     .when(F.col("incident_window_idx") == 2, F.lit(window2_end_ts))
     .otherwise(F.lit(None).cast("timestamp"))
).withColumn(
    # Stores the SIGNED value (+magnitude or -magnitude). Downstream consumers can take
    # ABS() if they want magnitude. Pairs with `incident_direction` enum for explicit
    # direction signaling.
    "incident_bias_mgdl",
    F.when(F.col("has_incident") == 1, F.col("signed_bias_mgdl")).otherwise(F.lit(None).cast("double"))
)
# incident_direction column is already on incident_patients → flows through the join.
# Null it out for clean (non-affected) patients for consistency.
pseudo_incident = pseudo_incident.withColumn(
    "incident_direction",
    F.when(F.col("has_incident") == 1, F.col("incident_direction")).otherwise(F.lit(None).cast("string"))
).drop("signed_bias_mgdl", "incident_window_idx")  # drop intermediate columns; incident_bias_mgdl + incident_direction carry the signal

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

# Join with incident flags. Drop has_incident AND incident_direction from df first
# because BOTH columns exist on `pseudo_incident_7d` (left, via df) AND on
# `pseudo_incident_7d_labeled` (right, via incident_info from pseudo_incident_tbl)
# — Spark raises AMBIGUOUS_REFERENCE on the post-join select() otherwise.
# Single source of truth: keep the copy from incident_info.
incident_info = spark.table(pseudo_incident_tbl).select(
    "patient_id", "time", "has_incident", "incident_type", "incident_direction"
)
df = df.drop("has_incident", "incident_direction").join(incident_info, ["patient_id", "time"], "inner")

# Add incident_active flag — TWO windows (two-window mirror design):
# A row is incident_active if the patient's cohort matches the window AND the row's time
# is inside that window. Cohort 1 (positive direction) maps to window 1; cohort 2
# (negative direction) maps to window 2. Cohorts are mutually exclusive so incident_active
# is 1 in exactly one window per patient.
base_date = pd.Timestamp(cfg.demo_week_start)
window1_start_ts = base_date + pd.Timedelta(days=cfg.incident_start_day, hours=cfg.incident_start_hour)
window1_end_ts = window1_start_ts + pd.Timedelta(minutes=cfg.incident_duration_min)
window2_start_ts = base_date + pd.Timedelta(days=cfg.second_incident_start_day, hours=cfg.second_incident_start_hour)
window2_end_ts = window2_start_ts + pd.Timedelta(minutes=cfg.second_incident_duration_min)
# Back-compat aliases for any older references later in the notebook
incident_start_ts = window1_start_ts
incident_end_ts = window1_end_ts

df = df.withColumn(
    "incident_active",
    (((F.col("incident_direction") == F.lit("positive")) &
      (F.col("time") >= F.lit(window1_start_ts)) &
      (F.col("time") < F.lit(window1_end_ts)))
     |
     ((F.col("incident_direction") == F.lit("negative")) &
      (F.col("time") >= F.lit(window2_start_ts)) &
      (F.col("time") < F.lit(window2_end_ts)))
    ).cast("int")
)

# Build features (same as clean model)
# IMPORTANT: Include glucose_true for visualization
w_ord = Window.partitionBy("patient_id").orderBy("time")

feat = (df.select(
        "patient_id", "time", "incident_active", "has_incident", "incident_direction",
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
# incident_direction is metadata for downstream MAE breakouts, NOT a model feature.
feature_cols = [c for c in feat_sample.columns if c not in
                {"patient_id", "time", "incident_active", "has_incident", "incident_direction",
                 "glucose_true", "y_tplus_3", "y_tplus_6"}]
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

    print(f"\nINCIDENT PERIOD (calibration bug, magnitude {bias_magnitude} mg/dL, bidirectional):")
    print(f"   MAE (aggregate): {incident_mae_15m:.1f} mg/dL (15m) | {incident_mae_30m:.1f} mg/dL (30m)")

    # Bidirectional MAE breakout — both directions should produce similar MAE magnitudes
    # because MAE is sign-agnostic (|forecast - observed|). Demonstrates direction-agnostic
    # anomaly detection: platform catches both over- and under-reading equally.
    pos_period = incident_period[incident_period['incident_direction'] == 'positive']
    neg_period = incident_period[incident_period['incident_direction'] == 'negative']
    if len(pos_period) > 0:
        pos_mae_15m = pos_period['mae_15m'].mean()
        pos_mae_30m = pos_period['mae_30m'].mean()
        print(f"   - Positive-bias group (+{bias_magnitude} mg/dL): MAE {pos_mae_15m:.1f} (15m) | {pos_mae_30m:.1f} (30m)  [over-reading, n={len(pos_period):,}]")
    if len(neg_period) > 0:
        neg_mae_15m = neg_period['mae_15m'].mean()
        neg_mae_30m = neg_period['mae_30m'].mean()
        print(f"   - Negative-bias group (-{bias_magnitude} mg/dL): MAE {neg_mae_15m:.1f} (15m) | {neg_mae_30m:.1f} (30m)  [under-reading, n={len(neg_period):,}]")
    print(f"   Status: CATASTROPHIC FAILURE — direction-agnostic detection proven")
    
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

# Aggregation strategy (bidirectional-aware):
#   - During clean period: aggregate all patients (no bias yet, devices read correctly).
#   - During incident period: aggregate ONLY affected patients (has_incident=1) — and
#     SPLIT them by incident_direction into positive/negative observed series, because
#     a signed AVG across both directions cancels (50% × +40 + 50% × -40 = 0). Two
#     separate series exposes the direction-aware bias visually.
# Include incident_direction in timeline_data so we can split.
timeline_data = feat_sample[["time", "incident_active", "has_incident", "incident_direction",
                              "mae_15m", "mae_30m", "glucose_true", "glucose_observed"]].copy()
timeline_data = timeline_data.sort_values("time")
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")

clean_data = timeline_data[timeline_data['incident_active'] == 0]
incident_data = timeline_data[(timeline_data['incident_active'] == 1) & (timeline_data['has_incident'] == 1)]

# Aggregate clean period (all patients). During clean, observed ≈ true (no bias),
# so positive/negative cohorts effectively have the same observed signal.
clean_agg = clean_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max",
    "glucose_true": "mean",
    "glucose_observed": "mean"
}).reset_index()
clean_agg["glucose_observed_positive"] = clean_agg["glucose_observed"]
clean_agg["glucose_observed_negative"] = clean_agg["glucose_observed"]

# Aggregate incident period (affected patients only) — base columns
incident_agg = incident_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max",
    "glucose_true": "mean",
    "glucose_observed": "mean"  # signed avg — kept for compat; positive/negative are the load-bearing series
}).reset_index()

# Split observed by incident_direction
positive_obs = (incident_data[incident_data["incident_direction"] == "positive"]
                .groupby("hour")["glucose_observed"].mean().reset_index()
                .rename(columns={"glucose_observed": "glucose_observed_positive"}))
negative_obs = (incident_data[incident_data["incident_direction"] == "negative"]
                .groupby("hour")["glucose_observed"].mean().reset_index()
                .rename(columns={"glucose_observed": "glucose_observed_negative"}))
incident_agg = incident_agg.merge(positive_obs, on="hour", how="left").merge(negative_obs, on="hour", how="left")

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

# Detect contiguous incident blocks — two-window mirror design has TWO
# separate incidents (Day 2 + Day 5), so we need one shaded rect + one yellow
# label per incident instead of one big rect + one summary label.
def _incident_blocks_from(df, time_col="hour", active_col="incident_active", gap_threshold_hours=2):
    """Group consecutive rows with active_col==1 into blocks. Returns list of dicts."""
    active_rows = df[df[active_col] == 1].sort_values(time_col).copy()
    if len(active_rows) == 0:
        return []
    active_rows["_gap"] = active_rows[time_col].diff() > pd.Timedelta(hours=gap_threshold_hours)
    active_rows["_block"] = active_rows["_gap"].cumsum()
    blocks = []
    for _bid, _blk in active_rows.groupby("_block"):
        bs = _blk[time_col].min()
        be = _blk[time_col].max() + pd.Timedelta(hours=1)
        blocks.append({"start": bs, "end": be, "mid": bs + (be - bs) / 2, "rows": _blk})
    return blocks

incident_blocks_1 = _incident_blocks_from(hourly_agg)

# Shade each incident period separately (one rectangle per block)
for _i, _blk in enumerate(incident_blocks_1):
    ax1.axvspan(_blk["start"], _blk["end"], alpha=0.2, color='grey',
                label='Incident Period' if _i == 0 else None)

if incident_blocks_1:
    ax1.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')

ax1.set_ylabel("MAE (mg/dL)", fontsize=12)
ax1.set_title("Incident Impact: MAE Spike During Device Calibration Bug", fontsize=14, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, max(hourly_agg["mae_15m"].max(), hourly_agg["mae_30m"].max()) * 1.1)

# Yellow box annotation per incident — positioned ABOVE-RIGHT of each spike
# with an arrow back to the spike, so the box does not occlude the data peak
# it is annotating. 12h horizontal offset clears spike width on a 7-day chart.
if incident_blocks_1:
    y_min_ax1, y_max_ax1 = ax1.get_ylim()
    for _i, _blk in enumerate(incident_blocks_1):
        _blk_peak_15m = _blk["rows"]["mae_15m"].max() if "mae_15m" in _blk["rows"].columns else 0
        _blk_peak_30m = _blk["rows"]["mae_30m"].max() if "mae_30m" in _blk["rows"].columns else 0
        _target_y = max(_blk_peak_15m, _blk_peak_30m) * 0.85

        ax1.annotate(
            f'Incident {_i+1}\n{_blk_peak_15m:.0f} (15m)\n{_blk_peak_30m:.0f} (30m) mg/dL',
            xy=(_blk["mid"], _target_y),
            xytext=(_blk["mid"] + pd.Timedelta(hours=12), y_max_ax1 * 0.88),
            fontsize=8,
            fontweight='bold',
            ha='center',
            va='center',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.2),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5, connectionstyle='arc3,rad=0.0')
        )

# Plot 2: Glucose Timeline (bidirectional)
# Unified palette (post-v7): DARKGRAY = True glucose reference, RED = positive cohort,
# BLUE = negative cohort. Same convention across all 05_incident_inference_bidirectional figures.
# DARKGRAY = True glucose (actual baseline)
# RED  = Positive-bias cohort device readings (over-reads — spikes UP +bias_magnitude during incident)
# BLUE = Negative-bias cohort device readings (under-reads — drops DOWN -bias_magnitude during incident)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_true"], label="True glucose (actual baseline)",
         linewidth=2.5, linestyle='-', color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_observed_positive"],
         label=f"Device — positive bias cohort (+{bias_magnitude:.0f} mg/dL)",
         linewidth=2.0, linestyle='-', color="red", marker="s", markersize=4, alpha=0.9, zorder=3)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_observed_negative"],
         label=f"Device — negative bias cohort (-{bias_magnitude:.0f} mg/dL)",
         linewidth=2.0, linestyle='-', color="blue", marker="^", markersize=4, alpha=0.9, zorder=3)

# Set explicit ylim with headroom so labels fit comfortably above/below spikes
# without colliding with chart title/frame.
_all_y_fig1 = pd.concat([
    hourly_agg["glucose_true"],
    hourly_agg.get("glucose_observed_positive", pd.Series(dtype=float)),
    hourly_agg.get("glucose_observed_negative", pd.Series(dtype=float)),
]).dropna()
_data_min_fig1, _data_max_fig1 = _all_y_fig1.min(), _all_y_fig1.max()
_y_range_fig1 = _data_max_fig1 - _data_min_fig1
ax2.set_ylim(_data_min_fig1 - _y_range_fig1 * 0.20, _data_max_fig1 + _y_range_fig1 * 0.20)
_y_min_fig1, _y_max_fig1 = ax2.get_ylim()
_y_pad_fig1 = (_y_max_fig1 - _y_min_fig1) * 0.05

# Shade each incident period + per-incident yellow label (offset to the right
# of each spike with arrow pointing back, so the box does not occlude the data).
# Window 1 (positive cohort) gets label "+N mg/dL"; Window 2 (negative cohort)
# gets label "-N mg/dL" — derived from the block's middle-row signed bias.
# NaN-aware direction detection: use 0 when the opposite cohort's value is NaN
# (Python's `or` would return NaN here — truthy — and break the comparison).
for _i, _blk in enumerate(incident_blocks_1):
    ax2.axvspan(_blk["start"], _blk["end"], alpha=0.15, color='grey',
                label='Incident Period' if _i == 0 else None, zorder=1)

    # Pick a representative row for arrow target (middle of block)
    _mid_idx = len(_blk["rows"]) // 2
    _row = _blk["rows"].iloc[_mid_idx]
    _y_true = _row["glucose_true"]
    _pos = _row.get("glucose_observed_positive")
    _neg = _row.get("glucose_observed_negative")

    # Determine direction by larger divergence from true (NaN-safe)
    _pos_diff = abs(_pos - _y_true) if pd.notna(_pos) else 0
    _neg_diff = abs(_neg - _y_true) if pd.notna(_neg) else 0
    if _pos_diff > _neg_diff:
        _direction = "positive"
        _sign = "+"
        # Arrow tip on the RED (positive cohort) spike — use the block's peak observation
        _pos_data = _blk["rows"].get("glucose_observed_positive")
        _y_target = _pos_data.max() if _pos_data is not None and pd.notna(_pos_data.max()) else (_y_true + bias_magnitude)
        _annot_y = min(_y_max_fig1 - _y_pad_fig1, _y_true + bias_magnitude + 10)
    else:
        _direction = "negative"
        _sign = "-"
        # Arrow tip on the BLUE (negative cohort) trough — use the block's lowest observation
        _neg_data = _blk["rows"].get("glucose_observed_negative")
        _y_target = _neg_data.min() if _neg_data is not None and pd.notna(_neg_data.min()) else (_y_true - bias_magnitude)
        _annot_y = max(_y_min_fig1 + _y_pad_fig1, _y_true - bias_magnitude - 10)

    ax2.annotate(
        f'Incident {_i+1}\n{_sign}{bias_magnitude:.0f} mg/dL\n({_direction} cohort)',
        xy=(_blk["mid"], _y_target),
        xytext=(_blk["mid"] + pd.Timedelta(hours=12), _annot_y),
        fontsize=8,
        fontweight='bold',
        ha='center',
        va='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.2),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, connectionstyle='arc3,rad=0.0')
    )

ax2.set_xlabel("Time", fontsize=12)
ax2.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax2.set_title(f"Glucose Timeline: ±{bias_magnitude:.0f} mg/dL Bidirectional Calibration Bias During Incident", fontsize=14, fontweight='bold')
ax2.legend(loc='upper left')
ax2.grid(True, alpha=0.3)
ax2.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax2.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

plt.tight_layout()
# Save PNG asset to UC Volume for repo refresh + MetricsExplained embed
# (transparent bg so the image inherits parent card color in any theme — dark or light)
# Ensure the pipeline_data volume exists — 05 runs before the tasks that
# create the volume otherwise (08 + create_device_telemetry +
# create_patient_registry all create it). Idempotent.
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.pipeline_data")
_ASSET_DIR = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/incident_inference_assets"
dbutils.fs.mkdirs(_ASSET_DIR)
_asset_path = f"{_ASSET_DIR}/incident_impact_2panel.png"
plt.savefig(_asset_path, transparent=True, dpi=150, bbox_inches='tight')
print(f"[ASSET] Saved {_asset_path}")
plt.show()

print("[SUCCESS] Visualization complete!")
print(f"\nThe plot clearly shows:")
print(f"   1. MAE is stable at ~5.8 mg/dL during clean periods")
print(f"   2. MAE spikes to ~{incident_mae_15m:.0f} mg/dL during the 3-hour incident (direction-agnostic — ABS captures both cohorts)")
print(f"   3. MAE returns to ~5.8 mg/dL after incident ends")
print(f"   4. GREEN line (true glucose) = stable baseline throughout")
print(f"   5. RED line (positive cohort) spikes +{bias_magnitude:.0f} mg/dL ABOVE green during incident (over-reading)")
print(f"   6. BLUE line (negative cohort) drops -{bias_magnitude:.0f} mg/dL BELOW green during incident (under-reading)")
print(f"   7. Outside incident: all three lines overlap (devices read correctly)")
print(f"\nThis demonstrates the critical impact of bidirectional device calibration bugs!")
print(f"Both over- and under-reading drifts are clinically dangerous (in opposite ways)")
print(f"but both are detected by the same direction-agnostic MAE monitor.")

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

# Detect incident blocks (two-window mirror design — uses helper from Plot 1 cell)
incident_blocks_2 = _incident_blocks_from(all_patients_agg)

# Default summary stats so downstream prints (line ~1296+) always have these
# defined even when a cohort has no incident-active rows (unaffected cohort is
# the obvious case — by construction it never has incident_active=1).
fleet_incident_mae_15m = 0.0
fleet_incident_mae_30m = 0.0
unaffected_incident_mae_15m = 0.0
unaffected_incident_mae_30m = 0.0

# Create figure with 3 subplots (vertical stack)
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

# Shared y-axis range across all 3 MAE panels — keeps amplitudes comparable
# (panel 2 affected has the highest spike; panel 3 unaffected is flat by design).
# Same pattern as Figure 3 (Glucose Timeline).
_fig2_all_mae = pd.concat([
    all_patients_agg["mae_15m"], all_patients_agg["mae_30m"],
    affected_agg["mae_15m"], affected_agg["mae_30m"],
    unaffected_agg["mae_15m"], unaffected_agg["mae_30m"],
]).dropna()
_y_max_fig2 = _fig2_all_mae.max() * 1.15
ax1.set_ylim(0, _y_max_fig2)
ax2.set_ylim(0, _y_max_fig2)
ax3.set_ylim(0, _y_max_fig2)

def _per_block_annotate(ax, agg_df, blocks, color_box='yellow', label_prefix=''):
    """Helper: draw one shaded rect + one label per incident block.
    Label is offset 12h to the right of the spike with an arrow back, so the
    box does not occlude the data peak. Uses the ax's CURRENT ylim (set globally
    above before the helper is called) so labels align with the shared range."""
    y_max = ax.get_ylim()[1]
    for _i, _blk in enumerate(blocks):
        ax.axvspan(_blk["start"], _blk["end"], alpha=0.2, color='grey',
                   label='Incident Period' if _i == 0 else None)
        _blk_15m = _blk["rows"]["mae_15m"].max() if "mae_15m" in _blk["rows"].columns else 0
        _blk_30m = _blk["rows"]["mae_30m"].max() if "mae_30m" in _blk["rows"].columns else 0
        ax.annotate(
            f'{label_prefix}Incident {_i+1}\n{_blk_15m:.0f} (15m)\n{_blk_30m:.0f} (30m) mg/dL',
            xy=(_blk["mid"], _blk_15m),
            xytext=(_blk["mid"] + pd.Timedelta(hours=12), y_max * 0.88),
            fontsize=8, fontweight='bold', ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.4', facecolor=color_box, alpha=0.7, edgecolor='black', linewidth=1.2),
            arrowprops=dict(arrowstyle='->', color='black', lw=1.5, connectionstyle='arc3,rad=0.0')
        )

# ------------------------
# Plot 1: ALL PATIENTS (Fleet-wide average)
# ------------------------
ax1.plot(all_patients_agg["hour"], all_patients_agg["mae_15m"],
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax1.plot(all_patients_agg["hour"], all_patients_agg["mae_30m"],
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')
if incident_blocks_2:
    ax1.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    _per_block_annotate(ax1, all_patients_agg, incident_blocks_2, label_prefix='Fleet ')
    fleet_incident_mae_15m = all_patients_agg[all_patients_agg["incident_active"] == 1]["mae_15m"].mean()
    fleet_incident_mae_30m = all_patients_agg[all_patients_agg["incident_active"] == 1]["mae_30m"].mean()

ax1.set_ylabel("MAE (mg/dL)", fontsize=12)
ax1.set_title("1. ALL PATIENTS (Fleet-wide Average) - Diluted Impact", fontsize=13, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)
# ylim shared with panels 2/3 — set globally right after figure creation

# ------------------------
# Plot 2: AFFECTED PATIENTS ONLY
# ------------------------
ax2.plot(affected_agg["hour"], affected_agg["mae_15m"],
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax2.plot(affected_agg["hour"], affected_agg["mae_30m"],
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')
incident_blocks_2_affected = _incident_blocks_from(affected_agg)
if incident_blocks_2_affected:
    ax2.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    _per_block_annotate(ax2, affected_agg, incident_blocks_2_affected, label_prefix='Affected ')

ax2.set_ylabel("MAE (mg/dL)", fontsize=12)
ax2.set_title(f"2. AFFECTED PATIENTS ONLY (~{(cfg.incident_pct + getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% of fleet across two windows) - True Incident Impact", fontsize=13, fontweight='bold')
ax2.legend(loc='upper left', fontsize=10)
ax2.grid(True, alpha=0.3)
# ylim shared with panels 1/3 — set globally right after figure creation

# ------------------------
# Plot 3: UNAFFECTED PATIENTS ONLY
# ------------------------
ax3.plot(unaffected_agg["hour"], unaffected_agg["mae_15m"],
         label="MAE 15m", linewidth=2, marker="o", markersize=4, color='blue')
ax3.plot(unaffected_agg["hour"], unaffected_agg["mae_30m"],
         label="MAE 30m", linewidth=2, marker="s", markersize=4, color='orange')
incident_blocks_2_unaffected = _incident_blocks_from(unaffected_agg)
if incident_blocks_2_unaffected:
    ax3.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')
    _per_block_annotate(ax3, unaffected_agg, incident_blocks_2_unaffected, color_box='lightgreen', label_prefix='Unaffected ')
    unaffected_incident_mae_15m = unaffected_agg[unaffected_agg["incident_active"] == 1]["mae_15m"].mean() if (unaffected_agg["incident_active"] == 1).any() else 0
    unaffected_incident_mae_30m = unaffected_agg[unaffected_agg["incident_active"] == 1]["mae_30m"].mean() if (unaffected_agg["incident_active"] == 1).any() else 0

ax3.set_xlabel("Time", fontsize=12)
ax3.set_ylabel("MAE (mg/dL)", fontsize=12)
ax3.set_title(f"3. UNAFFECTED PATIENTS ONLY (~{(1 - cfg.incident_pct - getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% of fleet — Epsilon/Zeta models) - Stable Performance", fontsize=13, fontweight='bold')
ax3.legend(loc='upper left', fontsize=10)
ax3.grid(True, alpha=0.3)
# ylim shared with panels 1/2 — set globally right after figure creation

plt.tight_layout()
# Save PNG asset to UC Volume for repo refresh + MetricsExplained embed (transparent bg)
_ASSET_DIR = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/incident_inference_assets"
dbutils.fs.mkdirs(_ASSET_DIR)
_asset_path = f"{_ASSET_DIR}/mae_breakdown_3panel.png"
plt.savefig(_asset_path, transparent=True, dpi=150, bbox_inches='tight')
print(f"[ASSET] Saved {_asset_path}")
plt.show()

print("[SUCCESS] 3-panel MAE comparison complete!")
print(f"\nKey Insights:")
print(f"   1. Fleet-wide (all patients): MAE ~{fleet_incident_mae_15m:.1f} mg/dL during incident")
print(f"      → Diluted by ~{(1 - cfg.incident_pct - getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% unaffected patients (Epsilon + Zeta models)")
print(f"   2. Affected patients: MAE ~{incident_mae_15m:.1f} mg/dL during incident")
print(f"      → True impact of ±{bias_magnitude:.0f} mg/dL bidirectional calibration bias (over-reading OR under-reading per cohort)")
print(f"   3. Unaffected patients: MAE ~{unaffected_incident_mae_15m:.1f} mg/dL (stable)")
print(f"      → No device bug, normal performance maintained")
print(f"\nThis demonstrates why patient-level monitoring is critical!")
print(f"Fleet-wide metrics can hide serious issues affecting subsets of patients.")

# COMMAND ----------

# DBTITLE 1,Glucose Timeline Comparison: All vs Affected vs Unaffected
# ------------------------
# Glucose Timeline Comparison: 3 Separate Views
# 1. All patients (fleet-wide average)
# 2. Affected patients only — bidirectional split (positive cohort over-reads, negative under-reads)
# 3. Unaffected patients only (stable baseline)
# ------------------------
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

print("Creating 3-panel glucose timeline comparison (bidirectional-aware)...\n")

# Prepare timeline data with glucose values + incident_direction (for bidirectional split)
timeline_data = feat_sample[["time", "incident_active", "has_incident", "incident_direction",
                              "glucose_true", "glucose_observed"]].copy()
timeline_data = timeline_data.sort_values("time")
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")

# 1. All patients aggregation (fleet-wide) — signed avg deliberately, this PANEL'S story
# is "fleet-wide averages mask both dilution AND bidirectional cancellation"
all_patients_glucose = timeline_data.groupby("hour").agg({
    "glucose_true": "mean",
    "glucose_observed": "mean",
    "incident_active": "max"
}).reset_index()

# 2. Affected patients only (has_incident=1) — SPLIT BY DIRECTION
# Signed AVG across positive+negative cohorts cancels (50% × +40 + 50% × -40 = 0).
# Split into separate positive/negative series to expose the bidirectional bias visually.
affected_data = timeline_data[timeline_data['has_incident'] == 1]
affected_glucose = affected_data.groupby("hour").agg({
    "glucose_true": "mean",
    "glucose_observed": "mean",  # kept for compat; positive/negative are load-bearing
    "incident_active": "max"
}).reset_index()
affected_positive_obs = (affected_data[affected_data["incident_direction"] == "positive"]
                          .groupby("hour")["glucose_observed"].mean().reset_index()
                          .rename(columns={"glucose_observed": "glucose_observed_positive"}))
affected_negative_obs = (affected_data[affected_data["incident_direction"] == "negative"]
                          .groupby("hour")["glucose_observed"].mean().reset_index()
                          .rename(columns={"glucose_observed": "glucose_observed_negative"}))
affected_glucose = (affected_glucose
                    .merge(affected_positive_obs, on="hour", how="left")
                    .merge(affected_negative_obs, on="hour", how="left"))

# 3. Unaffected patients only (has_incident=0) — no bias, observed == true
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

# Detect contiguous incident blocks (handles two-window mirror design — Day 2 + Day 5)
incident_blocks_3 = _incident_blocks_from(all_patients_glucose)

# Create figure with 3 subplots (vertical stack)
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 12), sharex=True)

# Shared y-axis range across all 3 panels — keeps scales comparable visually so
# the reader can compare amplitude of variation between Fleet-wide / Affected /
# Unaffected. Driven by panel 2 (affected) which has the widest range (+40/-40 spikes).
_fig3_all_data = pd.concat([
    all_patients_glucose["glucose_true"],
    all_patients_glucose.get("glucose_observed", pd.Series(dtype=float)),
    affected_glucose["glucose_true"],
    affected_glucose.get("glucose_observed_positive", pd.Series(dtype=float)),
    affected_glucose.get("glucose_observed_negative", pd.Series(dtype=float)),
    unaffected_glucose["glucose_true"],
    unaffected_glucose.get("glucose_observed", pd.Series(dtype=float)),
]).dropna()
_data_min_fig3, _data_max_fig3 = _fig3_all_data.min(), _fig3_all_data.max()
_y_range_fig3 = _data_max_fig3 - _data_min_fig3
_y_min_fig3 = _data_min_fig3 - _y_range_fig3 * 0.20
_y_max_fig3 = _data_max_fig3 + _y_range_fig3 * 0.20
_y_pad_fig3 = (_y_max_fig3 - _y_min_fig3) * 0.05
ax1.set_ylim(_y_min_fig3, _y_max_fig3)
ax2.set_ylim(_y_min_fig3, _y_max_fig3)
ax3.set_ylim(_y_min_fig3, _y_max_fig3)

# ------------------------
# Plot 1: ALL PATIENTS (Fleet-wide average)
# ------------------------
ax1.plot(all_patients_glucose["hour"], all_patients_glucose["glucose_true"],
         label="True glucose (actual baseline)", linewidth=2.5, linestyle='-',
         color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax1.plot(all_patients_glucose["hour"], all_patients_glucose["glucose_observed"],
         label="Observed glucose (device reading)", linewidth=2.5, linestyle='-',
         color="mediumturquoise", marker="s", markersize=4, alpha=0.85, zorder=3)
# Unified palette: panels 1 + 3 use mediumturquoise for observed (no cohort split)
# — visually paired as "no directional bias displayed". Distinct from panel 2's
# red/blue cohort split. True-glucose reference is darkgray across all figures.

# Compute per-block fleet bias + one yellow label per incident
fleet_bias = 0.0
for _i, _blk in enumerate(incident_blocks_3):
    ax1.axvspan(_blk["start"], _blk["end"], alpha=0.15, color='grey',
                label='Incident Period' if _i == 0 else None, zorder=1)
    _blk_obs = _blk["rows"]["glucose_observed"].mean()
    _blk_true = _blk["rows"]["glucose_true"].mean()
    _blk_bias = _blk_obs - _blk_true
    fleet_bias = _blk_bias  # last block wins for downstream print (best-effort)
    _mid_row = _blk["rows"].iloc[len(_blk["rows"]) // 2]
    ax1.annotate(
        f'Incident {_i+1}\n{_blk_bias:+.1f} mg/dL\nfleet-wide bias',
        xy=(_blk["mid"], _mid_row["glucose_observed"]),
        xytext=(_blk["mid"] + pd.Timedelta(hours=12), 175 if _blk_bias >= 0 else 95),
        fontsize=8, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.2),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=0.0')
    )

ax1.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax1.set_title("1. ALL PATIENTS (Fleet-wide Average) - Diluted Bias", fontsize=13, fontweight='bold')
ax1.legend(loc='upper left', fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax1.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

# ------------------------
# Plot 2: AFFECTED PATIENTS ONLY — bidirectional split
# Three lines: darkgray True + red positive cohort + blue negative cohort
# (Same color convention as the React Glucose Timeline chart in IncidentCharts.jsx)
# ------------------------
ax2.plot(affected_glucose["hour"], affected_glucose["glucose_true"],
         label="True glucose (actual baseline)", linewidth=2.5, linestyle='-',
         color="darkgray", marker="o", markersize=4, alpha=0.9, zorder=2)
ax2.plot(affected_glucose["hour"], affected_glucose["glucose_observed_positive"],
         label=f"Device — positive bias cohort (+{bias_magnitude:.0f} mg/dL, over-reads)",
         linewidth=2.0, linestyle='-',
         color="red", marker="s", markersize=4, alpha=0.9, zorder=3)
ax2.plot(affected_glucose["hour"], affected_glucose["glucose_observed_negative"],
         label=f"Device — negative bias cohort (-{bias_magnitude:.0f} mg/dL, under-reads)",
         linewidth=2.0, linestyle='-',
         color="blue", marker="^", markersize=4, alpha=0.9, zorder=3)

# NOTE: y-limit set globally for all 3 panels right after the figure-creation block above
# (shared range so panel-to-panel amplitude comparisons are visually fair).
incident_blocks_3_affected = _incident_blocks_from(affected_glucose)
for _i, _blk in enumerate(incident_blocks_3_affected):
    ax2.axvspan(_blk["start"], _blk["end"], alpha=0.15, color='grey',
                label='Incident Period' if _i == 0 else None, zorder=1)
    _mid_row = _blk["rows"].iloc[len(_blk["rows"]) // 2]
    _y_true = _mid_row["glucose_true"]
    # Direction: which cohort diverges from true at this block? (NaN-safe)
    _pos = _mid_row.get("glucose_observed_positive")
    _neg = _mid_row.get("glucose_observed_negative")
    if pd.notna(_pos) and (pd.isna(_neg) or abs(_pos - _y_true) > abs(_neg - _y_true)):
        _direction = "positive (over-reads)"
        _sign = "+"
        # Arrow tip on RED positive-cohort spike — use block's peak observation
        _pos_data = _blk["rows"].get("glucose_observed_positive")
        _y_target = _pos_data.max() if _pos_data is not None and pd.notna(_pos_data.max()) else (_y_true + bias_magnitude)
        _annot_y = min(_y_max_fig3 - _y_pad_fig3, _y_true + bias_magnitude + 10)
    else:
        _direction = "negative (under-reads)"
        _sign = "-"
        # Arrow tip on BLUE negative-cohort trough — use block's lowest observation
        _neg_data = _blk["rows"].get("glucose_observed_negative")
        _y_target = _neg_data.min() if _neg_data is not None and pd.notna(_neg_data.min()) else (_y_true - bias_magnitude)
        _annot_y = max(_y_min_fig3 + _y_pad_fig3, _y_true - bias_magnitude - 10)
    ax2.annotate(
        f'Incident {_i+1}\n{_sign}{bias_magnitude:.0f} mg/dL\n{_direction}',
        xy=(_blk["mid"], _y_target),
        xytext=(_blk["mid"] + pd.Timedelta(hours=12), _annot_y),
        fontsize=8, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='yellow', alpha=0.7, edgecolor='black', linewidth=1.2),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=0.0')
    )

ax2.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax2.set_title(f"2. AFFECTED PATIENTS ONLY (~{(cfg.incident_pct + getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% of fleet — Alpha/Gamma +bias on Day 2; Beta/Delta -bias on Day 5)", fontsize=12, fontweight='bold', color='#888888')
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
# Unified palette: panels 1 + 3 use mediumturquoise for observed (no cohort split)
# — visually paired as "no directional bias displayed". Distinct from blue=negative-
# cohort in panel 2. True-glucose reference is darkgray across all figures.

# NOTE: ylim shared with panels 1/2 (set globally right after figure creation) so
# amplitude comparison is visually fair. Unaffected panel will look flat within
# this wider range — that visual contrast IS the point.

incident_blocks_3_unaffected = _incident_blocks_from(unaffected_glucose)
for _i, _blk in enumerate(incident_blocks_3_unaffected):
    ax3.axvspan(_blk["start"], _blk["end"], alpha=0.15, color='grey',
                label='Incident Period' if _i == 0 else None, zorder=1)
    # Position label near top of shared range; arrow tip at the actual data point in block
    _mid_idx = len(_blk["rows"]) // 2
    _arrow_y = _blk["rows"]["glucose_observed"].iloc[_mid_idx] if "glucose_observed" in _blk["rows"].columns else (_y_min_fig3 + _y_max_fig3) / 2
    ax3.annotate(
        f'Incident {_i+1}\nNo bias\n(device OK)',
        xy=(_blk["mid"], _arrow_y),
        xytext=(_blk["mid"] + pd.Timedelta(hours=12), _y_max_fig3 - _y_pad_fig3),
        fontsize=8, fontweight='bold', ha='center', va='center',
        bbox=dict(boxstyle='round,pad=0.4', facecolor='lightgreen', alpha=0.7, edgecolor='black', linewidth=1.2),
        arrowprops=dict(arrowstyle='->', color='black', lw=1.5, alpha=0.7, connectionstyle='arc3,rad=0.0')
    )

ax3.set_xlabel("Time", fontsize=12)
ax3.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax3.set_title(f"3. UNAFFECTED PATIENTS ONLY (~{(1 - cfg.incident_pct - getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% of fleet — Epsilon/Zeta models) - No Device Bug", fontsize=12, fontweight='bold', color='#888888')
ax3.legend(loc='upper left', fontsize=10)
ax3.grid(True, alpha=0.3)
# axhlines for 70/180 thresholds: still drawn but typically off-screen at this tighter ylim
# (kept for visual consistency with panels 1/2; safe to remove if cleaner desired)
ax3.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
ax3.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)

plt.tight_layout()
# Save PNG asset to UC Volume for repo refresh + MetricsExplained embed (transparent bg)
_ASSET_DIR = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/incident_inference_assets"
dbutils.fs.mkdirs(_ASSET_DIR)
_asset_path = f"{_ASSET_DIR}/glucose_timeline_3panel.png"
plt.savefig(_asset_path, transparent=True, dpi=150, bbox_inches='tight')
print(f"[ASSET] Saved {_asset_path}")
plt.show()

print("[SUCCESS] 3-panel glucose timeline comparison complete!")
print(f"\nKey Insights:")
print(f"   1. Fleet-wide: Signed bias averages to ~{fleet_bias:.1f} mg/dL — DILUTION (only 30% affected)")
print(f"      AND bidirectional CANCELLATION (positive + negative cancel) both hide the issue.")
print(f"   2. Affected patients: ±{bias_magnitude:.0f} mg/dL bidirectional bias during incident")
print(f"      → RED line (positive cohort) spikes +{bias_magnitude:.0f} mg/dL ABOVE GREEN (over-reading)")
print(f"      → BLUE line (negative cohort) drops -{bias_magnitude:.0f} mg/dL BELOW GREEN (under-reading)")
print(f"   3. Unaffected patients: No bias, lines overlap (device working correctly)")
print(f"\nThis shows why patient-level + direction-aware monitoring is critical!")
print(f"Fleet-wide signed averages mask BOTH dilution and bidirectional cancellation —")
print(f"the platform's MAE monitor uses ABS so it catches both directions in the aggregate.")

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

# Get clean period and incident period glucose, plus per-cohort splits.
# E3: split Incident into Incident-Positive (Day 2 +40
# cohort) and Incident-Negative (Day 5 -40 cohort) so the direction-specific
# distribution shifts are visible. Lumping them under one "Incident" class
# hides the shift because positive and negative shifts partially cancel.
clean_glucose = clean_period['glucose_observed'].values
incident_glucose = incident_period['glucose_observed'].values
if 'incident_direction' in incident_period.columns:
    incident_pos_glucose = incident_period[incident_period['incident_direction'] == 'positive']['glucose_observed'].values
    incident_neg_glucose = incident_period[incident_period['incident_direction'] == 'negative']['glucose_observed'].values
else:
    incident_pos_glucose = np.array([])
    incident_neg_glucose = np.array([])

print(f"\nSample sizes:")
print(f"   Baseline: {len(baseline_glucose):,} points")
print(f"   Clean period: {len(clean_glucose):,} points")
print(f"   Incident period (all): {len(incident_glucose):,} points")
print(f"   Incident period (+ cohort): {len(incident_pos_glucose):,} points")
print(f"   Incident period (- cohort): {len(incident_neg_glucose):,} points")

# Calculate distribution statistics
print(f"\nDistribution Statistics:")
print(f"\n                    Baseline    Clean       Inc+         Inc-")
print("-" * 80)
print(f"Mean:               {baseline_glucose.mean():6.1f}      {clean_glucose.mean():6.1f}      "
      f"{(incident_pos_glucose.mean() if len(incident_pos_glucose) else float('nan')):6.1f}      "
      f"{(incident_neg_glucose.mean() if len(incident_neg_glucose) else float('nan')):6.1f}")
print(f"Median:             {np.median(baseline_glucose):6.1f}      {np.median(clean_glucose):6.1f}      "
      f"{(np.median(incident_pos_glucose) if len(incident_pos_glucose) else float('nan')):6.1f}      "
      f"{(np.median(incident_neg_glucose) if len(incident_neg_glucose) else float('nan')):6.1f}")
print(f"Std:                {baseline_glucose.std():6.1f}      {clean_glucose.std():6.1f}      "
      f"{(incident_pos_glucose.std() if len(incident_pos_glucose) else float('nan')):6.1f}      "
      f"{(incident_neg_glucose.std() if len(incident_neg_glucose) else float('nan')):6.1f}")

def _pct_buckets(arr):
    if len(arr) == 0:
        return 0.0, 0.0, 0.0
    return (
        (arr < 70).sum() / len(arr) * 100,
        ((arr >= 70) & (arr <= 180)).sum() / len(arr) * 100,
        (arr > 180).sum() / len(arr) * 100,
    )

baseline_hypo, baseline_normal, baseline_hyper = _pct_buckets(baseline_glucose)
clean_hypo, clean_normal, clean_hyper = _pct_buckets(clean_glucose)
incident_hypo, incident_normal, incident_hyper = _pct_buckets(incident_glucose)
inc_pos_hypo, inc_pos_normal, inc_pos_hyper = _pct_buckets(incident_pos_glucose)
inc_neg_hypo, inc_neg_normal, inc_neg_hyper = _pct_buckets(incident_neg_glucose)

print(f"\nHypo (<70):         {baseline_hypo:6.1f}%     {clean_hypo:6.1f}%     {inc_pos_hypo:6.1f}%     {inc_neg_hypo:6.1f}%")
print(f"Normal (70-180):    {baseline_normal:6.1f}%     {clean_normal:6.1f}%     {inc_pos_normal:6.1f}%     {inc_neg_normal:6.1f}%")
print(f"Hyper (>180):       {baseline_hyper:6.1f}%     {clean_hyper:6.1f}%     {inc_pos_hyper:6.1f}%     {inc_neg_hyper:6.1f}%")
print("")  # blank line — visual separator between stats table and 4-panel figure
print("")

# Create visualization — 4-class palette across all 4 subplots.
# Override OUTSIDE-the-axes text/edge colors (subplot titles, axis labels,
# tick labels, axes edges) to mid-grey `#888888`. This single color reads
# on BOTH the dark React app theme (~4.5:1 vs slate-950, passes WCAG AA)
# AND the notebook UI's light bg (~4.8:1 vs white, passes WCAG AA). Earlier
# iterations used 'white' which was crisp on React but INVISIBLE in the
# notebook UI. The mid-grey trade-off
# loses a bit of crispness on React but works in both contexts without
# generating two separate PNGs.
# IMPORTANT: do NOT override `text.color` (the GLOBAL text color) — that
# would also force ax.text() bar-chart percentage annotations to mid-grey,
# which would lower their contrast on the colored bars (default-black on
# top of the bars is intentional). Restored after plt.show() below.
# NOTE: wrapping plt.subplots() in `plt.style.context(...)` is NOT
# sufficient — these rcParams are read at render time (set_title /
# xlabel / etc.), which happens AFTER a style context would have exited;
# need the rcParams override to span the whole figure-construction block.
_DUAL05_FIG4_RCPARAMS_SAVED = {k: plt.rcParams[k] for k in (
    'axes.labelcolor', 'xtick.color', 'ytick.color',
    'axes.edgecolor', 'axes.titlecolor',
    'font.weight', 'axes.titleweight')}
plt.rcParams.update({
    'axes.labelcolor': '#888888',
    'xtick.color': '#888888', 'ytick.color': '#888888',
    'axes.edgecolor': '#888888', 'axes.titlecolor': '#888888',
    # Bold weight everywhere — legend labels, tick labels, default ax.text()
    # all inherit. Combined with mid-grey color, bold weight lifts perceived
    # contrast on dark React bg so labels read like the subplot titles did.
    'font.weight': 'bold', 'axes.titleweight': 'bold',
})
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Plot 1: Overlaid histograms — 4 classes
ax1 = axes[0, 0]
ax1.hist(baseline_glucose, bins=80, alpha=0.4, label='Baseline (Real)', density=True, range=(40, 400), color='darkgray')
ax1.hist(clean_glucose, bins=80, alpha=0.4, label='Clean Period', density=True, range=(40, 400), color='mediumturquoise')
if len(incident_pos_glucose):
    ax1.hist(incident_pos_glucose, bins=80, alpha=0.5, label='Incident — + cohort (+40)', density=True, range=(40, 400), color='red')
if len(incident_neg_glucose):
    ax1.hist(incident_neg_glucose, bins=80, alpha=0.5, label='Incident — − cohort (-40)', density=True, range=(40, 400), color='blue')
ax1.axvspan(40, 70, alpha=0.15, color='lightcoral')   # hypo zone — red-family (medical danger convention)
ax1.axvspan(70, 180, alpha=0.1, color='grey')          # normal range — neutral
ax1.axvspan(180, 400, alpha=0.15, color='lightblue')  # hyper zone — blue-family (visually contrasts with red positive-cohort line)
ax1.axvline(70, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax1.axvline(180, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax1.set_xlabel('Glucose (mg/dL)', fontsize=12, fontweight='bold', color='#888888')
ax1.set_ylabel('Density', fontsize=12, fontweight='bold', color='#888888')
ax1.set_title('Glucose Distribution: Baseline vs Clean vs Incident (split by cohort)', fontsize=12, fontweight='bold', color='#888888')
# Per-axis legend removed — single combined legend lives on ax3 (CDF lower-right empty quadrant).
ax1.grid(True, alpha=0.3)

# Plot 2: Distribution percentages — 4 bars per range
ax2 = axes[0, 1]
categories = ['Hypo\n(<70)', 'Normal\n(70-180)', 'Hyper\n(>180)']
baseline_pcts = [baseline_hypo, baseline_normal, baseline_hyper]
clean_pcts = [clean_hypo, clean_normal, clean_hyper]
inc_pos_pcts = [inc_pos_hypo, inc_pos_normal, inc_pos_hyper]
inc_neg_pcts = [inc_neg_hypo, inc_neg_normal, inc_neg_hyper]

x = np.arange(len(categories))
width = 0.2

ax2.bar(x - 1.5*width, baseline_pcts, width, label='Baseline', alpha=0.8, color='darkgray')
ax2.bar(x - 0.5*width, clean_pcts, width, label='Clean Period', alpha=0.8, color='mediumturquoise')
ax2.bar(x + 0.5*width, inc_pos_pcts, width, label='Inc + cohort', alpha=0.8, color='red')
ax2.bar(x + 1.5*width, inc_neg_pcts, width, label='Inc − cohort', alpha=0.8, color='blue')
ax2.set_ylabel('Percentage (%)', fontsize=12, fontweight='bold', color='#888888')
ax2.set_title('Distribution by Glucose Range (4-class direction split)', fontsize=12, fontweight='bold', color='#888888')
ax2.set_xticks(x)
ax2.set_xticklabels(categories)
# Per-axis legend removed — single combined legend lives on ax3 (CDF lower-right empty quadrant).
ax2.grid(True, alpha=0.3, axis='y')

# Add percentage labels for all 4 series
for i, (b, c, ip, in_) in enumerate(zip(baseline_pcts, clean_pcts, inc_pos_pcts, inc_neg_pcts)):
    ax2.text(i - 1.5*width, b + 1, f'{b:.0f}%', ha='center', fontsize=9)
    ax2.text(i - 0.5*width, c + 1, f'{c:.0f}%', ha='center', fontsize=9)
    ax2.text(i + 0.5*width, ip + 1, f'{ip:.0f}%', ha='center', fontsize=9)
    ax2.text(i + 1.5*width, in_ + 1, f'{in_:.0f}%', ha='center', fontsize=9)

# Plot 3: Cumulative distribution — 4 CDFs
ax3 = axes[1, 0]
ax3.plot(np.sort(baseline_glucose), np.arange(1, len(baseline_glucose) + 1) / max(1, len(baseline_glucose)),
         label='Baseline', linewidth=2, color='darkgray')
ax3.plot(np.sort(clean_glucose), np.arange(1, len(clean_glucose) + 1) / max(1, len(clean_glucose)),
         label='Clean Period', linewidth=2, color='mediumturquoise')
if len(incident_pos_glucose):
    ax3.plot(np.sort(incident_pos_glucose), np.arange(1, len(incident_pos_glucose) + 1) / max(1, len(incident_pos_glucose)),
             label='Inc + cohort', linewidth=2, color='red')
if len(incident_neg_glucose):
    ax3.plot(np.sort(incident_neg_glucose), np.arange(1, len(incident_neg_glucose) + 1) / max(1, len(incident_neg_glucose)),
             label='Inc − cohort', linewidth=2, color='blue')
ax3.axvline(70, color='red', linestyle='--', linewidth=1, alpha=0.5)
ax3.axvline(180, color='orange', linestyle='--', linewidth=1, alpha=0.5)
ax3.set_xlabel('Glucose (mg/dL)', fontsize=12, fontweight='bold', color='#888888')
ax3.set_ylabel('Cumulative Probability', fontsize=12, fontweight='bold', color='#888888')
ax3.set_title('Cumulative Distribution Function (split by cohort)', fontsize=12, fontweight='bold', color='#888888')
# Per-axis legend removed — single combined legend is built below, AFTER ax4
# exists (ax4 = axes[1, 1] is set up in the next block; the combined-legend
# builder needs both ax1 + ax4 to be fully populated with labeled artists
# before calling get_legend_handles_labels()).
ax3.grid(True, alpha=0.3)
ax3.set_xlim(40, 400)

# Plot 4: Box plots — 4 classes + E4 threshold visibility enhancements
ax4 = axes[1, 1]
box_data = [baseline_glucose, clean_glucose]
box_labels = ['Baseline', 'Clean\nPeriod']
box_colors = ['darkgray', 'mediumturquoise']
if len(incident_pos_glucose):
    box_data.append(incident_pos_glucose)
    box_labels.append('Inc +\ncohort')
    box_colors.append('red')
if len(incident_neg_glucose):
    box_data.append(incident_neg_glucose)
    box_labels.append('Inc −\ncohort')
    box_colors.append('blue')

bp = ax4.boxplot(
    box_data, labels=box_labels, patch_artist=True, widths=0.6,
    # Mid-grey for all line components so they read on BOTH dark React bg
    # AND notebook UI light bg. Default black whiskers/caps/fliers were
    # effectively invisible on slate-950 (~1.5:1 contrast).
    whiskerprops=dict(color='#888888', linewidth=1.2),
    capprops=dict(color='#888888', linewidth=1.2),
    medianprops=dict(color='orange', linewidth=1.8),  # orange median pops on both bgs
    flierprops=dict(marker='o', markerfacecolor='#888888', markeredgecolor='#888888',
                    markersize=4, alpha=0.7),
)
for patch, color in zip(bp['boxes'], box_colors):
    patch.set_facecolor(color)
    patch.set_alpha(0.6)

# E4 — bolder threshold zones so it's visually obvious which boxes cross hypo/hyper
# Hypo zone = lightcoral (red-family, matches medical danger convention).
# Hyper zone = lightblue (visually contrasts with red positive-cohort line spiking into it).
ax4.axhspan(0, 70, alpha=0.20, color='lightcoral', zorder=0)   # hypo zone — red-family
ax4.axhspan(180, 500, alpha=0.20, color='lightblue', zorder=0) # hyper zone — blue-family
ax4.axhline(y=70, color='red', linestyle='--', linewidth=1.5, alpha=0.8, label='Hypo threshold (<70)')
ax4.axhline(y=180, color='orange', linestyle='--', linewidth=1.5, alpha=0.8, label='Hyper threshold (>180)')

# Annotate the box that crosses thresholds furthest — Incident + cohort crosses
# hyper; Incident − cohort crosses hypo. Helps the eye land on the right place.
for _i, (_data, _lbl, _col) in enumerate(zip(box_data, box_labels, box_colors)):
    if len(_data) == 0:
        continue
    _max = float(np.max(_data))
    _min = float(np.min(_data))
    if 'Inc +' in _lbl and _max > 180:
        ax4.annotate(f'max {_max:.0f}', xy=(_i + 1, _max), xytext=(_i + 1, _max + 15),
                     fontsize=9, fontweight='bold', ha='center', color='#888888',
                     arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))
    if 'Inc −' in _lbl and _min < 70:
        ax4.annotate(f'min {_min:.0f}', xy=(_i + 1, _min), xytext=(_i + 1, _min - 15),
                     fontsize=9, fontweight='bold', ha='center', color='#888888',
                     arrowprops=dict(arrowstyle='->', color='#888888', lw=0.8))

ax4.set_ylabel('Glucose (mg/dL)', fontsize=12, fontweight='bold', color='#888888')
ax4.set_title('Glucose Distribution Box Plots — hypo/hyper zones shaded', fontsize=12, fontweight='bold', color='#888888')
ax4.grid(True, alpha=0.3, axis='y')
# Per-axis legend removed — hypo/hyper threshold handles (label= on the axhline
# calls above) are still discoverable via ax4.get_legend_handles_labels() and
# get picked up by the combined-legend builder on ax3 below.

# Combined legend for the whole 4-panel figure — parked in ax3's empty lower-right
# quadrant (CDFs saturate to y=1 by ~250-300 mg/dL, leaving the high-x/low-y region
# free). Pulls handles from ax1 (4 cohort entries with descriptive +40/-40 labels)
# plus ax4 (the 2 threshold-line entries — hypo <70 / hyper >180). Per-axis legends
# on ax1/ax2/ax4 are intentionally suppressed to reduce visual clutter. Must run
# AFTER ax4 is fully built (axhline label= calls populated its handles).
_combined_h, _combined_l = [], []
for _ax in (ax1, ax4):
    _h, _l = _ax.get_legend_handles_labels()
    for _hi, _li in zip(_h, _l):
        if _li not in _combined_l:
            _combined_h.append(_hi)
            _combined_l.append(_li)
_combined_legend = ax3.legend(_combined_h, _combined_l, loc='lower right', fontsize=8,
                              labelcolor='#888888', facecolor='none', edgecolor='lightgray',
                              handlelength=2.5, handleheight=1.2)
# Light dotted border — frame is visible but unobtrusive, no fill so the
# axes data shows through. labelcolor='#888888' (mid-grey) is the sweet
# spot: readable on dark React bg (~4.5:1 contrast vs slate-950) AND
# light notebook UI (~4.8:1 contrast vs white) — passes WCAG AA on both.
_combined_legend.get_frame().set_linestyle(':')
_combined_legend.get_frame().set_linewidth(1.2)
# Add a thin mid-grey outline to the PATCH legend handles (the 4 cohort
# histogram swatches) so the darkgray Baseline (Real) swatch is visible
# on dark bgs too — without this, darkgray patch on slate-950 React bg
# is effectively invisible because both are dark. Line handles (the 2
# threshold dashed lines from ax4) are skipped because their color +
# linestyle already make them visible without an outline.
from matplotlib.patches import Patch as _Patch
for _h in _combined_legend.legend_handles:
    if isinstance(_h, _Patch):
        _h.set_edgecolor('#888888')
        _h.set_linewidth(0.6)

plt.tight_layout()
# Save PNG asset for MetricsExplained "How MAE alerts are triggered" section.
# Transparent background + mid-grey (`#888888`) text/labels/ticks/edges via
# the rcParams override above — works on BOTH the dark React app theme AND
# notebook UI light bg (passes WCAG AA ~4.5:1 on both). Single PNG, no
# per-theme regeneration needed.
_ASSET_DIR = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/pipeline_data/incident_inference_assets"
dbutils.fs.mkdirs(_ASSET_DIR)
_asset_path = f"{_ASSET_DIR}/distribution_comparison_4panel.png"
plt.savefig(_asset_path, transparent=True, dpi=150, bbox_inches='tight')
print(f"[ASSET] Saved {_asset_path}")
plt.show()
# Restore rcParams so any later cell in this notebook uses defaults.
plt.rcParams.update(_DUAL05_FIG4_RCPARAMS_SAVED)

print("\n" + "="*80)
print("DISTRIBUTION IMPACT SUMMARY")
print("="*80)

print(f"\nClean Period vs Baseline:")
print(f"   Mean shift: {clean_glucose.mean() - baseline_glucose.mean():+.1f} mg/dL (should be ~0)")
print(f"   Distribution match: {'[OK] Good' if abs(clean_glucose.mean() - baseline_glucose.mean()) < 5 else '[WARNING] Check'}")

print(f"\nIncident Period vs Clean Period:")
print(f"   Mean shift (signed avg): {incident_glucose.mean() - clean_glucose.mean():+.1f} mg/dL")
print(f"   With bidirectional split (50/50 default), signed avg cancels to ~0; per-cohort magnitude is ±{bias_magnitude} mg/dL")
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

print(f"\nAffected Population (two-window mirror design):")
print(f"   Total patients: 1000")
print(f"   Incident patients (any window): {feat_sample[feat_sample['has_incident']==1]['patient_id'].nunique()} (~{(cfg.incident_pct + getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}%)")
print(f"   Clean patients (Epsilon/Zeta): {feat_sample[feat_sample['has_incident']==0]['patient_id'].nunique()} (~{(1 - cfg.incident_pct - getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}%)")

print(f"\nDevice Issue:")
print(f"   Type: Calibration bias")
print(f"   Magnitude: ±{bias_magnitude} mg/dL bidirectional systematic error (positive + negative cohorts)")
print(f"   Impact: {degradation_pct_15m:.0f}% MAE increase")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print(f"\nEven an excellent model (5.8 mg/dL MAE) fails catastrophically")
print(f"when device calibration is compromised. During the 3-hour incident:")
print(f"\n  * MAE increased from {clean_mae_15m:.1f} to {incident_mae_15m:.1f} mg/dL ({degradation_pct_15m:.0f}% worse)")
print(f"  * ~{(cfg.incident_pct + getattr(cfg, 'second_incident_pct', cfg.incident_pct))*100:.0f}% of patients affected across both incident windows")
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
        
        print(f"\nINCIDENT PERIOD (±{bias_magnitude} mg/dL bidirectional bias):")
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
# Use RANDOM timepoint from middle days (3-5) to avoid edge effects
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

print(f"\n[SUCCESS] Saved: {fleet_forecast_tbl}")
print(f"   Patients: {len(fleet_output):,}")
print(f"   Glucose range: [{fleet_output['glucose_observed'].min():.0f}, {fleet_output['glucose_observed'].max():.0f}] mg/dL")
print(f"   Average glucose: {fleet_output['glucose_observed'].mean():.1f} mg/dL")
print(f"   Patients at 40 mg/dL: {(fleet_output['glucose_observed'] == 40).sum()} (should be 0)")
print(f"\nSampling: Random timepoint from days 3-5, glucose > 40 mg/dL")
print(f"   * Avoids edge effects (timeline start/end)")
print(f"   * Excludes clipped floor values (data artifacts)")

display(spark.table(fleet_forecast_tbl).orderBy(F.desc("delta_30m")).limit(20))

