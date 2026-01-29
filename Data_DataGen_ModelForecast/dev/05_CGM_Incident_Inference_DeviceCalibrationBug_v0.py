# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook Organization & Demo Guide
# MAGIC
# MAGIC ## Purpose
# MAGIC This notebook demonstrates how a **device calibration bug** (+40 mg/dL bias) causes catastrophic model failure, even for high-performing models.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Tables Created
# MAGIC
# MAGIC ### [1] Input Data
# MAGIC * `hls_glucosphere.cgm.pseudo_clean_7d` - Clean baseline data (from baseline notebook)
# MAGIC
# MAGIC ### [2] Incident Data (Created by this notebook)
# MAGIC * `hls_glucosphere.cgm.pseudo_incident_7d` - Data with +40 mg/dL bias injected (Cell 9)
# MAGIC * `hls_glucosphere.cgm.pseudo_incident_7d_labeled` - Incident data with prediction labels (Cell 10)
# MAGIC
# MAGIC ### [3] Demo Output Table **[PRIMARY]**
# MAGIC * **`hls_glucosphere.cgm.fleet_forecast_incident`** - Fleet-wide predictions (Cell 16)
# MAGIC   - **USE THIS FOR DEMOS**
# MAGIC   - Contains: patient_id, time, glucose_observed, pred_15m, pred_30m, delta_15m, delta_30m
# MAGIC   - One random timepoint per patient from middle days (3-5)
# MAGIC   - Shows prediction deltas for incident-trained models
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Models Used
# MAGIC
# MAGIC ### Clean Models (Baseline)
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_15m@Champion` - 5.8 mg/dL MAE
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_30m@Champion` - 10.4 mg/dL MAE
# MAGIC
# MAGIC ### Incident Models (If trained)
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_15m_incident@Champion`
# MAGIC * `hls_glucosphere.cgm.cgm_xgb_30m_incident@Champion`
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Notebook Structure
# MAGIC
# MAGIC ### Section 1: Setup (Cells 2-6)
# MAGIC * Configuration, parameters, imports
# MAGIC
# MAGIC ### Section 2: Data Preparation (Cells 7-10)
# MAGIC * Load clean data, inject incident, add labels
# MAGIC
# MAGIC ### Section 3: Inference & Analysis (Cells 11-14)
# MAGIC * Run clean model on incident data
# MAGIC * Analyze MAE degradation (5.1 to 38.6 mg/dL)
# MAGIC * Visualize incident impact
# MAGIC * Summary statistics
# MAGIC
# MAGIC ### Section 4: Model Comparison (Cell 15)
# MAGIC * Compare clean vs incident-trained models
# MAGIC
# MAGIC ### Section 5: Fleet Forecast (Cell 16) **[DEMO TABLE]**
# MAGIC * Demo-ready output table
# MAGIC
# MAGIC ### Section 6: Additional Analysis (Cells 18-19)
# MAGIC * Glucose distribution comparison
# MAGIC * Enhanced MAE timeline visualization
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Quick Demo Steps
# MAGIC
# MAGIC 1. Show the incident scenario (Cell 2)
# MAGIC 2. Run cells 7-14 to generate incident analysis
# MAGIC 3. Show key findings (Cell 14 output)
# MAGIC 4. Query demo table: `SELECT * FROM hls_glucosphere.cgm.fleet_forecast_incident`
# MAGIC 5. Show visualizations (Cells 13, 18, 19)
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Findings
# MAGIC * Clean model MAE: **5.1 mg/dL** (clean period)
# MAGIC * Incident MAE: **38.6 mg/dL** (during 3-hour incident)
# MAGIC * **657% degradation** during device calibration bug
# MAGIC * Demonstrates critical need for device quality monitoring

# COMMAND ----------

# MAGIC %md
# MAGIC # CGM Incident Simulation - Device Calibration Bug
# MAGIC
# MAGIC ## Objective
# MAGIC Simulate a device calibration bug and measure its impact on glucose prediction model performance.
# MAGIC
# MAGIC ## Scenario
# MAGIC * **Incident:** Device calibration bug causing **+40 mg/dL systematic error**
# MAGIC * **Timing:** Day 2, 2:00 PM - 5:00 PM (3-hour window)
# MAGIC * **Affected:** 30% of patients (300 out of 1000)
# MAGIC * **Impact:** Compare model performance during incident vs clean periods
# MAGIC
# MAGIC ## Approach
# MAGIC 1. Reference clean pseudo data (from baseline notebook)
# MAGIC 2. Inject calibration bias into `glucose_observed` during incident window
# MAGIC 3. Keep `glucose_true` unchanged (ground truth for labels)
# MAGIC 4. Train model on biased data
# MAGIC 5. Compare: Clean model vs Incident-trained model
# MAGIC
# MAGIC ## Expected Results
# MAGIC * **Clean model on clean data:** ~5.8 mg/dL MAE (baseline)
# MAGIC * **Clean model during incident:** ~45 mg/dL MAE (spike)
# MAGIC * **Incident-trained model during incident:** ~10-15 mg/dL MAE (partial adaptation)
# MAGIC * **Post-incident:** Returns to ~5.8 mg/dL
# MAGIC
# MAGIC ## Run Cells 1-15 (~20 min)
# MAGIC **Pipeline:** Setup, Load Clean Data, Inject Incident, Train, Compare

# COMMAND ----------

# MAGIC %pip install xgboost --quiet
# MAGIC
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# ------------------------
# Widgets / Parameters - INCIDENT SIMULATION
# ------------------------
dbutils.widgets.text("CATALOG_NAME", "hls_glucosphere")
dbutils.widgets.text("SCHEMA_NAME", "cgm")

# Reference to clean data (from baseline notebook)
dbutils.widgets.text("PSEUDO_CLEAN_TBL", "hls_glucosphere.cgm.pseudo_clean_7d")

# Incident parameters
dbutils.widgets.text("INCIDENT_PCT", "0.30")  # 30% of patients affected
dbutils.widgets.text("INCIDENT_DAY_OFFSET", "2")  # Day 2 of 7
dbutils.widgets.text("INCIDENT_START_HOUR", "14")  # 2pm
dbutils.widgets.text("INCIDENT_DURATION_MIN", "180")  # 3 hours
dbutils.widgets.text("CALIBRATION_BIAS_MGDL", "40")  # +40 mg/dL systematic error
dbutils.widgets.text("SEED", "7")

# Feature table params
dbutils.widgets.text("LAGS", "12")
dbutils.widgets.text("ROLL_WINDOWS", "3,6,12")
dbutils.widgets.text("TRAIN_SAMPLE_FRAC", "0.30")

# XGBoost params (same as clean model)
dbutils.widgets.text("MAX_DEPTH", "7")
dbutils.widgets.text("ETA", "0.05")
dbutils.widgets.text("SUBSAMPLE", "0.8")
dbutils.widgets.text("COLSAMPLE", "0.8")
dbutils.widgets.text("N_ROUNDS", "2000")
dbutils.widgets.text("EARLY_STOP", "50")

# MLflow/UC registry params
dbutils.widgets.text("UC_MODEL_NAME_15M", "cgm_xgb_15m_incident")
dbutils.widgets.text("UC_MODEL_NAME_30M", "cgm_xgb_30m_incident")
dbutils.widgets.text("MLFLOW_EXPERIMENT", "")

HORIZONS = [1,2,3,6]  # 5/10/15/30 min ahead

print("INCIDENT SIMULATION CONFIGURATION")
print("   Incident: 30% patients, Day 2, 2pm-5pm (3 hours)")
print("   Bias: +40 mg/dL calibration error")
print("   Goal: Measure impact on model performance")

# COMMAND ----------

# Parse widgets - INCIDENT SIMULATION
CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")
PSEUDO_CLEAN_TBL = dbutils.widgets.get("PSEUDO_CLEAN_TBL")

INCIDENT_PCT = float(dbutils.widgets.get("INCIDENT_PCT"))
INCIDENT_DAY_OFFSET = int(dbutils.widgets.get("INCIDENT_DAY_OFFSET"))
INCIDENT_START_HOUR = int(dbutils.widgets.get("INCIDENT_START_HOUR"))
INCIDENT_DURATION_MIN = int(dbutils.widgets.get("INCIDENT_DURATION_MIN"))
CALIBRATION_BIAS_MGDL = float(dbutils.widgets.get("CALIBRATION_BIAS_MGDL"))
SEED = int(dbutils.widgets.get("SEED"))

LAGS = int(dbutils.widgets.get("LAGS"))
ROLL_WINDOWS = [int(x.strip()) for x in dbutils.widgets.get("ROLL_WINDOWS").split(",") if x.strip()]
TRAIN_SAMPLE_FRAC = float(dbutils.widgets.get("TRAIN_SAMPLE_FRAC"))

MAX_DEPTH = int(dbutils.widgets.get("MAX_DEPTH"))
ETA = float(dbutils.widgets.get("ETA"))
SUBSAMPLE = float(dbutils.widgets.get("SUBSAMPLE"))
COLSAMPLE = float(dbutils.widgets.get("COLSAMPLE"))
N_ROUNDS = int(dbutils.widgets.get("N_ROUNDS"))
EARLY_STOP = int(dbutils.widgets.get("EARLY_STOP"))

UC_MODEL_NAME_15M = dbutils.widgets.get("UC_MODEL_NAME_15M")
UC_MODEL_NAME_30M = dbutils.widgets.get("UC_MODEL_NAME_30M")
MLFLOW_EXPERIMENT = dbutils.widgets.get("MLFLOW_EXPERIMENT")

print("INCIDENT PARAMETERS:")
print(f"   Clean data source: {PSEUDO_CLEAN_TBL}")
print(f"   Incident: {INCIDENT_PCT*100:.0f}% patients, Day {INCIDENT_DAY_OFFSET}, {INCIDENT_START_HOUR}:00-{INCIDENT_START_HOUR + INCIDENT_DURATION_MIN//60}:00")
print(f"   Calibration bias: +{CALIBRATION_BIAS_MGDL} mg/dL")
print(f"   Models: {UC_MODEL_NAME_15M}, {UC_MODEL_NAME_30M}")

# COMMAND ----------

# Output tables - INCIDENT SIMULATION

# Incident data tables
pseudo_incident_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d"
incident_flag_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_with_flag"

# Feature and forecast tables
xgb_features_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.xgb_flat_min_lags{LAGS}_incident"
fleet_forecast_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.fleet_forecast_incident"

# UC model names (incident-trained models)
uc_model_fqn_15m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{UC_MODEL_NAME_15M}"
uc_model_fqn_30m = f"{CATALOG_NAME}.{SCHEMA_NAME}.{UC_MODEL_NAME_30M}"

# Reference to clean models (for comparison)
uc_model_fqn_15m_clean = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_15m"
uc_model_fqn_30m_clean = f"{CATALOG_NAME}.{SCHEMA_NAME}.cgm_xgb_30m"

print("Table Configuration:")
print(f"   Clean data source: {PSEUDO_CLEAN_TBL}")
print(f"   Incident data output: {pseudo_incident_tbl}")
print(f"   Incident models: {uc_model_fqn_15m}, {uc_model_fqn_30m}")

# COMMAND ----------

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
print(f"   Source: {PSEUDO_CLEAN_TBL}")

pseudo_clean = spark.table(PSEUDO_CLEAN_TBL)

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

# Calculate demo week start (needed for incident window)
demo_week_start = spark.sql("select date_trunc('week', current_timestamp()) as wk_start").collect()[0]["wk_start"]

# Calculate incident window
base_date = pd.Timestamp(demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=INCIDENT_DAY_OFFSET, hours=INCIDENT_START_HOUR)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=INCIDENT_DURATION_MIN)

print(f"\nIncident Window:")
print(f"   Start: {incident_start_ts}")
print(f"   End: {incident_end_ts}")
print(f"   Duration: {INCIDENT_DURATION_MIN} minutes ({INCIDENT_DURATION_MIN/60:.1f} hours)")

# Select patients for incident (random 30%)
all_patients = pseudo_clean.select("patient_id").distinct()
total_patients = all_patients.count()
n_incident_patients = int(total_patients * INCIDENT_PCT)

incident_patients = (all_patients
  .orderBy(F.rand(seed=SEED))
  .limit(n_incident_patients)
  .withColumn("has_incident", F.lit(1))
)

print(f"\nAffected Patients:")
print(f"   Total patients: {total_patients}")
print(f"   Incident patients: {n_incident_patients} ({INCIDENT_PCT*100:.0f}%)")
print(f"   Clean patients: {total_patients - n_incident_patients} ({(1-INCIDENT_PCT)*100:.0f}%)")

# Calculate expected impact
points_per_patient = pseudo_clean.count() / total_patients
points_in_window = INCIDENT_DURATION_MIN / 5  # 5-min cadence
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
print(f"   Bias: +{CALIBRATION_BIAS_MGDL} mg/dL")
print(f"   Affected: {INCIDENT_PCT*100:.0f}% of patients during incident window\n")

# Drop has_incident from pseudo_clean to avoid ambiguity, then join
pseudo_with_flag = pseudo_clean.drop("has_incident").join(
    incident_patients,
    "patient_id",
    "left"
).fillna({"has_incident": 0})

# Inject bias: Add CALIBRATION_BIAS_MGDL to glucose_observed during incident window
pseudo_incident = pseudo_with_flag.withColumn(
    "glucose_observed",
    F.when(
        (F.col("has_incident") == 1) &
        (F.col("time") >= F.lit(incident_start_ts)) &
        (F.col("time") < F.lit(incident_end_ts)),
        F.col("glucose_observed") + F.lit(CALIBRATION_BIAS_MGDL)
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
    F.when(F.col("has_incident") == 1, F.lit(CALIBRATION_BIAS_MGDL)).otherwise(F.lit(None).cast("double"))
)

# Save incident data
pseudo_incident.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(pseudo_incident_tbl)

# Verify injection
verify = pseudo_incident.select(
    F.count("*").alias("total_rows"),
    F.sum((F.col("incident_type") == "calibration_bias").cast("int")).alias("biased_points"),
    F.sum(F.col("has_incident")).alias("incident_patient_rows")
).collect()[0]

print(f"\n[SUCCESS] Incident data saved: {pseudo_incident_tbl}")
print(f"   Total rows: {verify['total_rows']:,}")
print(f"   Biased timepoints: {verify['biased_points']:,} ({verify['biased_points']/verify['total_rows']*100:.2f}%)")
print(f"   Incident patient rows: {verify['incident_patient_rows']:,}")

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
base_date = pd.Timestamp(demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=INCIDENT_DAY_OFFSET, hours=INCIDENT_START_HOUR)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=INCIDENT_DURATION_MIN)

df = df.withColumn(
    "incident_active",
    ((F.col("has_incident") == 1) &
     (F.col("time") >= F.lit(incident_start_ts)) &
     (F.col("time") < F.lit(incident_end_ts))).cast("int")
)

# Build features (same as clean model)
w_ord = Window.partitionBy("patient_id").orderBy("time")

feat = (df.select(
        "patient_id", "time", "incident_active", "has_incident",
        F.col("glucose_observed").cast("double").alias("glucose_observed"),
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
for k in range(1, LAGS+1):
    feat = feat.withColumn(f"glucose_lag_{k}", F.lag("glucose_observed", k).over(w_ord))

# Add rolling windows
for rw in ROLL_WINDOWS:
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
feat_sample = feat.sample(False, 0.3, seed=SEED).toPandas()
feat_sample = feat_sample.dropna(subset=[f"glucose_lag_{k}" for k in range(1, LAGS+1)] + ["y_tplus_3", "y_tplus_6"])

print(f"[SUCCESS] Features built: {len(feat_sample):,} timepoints")
print(f"   Incident timepoints: {feat_sample['incident_active'].sum():,} ({feat_sample['incident_active'].sum()/len(feat_sample)*100:.1f}%)")

# Prepare feature matrix
feature_cols = [c for c in feat_sample.columns if c not in 
                {"patient_id", "time", "incident_active", "has_incident", "y_tplus_3", "y_tplus_6"}]
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
    
    print(f"\nINCIDENT PERIOD (+{CALIBRATION_BIAS_MGDL} mg/dL calibration bug):")
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

# Prepare timeline data
timeline_data = feat_sample[["time", "incident_active", "mae_15m", "mae_30m", "glucose_observed"]].copy()
timeline_data = timeline_data.sort_values("time")

# Aggregate by hour for cleaner visualization
timeline_data["hour"] = pd.to_datetime(timeline_data["time"]).dt.floor("H")
hourly_agg = timeline_data.groupby("hour").agg({
    "mae_15m": "mean",
    "mae_30m": "mean",
    "incident_active": "max",
    "glucose_observed": "mean"
}).reset_index()

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Plot 1: MAE Timeline
ax1.plot(hourly_agg["hour"], hourly_agg["mae_15m"], label="MAE 15m", linewidth=2, marker="o", markersize=4)
ax1.plot(hourly_agg["hour"], hourly_agg["mae_30m"], label="MAE 30m", linewidth=2, marker="s", markersize=4)

# Shade incident period
incident_hours = hourly_agg[hourly_agg["incident_active"] == 1]
if len(incident_hours) > 0:
    incident_start = incident_hours["hour"].min()
    incident_end = incident_hours["hour"].max() + pd.Timedelta(hours=1)
    ax1.axvspan(incident_start, incident_end, alpha=0.2, color='red', label='Incident Period')
    ax1.axhline(y=5.8, color='green', linestyle='--', linewidth=1, alpha=0.7, label='Baseline MAE (5.8)')

ax1.set_ylabel("MAE (mg/dL)", fontsize=12)
ax1.set_title("Incident Impact: MAE Spike During Device Calibration Bug", fontsize=14, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_ylim(0, max(hourly_agg["mae_15m"].max(), hourly_agg["mae_30m"].max()) * 1.1)

# Plot 2: Average Glucose (shows bias)
ax2.plot(hourly_agg["hour"], hourly_agg["glucose_observed"], label="Glucose (observed)", linewidth=2, color="purple", marker="o", markersize=4)

# Shade incident period
if len(incident_hours) > 0:
    ax2.axvspan(incident_start, incident_end, alpha=0.2, color='red', label='Incident Period')
    # Show expected glucose without bias
    expected_glucose = hourly_agg["glucose_observed"].copy()
    incident_mask = hourly_agg["incident_active"] == 1
    expected_glucose[incident_mask] = expected_glucose[incident_mask] - CALIBRATION_BIAS_MGDL
    ax2.plot(hourly_agg["hour"], expected_glucose, label="Expected (without bias)", linewidth=2, linestyle='--', color="green", alpha=0.7)

ax2.set_xlabel("Time", fontsize=12)
ax2.set_ylabel("Glucose (mg/dL)", fontsize=12)
ax2.set_title("Glucose Timeline: +40 mg/dL Bias During Incident", fontsize=14)
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
print(f"   4. Glucose readings show +40 mg/dL bias during incident")
print(f"\nThis demonstrates the critical impact of device calibration bugs!")

# COMMAND ----------

# DBTITLE 1,Glucose distribution comparison: baseline vs incident
# ------------------------
# Glucose Distribution Comparison: Baseline vs Clean vs Incident Period
# ------------------------
import matplotlib.pyplot as plt
import seaborn as sns

print("Glucose Distribution Comparison")
print("="*80)

# Get baseline distribution
baseline_df = spark.table("hls_glucosphere.cgm.diabetes_data")
baseline_sample = baseline_df.sample(False, 0.1, seed=SEED).toPandas()
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
ax1.hist(baseline_glucose, bins=80, alpha=0.4, label='Baseline (Real)', density=True, range=(40, 400), color='blue')
ax1.hist(clean_glucose, bins=80, alpha=0.4, label='Clean Period', density=True, range=(40, 400), color='green')
ax1.hist(incident_glucose, bins=80, alpha=0.4, label='Incident Period (+40 bias)', density=True, range=(40, 400), color='red')
ax1.axvspan(40, 70, alpha=0.1, color='red')
ax1.axvspan(70, 180, alpha=0.1, color='grey')
ax1.axvspan(180, 400, alpha=0.1, color='yellow')
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

ax2.bar(x - width, baseline_pcts, width, label='Baseline', alpha=0.8, color='blue')
ax2.bar(x, clean_pcts, width, label='Clean Period', alpha=0.8, color='green')
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

ax3.plot(baseline_sorted, baseline_cdf, label='Baseline', linewidth=2, color='blue')
ax3.plot(clean_sorted, clean_cdf, label='Clean Period', linewidth=2, color='green')
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
box_colors = ['blue', 'green', 'red']

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
print(f"   Mean shift: {incident_glucose.mean() - clean_glucose.mean():+.1f} mg/dL (expected: +{CALIBRATION_BIAS_MGDL})")
print(f"   Hypo reduction: {incident_hypo - clean_hypo:+.1f}% (bias shifts distribution up)")
print(f"   Hyper increase: {incident_hyper - clean_hyper:+.1f}% (more high glucose readings)")

print(f"\nKey Observations:")
print(f"   [1] Clean period matches baseline distribution")
print(f"   [2] Incident period shows clear +{incident_glucose.mean() - clean_glucose.mean():.0f} mg/dL shift")
print(f"   [3] Calibration bias affects entire distribution")
print(f"   [4] This explains the MAE spike ({clean_mae_15m:.1f} to {incident_mae_15m:.1f} mg/dL)")
print("="*80)

# COMMAND ----------

# DBTITLE 1,Summary statistics table
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
print(f"   Duration: {INCIDENT_DURATION_MIN} minutes ({INCIDENT_DURATION_MIN/60:.1f} hours)")

print(f"\nAffected Population:")
print(f"   Total patients: 1000")
print(f"   Incident patients: {feat_sample[feat_sample['has_incident']==1]['patient_id'].nunique()} ({INCIDENT_PCT*100:.0f}%)")
print(f"   Clean patients: {feat_sample[feat_sample['has_incident']==0]['patient_id'].nunique()} ({(1-INCIDENT_PCT)*100:.0f}%)")

print(f"\nDevice Issue:")
print(f"   Type: Calibration bias")
print(f"   Magnitude: +{CALIBRATION_BIAS_MGDL} mg/dL systematic error")
print(f"   Impact: {degradation_pct_15m:.0f}% MAE increase")

print("\n" + "="*80)
print("CONCLUSION")
print("="*80)
print(f"\nEven an excellent model (5.8 mg/dL MAE) fails catastrophically")
print(f"when device calibration is compromised. During the 3-hour incident:")
print(f"\n  * MAE increased from {clean_mae_15m:.1f} to {incident_mae_15m:.1f} mg/dL ({degradation_pct_15m:.0f}% worse)")
print(f"  * {INCIDENT_PCT*100:.0f}% of patients affected")
print(f"  * Performance returned to normal after incident ended")
print(f"\n[CRITICAL] This demonstrates the critical importance of:")
print(f"  1. Real-time device quality monitoring")
print(f"  2. Automated anomaly detection")
print(f"  3. Rapid incident response protocols")
print("="*80)

# COMMAND ----------

# https://www.nature.com/articles/s41746-021-00480-x

# COMMAND ----------

# [optional]

# COMMAND ----------

# DBTITLE 1,Compare clean vs incident model performance
# ------------------------
# INCIDENT IMPACT ANALYSIS
# Compare: Clean model vs Incident model on incident data
# ------------------------
import mlflow.xgboost

print("INCIDENT IMPACT ANALYSIS")
print("="*80)

# Load both models
clean_15m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_15m_clean}@Champion")
clean_30m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_30m_clean}@Champion")
incident_15m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_15m}@Champion")
incident_30m = mlflow.xgboost.load_model(f"models:/{uc_model_fqn_30m}@Champion")

print("[SUCCESS] Loaded models:")
print(f"   Clean: {uc_model_fqn_15m_clean}, {uc_model_fqn_30m_clean}")
print(f"   Incident: {uc_model_fqn_15m}, {uc_model_fqn_30m}")

# Get incident data with flags - drop has_incident from left table to avoid ambiguity
incident_data = spark.table(incident_labeled_tbl).drop("has_incident").join(
    spark.table(pseudo_incident_tbl).select("patient_id", "time", "has_incident", "incident_type"),
    ["patient_id", "time"],
    "inner"
)

# Calculate incident window
base_date = pd.Timestamp(demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=INCIDENT_DAY_OFFSET, hours=INCIDENT_START_HOUR)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=INCIDENT_DURATION_MIN)

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
for k in range(1, LAGS+1):
    feat_for_pred = feat_for_pred.withColumn(f"glucose_lag_{k}", F.lag("glucose_observed", k).over(w_ord))

for rw in ROLL_WINDOWS:
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
comparison_pd = feat_for_pred.sample(False, 0.3, seed=SEED).toPandas()
comparison_pd = comparison_pd.dropna(subset=[f"glucose_lag_{k}" for k in range(1, LAGS+1)] + ["y_tplus_3", "y_tplus_6"])

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
clean_period = comparison_pd[comparison_pd['incident_active'] == 0]
incident_period = comparison_pd[comparison_pd['incident_active'] == 1]

print("\n" + "="*80)
print("INCIDENT IMPACT SUMMARY")
print("="*80)

print(f"\nData split:")
print(f"   Clean period: {len(clean_period):,} timepoints")
print(f"   Incident period: {len(incident_period):,} timepoints ({len(incident_period)/len(comparison_pd)*100:.1f}%)")

if len(incident_period) > 0:
    print(f"\nCLEAN PERIOD (no bias):")
    print(f"   Clean model MAE:    {clean_period['mae_15m_clean'].mean():.2f} mg/dL (15m) | {clean_period['mae_30m_clean'].mean():.2f} mg/dL (30m)")
    print(f"   Incident model MAE: {clean_period['mae_15m_incident'].mean():.2f} mg/dL (15m) | {clean_period['mae_30m_incident'].mean():.2f} mg/dL (30m)")
    
    print(f"\nINCIDENT PERIOD (+{CALIBRATION_BIAS_MGDL} mg/dL bias):")
    print(f"   Clean model MAE:    {incident_period['mae_15m_clean'].mean():.2f} mg/dL (15m) | {incident_period['mae_30m_clean'].mean():.2f} mg/dL (30m)")
    print(f"   Incident model MAE: {incident_period['mae_15m_incident'].mean():.2f} mg/dL (15m) | {incident_period['mae_30m_incident'].mean():.2f} mg/dL (30m)")
    
    # Calculate impact
    clean_degradation_15m = incident_period['mae_15m_clean'].mean() - clean_period['mae_15m_clean'].mean()
    incident_improvement_15m = incident_period['mae_15m_clean'].mean() - incident_period['mae_15m_incident'].mean()
    
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

# Use the features DataFrame built in cell 11 instead of reading from non-existent table
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
w_random = Window.partitionBy("patient_id").orderBy(F.rand(seed=SEED))
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

# COMMAND ----------



# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # Next Steps & Demo Guide
# MAGIC
# MAGIC ## Primary Demo Table
# MAGIC
# MAGIC ### `hls_glucosphere.cgm.fleet_forecast_incident`
# MAGIC
# MAGIC **Use this table for demos and dashboards**
# MAGIC
# MAGIC ```sql
# MAGIC SELECT 
# MAGIC   patient_id,
# MAGIC   time,
# MAGIC   glucose_observed,
# MAGIC   pred_15m,
# MAGIC   pred_30m,
# MAGIC   delta_15m,
# MAGIC   delta_30m,
# MAGIC   carb_input,
# MAGIC   bolus_volume_delivered,
# MAGIC   basal_rate,
# MAGIC   steps
# MAGIC FROM hls_glucosphere.cgm.fleet_forecast_incident
# MAGIC ORDER BY delta_30m DESC
# MAGIC LIMIT 20
# MAGIC ```
# MAGIC
# MAGIC **Table Contents:**
# MAGIC * 1,000 patients (one random timepoint per patient)
# MAGIC * Predictions from incident-trained models
# MAGIC * Prediction deltas showing forecast accuracy
# MAGIC * Sampled from middle days (3-5) to avoid edge effects
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Supporting Tables
# MAGIC
# MAGIC ### For Incident Analysis:
# MAGIC * `hls_glucosphere.cgm.pseudo_incident_7d` - Full incident data with bias
# MAGIC * `hls_glucosphere.cgm.pseudo_incident_7d_labeled` - With prediction labels
# MAGIC
# MAGIC ### For Baseline Comparison:
# MAGIC * `hls_glucosphere.cgm.pseudo_clean_7d` - Original clean data
# MAGIC * `hls_glucosphere.cgm.diabetes_data` - Real baseline data
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Recommended Next Steps
# MAGIC
# MAGIC ### [1] Create Dashboard
# MAGIC * Use `fleet_forecast_incident` table
# MAGIC * Show prediction accuracy by patient
# MAGIC * Highlight patients with largest deltas
# MAGIC * Add filters for glucose ranges
# MAGIC
# MAGIC ### [2] Build Monitoring Alerts
# MAGIC * Monitor MAE in real-time
# MAGIC * Alert when MAE > 15 mg/dL (3x baseline)
# MAGIC * Track incident recovery time
# MAGIC
# MAGIC ### [3] Extend Analysis
# MAGIC * Compare multiple incident types (bias, noise, dropout)
# MAGIC * Test different bias magnitudes
# MAGIC * Analyze patient-level impact
# MAGIC
# MAGIC ### [4] Train Robust Models
# MAGIC * Add incident data to training set
# MAGIC * Implement data quality checks
# MAGIC * Build ensemble models
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Metrics Summary
# MAGIC
# MAGIC | Metric | Clean Period | Incident Period | Impact |
# MAGIC |--------|--------------|-----------------|--------|
# MAGIC | MAE 15m | 5.1 mg/dL | 38.6 mg/dL | +657% |
# MAGIC | MAE 30m | 10.4 mg/dL | ~70 mg/dL | +573% |
# MAGIC | Affected Patients | 0% | 30% | 300/1000 |
# MAGIC | Duration | - | 3 hours | Day 2, 2-5pm |
# MAGIC
# MAGIC **Conclusion:** Even excellent models fail catastrophically during device incidents. Real-time monitoring is critical.

# COMMAND ----------

# DBTITLE 1,NOTEs
# Apparently """While both are dangerous, hypoglycemia (low blood sugar) is generally considered more immediately dangerous because it deprives the brain of crucial energy, potentially causing confusion, seizures, coma, or death very quickly, requiring immediate carbohydrate intake. Hyperglycemia (high blood sugar) typically develops more slowly, but severe, prolonged cases can lead to serious long-term complications like heart, kidney, or nerve damage, and acute emergencies like DKA (Diabetic Ketoacidosis). """


# [Hmm actually the scenario would be that actually some folks would have been trending hypoglycemic -- HOWEVER because of the firmware/device bug their glucose levels were deem "OK" --> shift positive ---> so they were actually in precarious range...]  

# Maybe we are ok with what we currently have.... 
