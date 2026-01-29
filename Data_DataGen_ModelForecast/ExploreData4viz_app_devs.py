# Databricks notebook source
dbutils.widgets.removeAll()

# COMMAND ----------

# ------------------------
# Widgets / Parameters - INCIDENT SIMULATION
# ------------------------
dbutils.widgets.text("CATALOG_NAME", "hls_glucosphere")
dbutils.widgets.text("SCHEMA_NAME", "cgm")

# Reference to clean data (from baseline notebook)
# dbutils.widgets.text("PSEUDO_CLEAN_TBL", "hls_glucosphere.cgm.pseudo_clean_7d")


# Incident parameters
dbutils.widgets.text("INCIDENT_PCT", "0.30")  # 30% of patients affected
dbutils.widgets.text("INCIDENT_DAY_OFFSET", "2")  # Day 2 of 7
dbutils.widgets.text("INCIDENT_START_HOUR", "14")  # 2pm
dbutils.widgets.text("INCIDENT_DURATION_MIN", "180")  # 3 hours
dbutils.widgets.text("CALIBRATION_BIAS_MGDL", "40")  # +40 mg/dL systematic error

# COMMAND ----------

# Parse widgets - INCIDENT SIMULATION
CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")
# PSEUDO_CLEAN_TBL = dbutils.widgets.get("PSEUDO_CLEAN_TBL")


# COMMAND ----------

# MAGIC %md
# MAGIC

# COMMAND ----------

# DBTITLE 1,Define tables to copy and copy function
# ------------------------
# Define list of tables to copy in Unity Catalog
# ------------------------

suffix2use = "v20260105"

# List of tables to copy (source -> target)
tables_to_copy = [
    {
        "source": "hls_glucosphere.cgm.pseudo_clean_7d",
        "target": f"hls_glucosphere.cgm.pseudo_clean_7d_{suffix2use}",
        "description": "Clean pseudo patients (1000 patients, 7 days)"
    },
    {
        "source": "hls_glucosphere.cgm.pseudo_incident_7d",
        "target": f"hls_glucosphere.cgm.pseudo_incident_7d_{suffix2use}",
        "description": "Incident data with calibration bias"
    },
    {
        "source": "hls_glucosphere.cgm.pseudo_incident_7d_labeled",
        "target": f"hls_glucosphere.cgm.pseudo_incident_7d_labeled_{suffix2use}",
        "description": "Incident data with prediction labels"
    },
    {
        "source": "hls_glucosphere.cgm.fleet_forecast_incident",
        "target": f"hls_glucosphere.cgm.fleet_forecast_incident_{suffix2use}",
        "description": "Fleet predictions (1 timepoint per patient)"
    },
    # {
    #     "source": "hls_glucosphere.cgm.xgb_flat_min_lags12",
    #     "target": f"hls_glucosphere.cgm.xgb_flat_min_lags12_{suffix2use}",
    #     "description": "Feature table for training (clean data)"
    # },
    # {
    #     "source": "hls_glucosphere.cgm.xgb_flat_min_lags12_incident",
    #     "target": f"hls_glucosphere.cgm.xgb_flat_min_lags12_incident_{suffix2use}",
    #     "description": "Feature table for training (incident data)"
    # }
]

print("Tables to copy:")
for i, tbl in enumerate(tables_to_copy, 1):
    print(f"   {i}. {tbl['source']}")
    print(f"      -> {tbl['target']}")
    print(f"      {tbl['description']}")
    print()

print(f"Total: {len(tables_to_copy)} tables")

# COMMAND ----------

# DBTITLE 1,list all tables with suffix2use
from pyspark.sql import functions as F

# Query information_schema to find all tables with v20260105 suffix
tables_with_suffix = spark.sql(f"""
    SELECT 
        table_catalog,
        table_schema,
        table_name,
        CONCAT(table_catalog, '.', table_schema, '.', table_name) as full_table_name,
        table_type
    FROM system.information_schema.tables
    WHERE table_name LIKE '%{suffix2use}%'
    ORDER BY table_catalog, table_schema, table_name
""")

tables_list = tables_with_suffix.collect()

print(f"Found {len(tables_list)} tables with {suffix2use} suffix:")
print("="*80)

for i, row in enumerate(tables_list, 1):
    print(f"\n{i}. {row['full_table_name']}")
    print(f"   Catalog: {row['table_catalog']}")
    print(f"   Schema: {row['table_schema']}")
    print(f"   Type: {row['table_type']}")
    
    # Get row count
    try:
        count = spark.table(row['full_table_name']).count()
        print(f"   Rows: {count:,}")
    except:
        print(f"   Rows: [Unable to count]")

print("\n" + "="*80)
print(f"Total: {len(tables_list)} tables with {suffix2use} suffix")

# COMMAND ----------

# DBTITLE 1,Copy `hls_glucosphere.cgm.{tablename}_{suffix2use}` for AppDev
# ------------------------
# Copy multiple tables using the tables_to_copy list
# ------------------------

def copy_table_safe(source, target, description=""):
    """
    Safely copy a table in Unity Catalog.
    Checks if target exists before creating.
    """
    try:
        # Check if source exists
        source_count = spark.table(source).count()
        print(f"\n[INFO] Source table: {source}")
        print(f"   Rows: {source_count:,}")
        
        # Check if target exists
        try:
            existing_count = spark.table(target).count()
            print(f"[SKIP] Target already exists: {target}")
            print(f"   Existing rows: {existing_count:,}")
            print(f"   To overwrite, manually run: DROP TABLE {target}")
            return "skipped"
        except:
            # Target doesn't exist, create it
            spark.sql(f"CREATE TABLE {target} AS SELECT * FROM {source}")
            target_count = spark.table(target).count()
            
            print(f"[SUCCESS] Created: {target}")
            print(f"   Rows copied: {target_count:,}")
            print(f"   Match: {'✓' if source_count == target_count else '✗'}")
            if description:
                print(f"   Description: {description}")
            return "copied"
            
    except Exception as e:
        print(f"[ERROR] Failed to copy {source}: {str(e)}")
        return "failed"

# Execute table copies using the list from cell 24
print("Starting table copy process...")
print("="*80)

copied = 0
skipped = 0
failed = 0

for tbl in tables_to_copy:
    result = copy_table_safe(tbl['source'], tbl['target'], tbl['description'])
    if result == "copied":
        copied += 1
    elif result == "skipped":
        skipped += 1
    else:
        failed += 1

print("\n" + "="*80)
print("COPY SUMMARY")
print("="*80)
print(f"\n   Copied: {copied}")
print(f"   Skipped (already exist): {skipped}")
print(f"   Failed: {failed}")
print(f"   Total: {len(tables_to_copy)}")

if copied > 0:
    print(f"\n[SUCCESS] {copied} table(s) copied successfully!")
if skipped > 0:
    print(f"\n[INFO] {skipped} table(s) already exist - skipped")
if failed > 0:
    print(f"\n[ERROR] {failed} table(s) failed to copy")

print("\n" + "="*80)

# COMMAND ----------

# pseudoData_incident7dlabeled = spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105')

# display(pseudoData_incident7dlabeled)

# COMMAND ----------

# ------------------------
# Select sample patients: incident vs non-incident
# ------------------------
from pyspark.sql import functions as F
import random

# Get incident patients (has_incident == 1)
incident_patients_df = spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter(
    F.col('has_incident') == 1  # 30% ~300
).select('patient_id').distinct()

incident_patient_list = [row['patient_id'] for row in incident_patients_df.collect()]

# Get non-incident patients (has_incident == 0)
non_incident_patients_df = spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter(
    F.col('has_incident') == 0
).select('patient_id').distinct()

non_incident_patient_list = [row['patient_id'] for row in non_incident_patients_df.collect()]

print(f"Patient counts:")
print(f"   Incident patients: {len(incident_patient_list)}")
print(f"   Non-incident patients: {len(non_incident_patient_list)}")

# Select 3 sample patients from each group
random.seed(7)  # Use seed=7 for reproducibility

sample_incident = random.sample(incident_patient_list, min(3, len(incident_patient_list)))
sample_non_incident = random.sample(non_incident_patient_list, min(3, len(non_incident_patient_list)))

print(f"\nSample patients for plotting:")
print(f"\nIncident patients (has_incident=1):")
for i, pid in enumerate(sample_incident, 1):
    print(f"   {i}. {pid}")

print(f"\nNon-incident patients (has_incident=0):")
for i, pid in enumerate(sample_non_incident, 1):
    print(f"   {i}. {pid}")

print(f"\n[SUCCESS] Sample patients selected")

# COMMAND ----------

# DBTITLE 1,Plot timeseries for sample patients
# ------------------------
# Plot timeseries for sample incident and non-incident patients
# ------------------------
import matplotlib.pyplot as plt
import pandas as pd

# Parse incident parameters from widgets
INCIDENT_DAY_OFFSET = int(dbutils.widgets.get("INCIDENT_DAY_OFFSET"))
INCIDENT_START_HOUR = int(dbutils.widgets.get("INCIDENT_START_HOUR"))
INCIDENT_DURATION_MIN = int(dbutils.widgets.get("INCIDENT_DURATION_MIN"))
CALIBRATION_BIAS_MGDL = float(dbutils.widgets.get("CALIBRATION_BIAS_MGDL"))

# Load full timeseries data for sample patients
all_sample_patients = sample_incident + sample_non_incident

timeseries_data = spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter(
    F.col('patient_id').isin(all_sample_patients)
).select(
    'patient_id', 'time', 'glucose_true', 'glucose_observed', 'has_incident', 'incident_type',
    'carb_input', 'bolus_volume_delivered', 'basal_rate', 'steps'
).orderBy('patient_id', 'time').toPandas()

# Calculate incident window
demo_week_start = spark.sql("select date_trunc('week', current_timestamp()) as wk_start").collect()[0]["wk_start"]
base_date = pd.Timestamp(demo_week_start)
incident_start_ts = base_date + pd.Timedelta(days=INCIDENT_DAY_OFFSET, hours=INCIDENT_START_HOUR)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=INCIDENT_DURATION_MIN)

print(f"Plotting timeseries for {len(all_sample_patients)} patients...")
print(f"   Incident patients: {len(sample_incident)}")
print(f"   Non-incident patients: {len(sample_non_incident)}")
print(f"\nIncident window: {incident_start_ts} to {incident_end_ts}\n")

# Create subplots: 2 rows x 3 columns
fig, axes = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle('Glucose Timeseries: Incident vs Non-Incident Patients', fontsize=16, fontweight='bold')

# Plot incident patients (top row)
for i, patient_id in enumerate(sample_incident):
    ax = axes[0, i]
    patient_data = timeseries_data[timeseries_data['patient_id'] == patient_id].copy()
    patient_data['time'] = pd.to_datetime(patient_data['time'])
    
    # Plot glucose_true and glucose_observed
    ax.plot(patient_data['time'], patient_data['glucose_true'], 
            label='True Glucose', linewidth=2, color='green', alpha=0.8)
    ax.plot(patient_data['time'], patient_data['glucose_observed'], 
            label='Observed Glucose', linewidth=2, color='red', alpha=0.8, linestyle='--')
    
    # Shade incident window
    ax.axvspan(incident_start_ts, incident_end_ts, alpha=0.2, color='red', label='Incident Window')
    
    # Add glucose range lines
    ax.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
    ax.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)
    
    ax.set_title(f'{patient_id}\n[INCIDENT PATIENT]', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time', fontsize=9)
    ax.set_ylabel('Glucose (mg/dL)', fontsize=9)
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(40, 400)
    ax.tick_params(axis='x', rotation=45, labelsize=8)

# Plot non-incident patients (bottom row)
for i, patient_id in enumerate(sample_non_incident):
    ax = axes[1, i]
    patient_data = timeseries_data[timeseries_data['patient_id'] == patient_id].copy()
    patient_data['time'] = pd.to_datetime(patient_data['time'])
    
    # Plot glucose_true and glucose_observed (should be identical)
    ax.plot(patient_data['time'], patient_data['glucose_true'], 
            label='True Glucose', linewidth=2, color='blue', alpha=0.8)
    ax.plot(patient_data['time'], patient_data['glucose_observed'], 
            label='Observed Glucose', linewidth=2, color='cyan', alpha=0.6, linestyle='--')
    
    # Shade incident window (for reference, but no bias for these patients)
    ax.axvspan(incident_start_ts, incident_end_ts, alpha=0.1, color='grey', label='Incident Window (no bias)')
    
    # Add glucose range lines
    ax.axhline(y=70, color='red', linestyle=':', linewidth=1, alpha=0.5)
    ax.axhline(y=180, color='orange', linestyle=':', linewidth=1, alpha=0.5)
    
    ax.set_title(f'{patient_id}\n[NON-INCIDENT PATIENT]', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time', fontsize=9)
    ax.set_ylabel('Glucose (mg/dL)', fontsize=9)
    ax.legend(fontsize=8, loc='upper right')
    ax.grid(True, alpha=0.3)
    ax.set_ylim(40, 400)
    ax.tick_params(axis='x', rotation=45, labelsize=8)

plt.tight_layout()
plt.show()

print("\n" + "="*80)
print("TIMESERIES COMPARISON")
print("="*80)
print(f"\nTop Row (Incident Patients):")
print(f"   * Red shaded area = incident window (Day 2, 2-5pm)")
print(f"   * Green line = true glucose (ground truth)")
print(f"   * Red dashed line = observed glucose (+40 mg/dL bias during incident)")
print(f"   * Notice the divergence during the incident window")

print(f"\nBottom Row (Non-Incident Patients):")
print(f"   * Grey shaded area = incident window (for reference only)")
print(f"   * Blue line = true glucose")
print(f"   * Cyan dashed line = observed glucose (no bias, overlaps with true)")
print(f"   * No divergence - these patients were not affected")

print(f"\nKey Observation:")
print(f"   Incident patients show clear +40 mg/dL bias during the 3-hour window")
print(f"   Non-incident patients remain unaffected throughout")
print("="*80)

# COMMAND ----------

# MAGIC %md
# MAGIC

# COMMAND ----------

clean7d = spark.table("hls_glucosphere.cgm.pseudo_clean_7d")
display(clean7d)

# COMMAND ----------

incident7d = spark.table("hls_glucosphere.cgm.pseudo_incident_7d")
display(incident7d)

# COMMAND ----------

display(clean7d.filter(F.col('patient_id')=="PSEUDO_0000591"))

# COMMAND ----------

display(incident7d.filter(F.col('patient_id')=="PSEUDO_0000591"))

# COMMAND ----------

# MAGIC %md
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ### Timeseries Data for App Devs 

# COMMAND ----------

# DBTITLE 1,timeseries -- is converted to pandas in plot code above
display(timeseries_data[timeseries_data['patient_id'] == "PSEUDO_0000591"])

# COMMAND ----------

timeseries_data[timeseries_data['patient_id'] == "PSEUDO_0000591"].groupby("incident_type").value_counts().to_frame()

# COMMAND ----------

# DBTITLE 1,timeseries is derived from hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105
spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter(F.col('patient_id') == "PSEUDO_0000591") .groupby("incident_type").count().display()

# COMMAND ----------

import pyspark.sql.functions as F

spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter((F.col('patient_id') == "PSEUDO_0000591") & (F.col('incident_type').cast('string') == "calibration_bias")).display()

# COMMAND ----------

36*5

# COMMAND ----------

spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105').filter((F.col('patient_id') == "PSEUDO_0000591")).agg(F.count(F.when(F.col('incident_type').cast('string') == "calibration_bias", 1)), F.count(F.when(F.col('has_incident') == 1, 1))).display()

# COMMAND ----------

# DBTITLE 1,NOTEs
# Why the Numbers Differ (36 vs 2016)
# The difference exists because these two fields serve different purposes:

# has_incident = 1 (2016 records)
# Patient-level metadata flag indicating this patient experiences an incident somewhere in their 7-day timeline
# Set to 1 for ALL records of this patient (from 2026-01-05 00:00 to 2026-01-11 23:55)
# Used for filtering/grouping patients by incident status
# Think of it as: "Does this patient have an incident event in their data?"
# incident_type = "calibration_bias" (36 records)
# Time-specific field populated only during the actual incident window
# Only set for records from 2026-01-07 14:00:00 to 17:00:00 (3 hours = 36 × 5-minute intervals)
# Indicates the exact timepoints when the device malfunction is occurring
# Think of it as: "Is this specific measurement affected by the incident?"
# Visual Timeline
# Use Case Guidance:

# Use has_incident=1 to identify which patients experienced incidents
# Use incident_type IS NOT NULL to identify the exact affected measurements for analysis or model training

# COMMAND ----------



# COMMAND ----------

ts_df = spark.table('hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105')

# COMMAND ----------

display(ts_df)

# COMMAND ----------



# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # Next Steps & Demo Guide
# MAGIC
# MAGIC ## Primary Demo Table
# MAGIC
# MAGIC ### `hls_glucosphere.cgm.fleet_forecast_incident_v{suffix2use}`
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


