# Databricks notebook source
# DBTITLE 1,Widgets | Configs
dbutils.widgets.text("CATALOG_NAME", "hls_glucosphere", "CATALOG")
# dbutils.widgets.text("SCHEMA_NAME", "cgm", "SCHEMA")      # Continuous Glucose Monitoring
dbutils.widgets.text("SCHEMA_NAME", "cgm_devs", "SCHEMA")   # Continuous Glucose Monitoring --- using a different Schema for devs
 
# dbutils.widgets.text("VOLUME_NAME", "data", "VOLUMES")    # HUPA-UCM dataset volume

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME  = dbutils.widgets.get("SCHEMA_NAME")
# VOLUME_NAME  = dbutils.widgets.get("VOLUME_NAME")

# COMMAND ----------

# MAGIC %md
# MAGIC # HUPA-UCM: Baseline Timeseries Extraction 
# MAGIC
# MAGIC ## Decision
# MAGIC **Option A:** Treat the dataset as an **observed 5‑minute signal** (continuous grid).  
# MAGIC We do **not** attempt to detect/remove interpolation-as-missingness and we do **not** model missingness from this table.
# MAGIC
# MAGIC ## Outputs (Unity Catalog)
# MAGIC 1. **`baseline_timeseries`**: 10–14 day windows for training & pseudo-patient generation (may contain overlapping windows).
# MAGIC 2. **`baseline_windows_metadata`**: window metadata.
# MAGIC 3. **`diabetes_data_cleaned`**: slim full longitudinal table for QC/re-windowing (not “cleaned” via NaN replacement; just standardized flags).
# MAGIC
# MAGIC ## Column policy (per your request)
# MAGIC Keep: `patient_id`, `time`, `glucose`, `calories`, `heart_rate`, `steps`, `basal_rate`, `bolus_volume_delivered`, `carb_input`  
# MAGIC Drop: `glucose_original` (duplicate), `is_interpolated` (always False under Option A), `load_timestamp` (not needed downstream)  
# MAGIC Keep (optional metadata): `is_non_anchor_15min`

# COMMAND ----------

# DBTITLE 1,Load all patient data
import pandas as pd
import numpy as np
from pyspark.sql import functions as F

print("Loading patient data...")
print("=" * 80)

all_df = spark.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data")

all_patients_pd = all_df.toPandas()
all_patients_pd["time"] = pd.to_datetime(all_patients_pd["time"])
all_patients_pd["date"] = all_patients_pd["time"].dt.date

print(f"✓ Loaded {len(all_patients_pd):,} readings from {all_patients_pd['patient_id'].nunique()} patients")
print(f"  Date range: {all_patients_pd['time'].min()} to {all_patients_pd['time'].max()}")
print(f"  Columns: {list(all_patients_pd.columns)}")

# COMMAND ----------

# DBTITLE 1,Verify 5-min continuity + add minimal flags
print("\nVerifying 5-minute grid continuity...")
print("=" * 80)

all_patients_cleaned = all_patients_pd.copy()
all_patients_cleaned = all_patients_cleaned.sort_values(['patient_id', 'time']).reset_index(drop=True)

# Verify time step continuity per patient
tmp = all_patients_cleaned[['patient_id', 'time']].copy().sort_values(['patient_id', 'time'])
tmp['dt_min'] = tmp.groupby('patient_id')['time'].diff().dt.total_seconds() / 60.0

dt_counts = tmp['dt_min'].value_counts(dropna=True).head(10)
pct_5min = float((tmp['dt_min'] == 5).mean())
max_gap = float(tmp['dt_min'].max())

print("Top dt_min counts:")
print(dt_counts.to_string())
print(f"\nPct exactly 5-min steps: {pct_5min:.6f}")
print(f"Max gap (min): {max_gap:.1f}")

# - do not attempt to flag interpolation-as-missingness -- processed data using 5-min grid via an algorithm 
# - keep only optional metadata about 15-min anchors
all_patients_cleaned['is_non_anchor_15min'] = (all_patients_cleaned['time'].dt.minute % 15 != 0)

print(f"\nMetadata flag:")
print(f"  is_non_anchor_15min: {all_patients_cleaned['is_non_anchor_15min'].mean()*100:.1f}% non-anchor points")

# COMMAND ----------

# DBTITLE 1,Calculate daily data presence (quality)
print("\nCalculating daily data presence...")
print("=" * 80)

EXPECTED_PER_DAY = 288  # 5-min grid

daily_quality = all_patients_cleaned.groupby(['patient_id', 'date']).agg(
    total_readings=('time', 'count'),
    glucose_non_null=('glucose', lambda x: x.notna().sum()),
    day_start=('time', 'min'),
    day_end=('time', 'max')
).reset_index()

daily_quality['date'] = pd.to_datetime(daily_quality['date'])
daily_quality['presence_pct'] = 100 * daily_quality['total_readings'] / EXPECTED_PER_DAY
daily_quality['glucose_present_pct'] = 100 * daily_quality['glucose_non_null'] / daily_quality['total_readings']

print(f"✓ Calculated daily presence metrics for {len(daily_quality)} patient-days")
print(f"\nPresence distribution (expected 288 readings/day):")
print(f"  Days with >=99% presence: {(daily_quality['presence_pct'] >= 99).sum()}")
print(f"  Days with 95-99% presence: {((daily_quality['presence_pct'] >= 95) & (daily_quality['presence_pct'] < 99)).sum()}")
print(f"  Days with <95% presence: {(daily_quality['presence_pct'] < 95).sum()}")

display(daily_quality.head(20))

# COMMAND ----------

# DBTITLE 1,true “minimal possible” window length automatically
# def longest_consecutive_streak(dates: pd.Series) -> int:
#     d = pd.to_datetime(sorted(dates.unique()))
#     if len(d) == 0:
#         return 0
#     streak = best = 1
#     for i in range(1, len(d)):
#         if (d[i] - d[i-1]).days <= 1:
#             streak += 1
#         else:
#             best = max(best, streak)
#             streak = 1
#     return max(best, streak)

# streaks = daily_quality.groupby('patient_id')['date'].apply(longest_consecutive_streak).sort_values()
# display(streaks.reset_index(name="longest_consecutive_days"))
# print("Minimum streak across patients:", int(streaks.min()))

# COMMAND ----------

# DBTITLE 1,Find 7-14 day windows with sufficient daily presence
print("\nFinding 7–14 day baseline windows with sufficient daily presence...")
print("=" * 80)

def find_windows_by_presence_threshold(min_presence_pct, window_days_range=[7, 8, 9, 10, 11, 12, 13, 14]):
    """
    Find continuous windows where all days have at least min_presence_pct presence.
    Presence is based on 288 expected records/day for 5-min grid.
    """
    windows = []
    for pid in daily_quality['patient_id'].unique():
        patient_daily = daily_quality[daily_quality['patient_id'] == pid].sort_values('date').copy()

        for window_days in window_days_range:
            for i in range(len(patient_daily) - window_days + 1):
                window = patient_daily.iloc[i:i+window_days]

                # Continuous dates (no gaps >1 day)
                date_diffs = window['date'].diff().dt.days
                is_continuous = (date_diffs[1:] <= 1).all()

                # All days meet threshold
                all_days_sufficient = (window['presence_pct'] >= min_presence_pct).all()

                if is_continuous and all_days_sufficient:
                    avg_presence = window['presence_pct'].mean()
                    min_presence = window['presence_pct'].min()

                    windows.append({
                        'patient_id': pid,
                        'window_days': int(window_days),
                        'start_date': window['day_start'].min(),
                        'end_date': window['day_end'].max(),
                        'avg_presence_pct': float(avg_presence),
                        'min_daily_presence_pct': float(min_presence),
                        'total_readings': int(window['total_readings'].sum()),
                        'quality_score': float(avg_presence)
                    })
    return pd.DataFrame(windows)

tier1_windows = find_windows_by_presence_threshold(min_presence_pct=99)  # near complete
tier2_windows = find_windows_by_presence_threshold(min_presence_pct=95)  # good
tier3_windows = find_windows_by_presence_threshold(min_presence_pct=90)  # acceptable

print(f"Tier 1 (>=99% presence): {len(tier1_windows)} windows from {tier1_windows['patient_id'].nunique() if len(tier1_windows)>0 else 0} patients")
print(f"Tier 2 (>=95% presence): {len(tier2_windows)} windows from {tier2_windows['patient_id'].nunique() if len(tier2_windows)>0 else 0} patients")
print(f"Tier 3 (>=90% presence): {len(tier3_windows)} windows from {tier3_windows['patient_id'].nunique() if len(tier3_windows)>0 else 0} patients")

# COMMAND ----------

# DBTITLE 1,Display tiered baseline windows
print("\nTiered Baseline Windows Analysis (Presence-based):")
print("=" * 80)

if len(tier1_windows) > 0:
    print(f"\nTIER 1: Excellent (>=99% daily presence)")
    print("-" * 80)
    print(f"  Total windows: {len(tier1_windows)}")
    print(f"  Unique patients: {tier1_windows['patient_id'].nunique()}")
    print(f"  Avg presence: {tier1_windows['avg_presence_pct'].mean():.2f}%")
    print(f"  Window length distribution: {tier1_windows['window_days'].value_counts().sort_index().to_dict()}")
    display(tier1_windows.sort_values('quality_score', ascending=False).head(10))
else:
    print("\nTIER 1: No windows found")

if len(tier2_windows) > 0:
    tier2_only = tier2_windows[tier2_windows['avg_presence_pct'] < 99]
    print(f"\nTIER 2: Good (95–99% daily presence)")
    print("-" * 80)
    print(f"  Total windows: {len(tier2_only)}")
    print(f"  Unique patients: {tier2_only['patient_id'].nunique() if len(tier2_only)>0 else 0}")
    if len(tier2_only) > 0:
        print(f"  Avg presence: {tier2_only['avg_presence_pct'].mean():.2f}%")
        print(f"  Window length distribution: {tier2_only['window_days'].value_counts().sort_index().to_dict()}")
else:
    print("\nTIER 2: No windows found")

if len(tier3_windows) > 0:
    tier3_only = tier3_windows[tier3_windows['avg_presence_pct'] < 95]
    print(f"\nTIER 3: Acceptable (90–95% daily presence)")
    print("-" * 80)
    print(f"  Total windows: {len(tier3_only)}")
    print(f"  Unique patients: {tier3_only['patient_id'].nunique() if len(tier3_only)>0 else 0}")
    if len(tier3_only) > 0:
        print(f"  Avg presence: {tier3_only['avg_presence_pct'].mean():.2f}%")
else:
    print("\nTIER 3: No windows found")

print("\n" + "=" * 80)

# COMMAND ----------

# DBTITLE 1,Extract baseline dataset
print("\nExtracting Baseline Window Data ...")
print("=" * 80)

# Recommended baseline = Tier 2 (>=95% presence); includes tier1 windows naturally
recommended_windows = tier2_windows.copy()

print(f"Using windows with >=95% daily presence")
print(f"  Total windows: {len(recommended_windows)}")
print(f"  Unique patients: {recommended_windows['patient_id'].nunique() if len(recommended_windows)>0 else 0}")

baseline_timeseries = []

for _, window in recommended_windows.iterrows():
    window_data = all_patients_cleaned[
        (all_patients_cleaned['patient_id'] == window['patient_id']) &
        (all_patients_cleaned['time'] >= window['start_date']) &
        (all_patients_cleaned['time'] <= window['end_date'])
    ].copy()

    window_data['window_id'] = f"{window['patient_id']}_{window['start_date'].strftime('%Y%m%d')}"
    window_data['window_days'] = window['window_days']
    window_data['window_quality_score'] = window['quality_score']
    baseline_timeseries.append(window_data)

if len(baseline_timeseries) > 0:
    baseline_dataset = pd.concat(baseline_timeseries, ignore_index=True)

    print(f"\n✓ Extracted baseline dataset:")
    print(f"  Total readings: {len(baseline_dataset):,}")
    print(f"  Glucose non-null: {baseline_dataset['glucose'].notna().sum():,} ({baseline_dataset['glucose'].notna().mean()*100:.3f}%)")
    print(f"  Unique windows: {baseline_dataset['window_id'].nunique()}")
    print(f"  Unique patients: {baseline_dataset['patient_id'].nunique()}")

    print(f"\nSample (first 20):")
    display(
        baseline_dataset.head(20)[
            ['window_id','time','glucose','calories','heart_rate','steps',
             'basal_rate','bolus_volume_delivered','carb_input','patient_id','is_non_anchor_15min']
        ]
    )
else:
    print("\n⚠️ No baseline windows found at >=95% presence")
    baseline_dataset = None

# COMMAND ----------

# DBTITLE 1,Final summary
print("\n" + "=" * 80)
print("FINAL SUMMARY (Option A: observed 5-min signal)")
print("=" * 80)

print(f"\n1. DATA STATUS:")
print(f"   ✓ Continuous 5-min grid confirmed (max gap = {max_gap:.1f} min)")
print(f"   ✓ No interpolation-as-missingness removal performed")
print(f"   ✓ Missingness modeling removed (not needed under Option A)")

if baseline_dataset is not None:
    print(f"\n2. BASELINE DATASET:")
    print(f"   ✓ Windows (>=95% presence): {len(recommended_windows)}")
    print(f"   ✓ Patients: {recommended_windows['patient_id'].nunique()}")
    print(f"   ✓ Window lengths: {sorted(recommended_windows['window_days'].unique().tolist())}")
    print(f"   ✓ Total rows: {len(baseline_dataset):,}")
else:
    print(f"\n2. BASELINE DATASET:")
    print(f"   ⚠️ None extracted; lower threshold (e.g., 90%) if needed")

print("\n" + "=" * 80)
print("✓ Ready to save to Unity Catalog")
print("=" * 80)

# COMMAND ----------

# can we visualize baseline and clean data like before for e.g. Visualize baseline dataset characteristics + Visualize tier1 windows metadata + Visualize sample timeseries from baseline dataset + Calculate 24-hour cycle patterns + Visualize 24-hour glucose cycle + Visualize 24-hour patterns for insulin, carbs, and activity + Calculate weekly cycle patterns + Visualize weekly glucose cycle + Visualize weekly behavioral patterns + Combined 24-hour heatmap across all measures before saving to UC?

# COMMAND ----------

# MAGIC %md
# MAGIC ---
# MAGIC
# MAGIC # DATA QUALITY VISUALIZATIONS
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Comprehensive Analysis Before Saving to Unity Catalog
# MAGIC
# MAGIC Visualize baseline dataset characteristics, temporal patterns, and data quality metrics.

# COMMAND ----------

# DBTITLE 1,Visualize Baseline Dataset Characteristics
import matplotlib.pyplot as plt
import numpy as np

if baseline_dataset is not None and len(baseline_dataset) > 0:
    print("Baseline Dataset Characteristics:")
    print("=" * 80)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Baseline Dataset Overview', fontsize=14, fontweight='bold')
    
    # 1. Glucose distribution
    ax1 = axes[0, 0]
    glucose_vals = baseline_dataset['glucose'].dropna()
    ax1.hist(glucose_vals, bins=50, color='blue', alpha=0.7, edgecolor='black')
    ax1.axvline(glucose_vals.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {glucose_vals.mean():.1f}')
    ax1.axvline(glucose_vals.median(), color='orange', linestyle='--', linewidth=2, label=f'Median: {glucose_vals.median():.1f}')
    ax1.axvline(70, color='red', linestyle=':', alpha=0.5, label='Hypo threshold')
    ax1.axvline(180, color='orange', linestyle=':', alpha=0.5, label='Hyper threshold')
    ax1.set_xlabel('Glucose (mg/dL)', fontsize=10)
    ax1.set_ylabel('Frequency', fontsize=10)
    ax1.set_title('Glucose Distribution', fontsize=11)
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. Records per patient
    ax2 = axes[0, 1]
    records_per_patient = baseline_dataset.groupby('patient_id').size().sort_values(ascending=False)
    ax2.bar(range(len(records_per_patient)), records_per_patient.values, color='green', alpha=0.7)
    ax2.set_xlabel('Patient (sorted by records)', fontsize=10)
    ax2.set_ylabel('Number of Records', fontsize=10)
    ax2.set_title(f'Records per Patient (n={len(records_per_patient)})', fontsize=11)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Windows per patient
    ax3 = axes[0, 2]
    windows_per_patient = baseline_dataset.groupby('patient_id')['window_id'].nunique().sort_values(ascending=False)
    ax3.bar(range(len(windows_per_patient)), windows_per_patient.values, color='purple', alpha=0.7)
    ax3.set_xlabel('Patient (sorted by windows)', fontsize=10)
    ax3.set_ylabel('Number of Windows', fontsize=10)
    ax3.set_title(f'Windows per Patient (n={len(windows_per_patient)})', fontsize=11)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Window length distribution
    ax4 = axes[1, 0]
    window_lengths = baseline_dataset.groupby('window_id')['window_days'].first()
    ax4.hist(window_lengths, bins=range(7, 16), color='teal', alpha=0.7, edgecolor='black', align='left')
    ax4.set_xlabel('Window Length (days)', fontsize=10)
    ax4.set_ylabel('Number of Windows', fontsize=10)
    ax4.set_title('Window Length Distribution', fontsize=11)
    ax4.set_xticks(range(7, 15))
    ax4.grid(True, alpha=0.3, axis='y')
    
    # 5. Data quality score distribution
    ax5 = axes[1, 1]
    quality_scores = baseline_dataset.groupby('window_id')['window_quality_score'].first()
    ax5.hist(quality_scores, bins=30, color='orange', alpha=0.7, edgecolor='black')
    ax5.axvline(quality_scores.mean(), color='red', linestyle='--', linewidth=2, label=f'Mean: {quality_scores.mean():.1f}%')
    ax5.set_xlabel('Quality Score (%)', fontsize=10)
    ax5.set_ylabel('Number of Windows', fontsize=10)
    ax5.set_title('Window Quality Distribution', fontsize=11)
    ax5.legend(fontsize=8)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Summary statistics
    ax6 = axes[1, 2]
    ax6.axis('off')
    
    hypo_pct = (glucose_vals < 70).mean() * 100
    in_range_pct = ((glucose_vals >= 70) & (glucose_vals <= 180)).mean() * 100
    hyper_pct = (glucose_vals > 180).mean() * 100
    
    summary_text = f"""BASELINE DATASET SUMMARY
{'='*35}

Total Records: {len(baseline_dataset):,}
Glucose Non-Null: {len(glucose_vals):,}
Unique Patients: {baseline_dataset['patient_id'].nunique()}
Unique Windows: {baseline_dataset['window_id'].nunique()}

Glucose Statistics:
  Mean: {glucose_vals.mean():.1f} mg/dL
  Median: {glucose_vals.median():.1f} mg/dL
  Std: {glucose_vals.std():.1f} mg/dL
  Range: {glucose_vals.min():.0f}-{glucose_vals.max():.0f}

Clinical Ranges:
  Hypo (<70): {hypo_pct:.1f}%
  In Range (70-180): {in_range_pct:.1f}%
  Hyper (>180): {hyper_pct:.1f}%

Window Stats:
  Avg windows/patient: {windows_per_patient.mean():.1f}
  Avg quality score: {quality_scores.mean():.1f}%
"""
    
    ax6.text(0.05, 0.5, summary_text, fontsize=9, family='monospace',
             verticalalignment='center', bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ Baseline dataset characteristics visualization complete")
else:
    print("⚠️ baseline_dataset not available for visualization")

# COMMAND ----------

# DBTITLE 1,Visualize Sample Timeseries from Baseline
import matplotlib.pyplot as plt
import numpy as np

if baseline_dataset is not None and len(baseline_dataset) > 0:
    print("Sample Timeseries from Baseline Dataset:")
    print("=" * 80)
    
    # Select 4 random patients with good data
    patients_with_data = baseline_dataset.groupby('patient_id')['glucose'].count().sort_values(ascending=False).head(4).index
    
    fig, axes = plt.subplots(2, 2, figsize=(18, 10))
    fig.suptitle('Sample Patient Timeseries (Baseline Dataset)', fontsize=14, fontweight='bold')
    
    for idx, patient_id in enumerate(patients_with_data):
        ax = axes[idx // 2, idx % 2]
        
        # Get patient data (first window)
        patient_data = baseline_dataset[baseline_dataset['patient_id'] == patient_id].sort_values('time').head(2000)
        
        # Plot glucose
        ax.plot(patient_data['time'], patient_data['glucose'], 'o-', markersize=2, linewidth=0.5, color='blue', alpha=0.7)
        ax.axhline(70, color='red', linestyle='--', alpha=0.5, linewidth=1, label='Hypo (70)')
        ax.axhline(180, color='orange', linestyle='--', alpha=0.5, linewidth=1, label='Hyper (180)')
        ax.fill_between(patient_data['time'], 70, 180, alpha=0.1, color='green', label='Target range')
        
        ax.set_xlabel('Time', fontsize=10)
        ax.set_ylabel('Glucose (mg/dL)', fontsize=10)
        ax.set_title(f'{patient_id} (n={len(patient_data):,} records)', fontsize=11)
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(40, 400)
        
        # Rotate x-axis labels
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ Sample timeseries visualization complete")
else:
    print("⚠️ baseline_dataset not available for visualization")

# COMMAND ----------

# DBTITLE 1,Calculate 24-Hour Cycle Patterns
import numpy as np
import pandas as pd

if baseline_dataset is not None and len(baseline_dataset) > 0:
    print("Calculating 24-Hour Cycle Patterns:")
    print("=" * 80)
    
    # Extract hour from time
    baseline_with_hour = baseline_dataset.copy()
    baseline_with_hour['hour'] = pd.to_datetime(baseline_with_hour['time']).dt.hour
    
    # Calculate hourly statistics for each measure
    hourly_glucose = baseline_with_hour.groupby('hour')['glucose'].agg(['mean', 'std', 'count']).reset_index()
    hourly_basal = baseline_with_hour.groupby('hour')['basal_rate'].agg(['mean', 'std', 'count']).reset_index()
    hourly_bolus = baseline_with_hour.groupby('hour')['bolus_volume_delivered'].agg(['sum', 'count']).reset_index()
    hourly_carbs = baseline_with_hour.groupby('hour')['carb_input'].agg(['sum', 'count']).reset_index()
    hourly_hr = baseline_with_hour.groupby('hour')['heart_rate'].agg(['mean', 'std', 'count']).reset_index()
    hourly_steps = baseline_with_hour.groupby('hour')['steps'].agg(['sum', 'count']).reset_index()
    hourly_calories = baseline_with_hour.groupby('hour')['calories'].agg(['sum', 'count']).reset_index()
    
    print(f"\n✓ Calculated 24-hour patterns for all measures")
    print(f"  Hours analyzed: 0-23")
    print(f"  Total records: {len(baseline_with_hour):,}")
    
    # Store for visualization
    hourly_patterns = {
        'glucose': hourly_glucose,
        'basal': hourly_basal,
        'bolus': hourly_bolus,
        'carbs': hourly_carbs,
        'heart_rate': hourly_hr,
        'steps': hourly_steps,
        'calories': hourly_calories
    }
    
    print(f"\nGlucose 24-hour pattern:")
    print(f"  Peak hour: {hourly_glucose.loc[hourly_glucose['mean'].idxmax(), 'hour']:.0f}:00 ({hourly_glucose['mean'].max():.1f} mg/dL)")
    print(f"  Lowest hour: {hourly_glucose.loc[hourly_glucose['mean'].idxmin(), 'hour']:.0f}:00 ({hourly_glucose['mean'].min():.1f} mg/dL)")
    print(f"  Daily variation: {hourly_glucose['mean'].max() - hourly_glucose['mean'].min():.1f} mg/dL")
else:
    print("⚠️ baseline_dataset not available for 24-hour analysis")
    hourly_patterns = None

# COMMAND ----------

# DBTITLE 1,Visualize 24-Hour Glucose Cycle
import matplotlib.pyplot as plt
import numpy as np

if hourly_patterns is not None:
    print("Visualizing 24-Hour Glucose Cycle:")
    print("=" * 80)
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 5))
    fig.suptitle('24-Hour Glucose Patterns', fontsize=14, fontweight='bold')
    
    hourly_glucose = hourly_patterns['glucose']
    
    # 1. Mean glucose by hour with error bars
    ax1 = axes[0]
    hours = hourly_glucose['hour']
    means = hourly_glucose['mean']
    stds = hourly_glucose['std']
    
    ax1.plot(hours, means, 'o-', linewidth=2, markersize=8, color='blue', label='Mean glucose')
    ax1.fill_between(hours, means - stds, means + stds, alpha=0.2, color='blue', label='±1 SD')
    ax1.axhline(70, color='red', linestyle='--', alpha=0.5, linewidth=1, label='Hypo (70)')
    ax1.axhline(180, color='orange', linestyle='--', alpha=0.5, linewidth=1, label='Hyper (180)')
    ax1.fill_between(hours, 70, 180, alpha=0.1, color='green')
    
    ax1.set_xlabel('Hour of Day', fontsize=11)
    ax1.set_ylabel('Glucose (mg/dL)', fontsize=11)
    ax1.set_title('Mean Glucose by Hour (with SD)', fontsize=12)
    ax1.set_xticks(range(0, 24, 2))
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(60, 200)
    
    # 2. Sample count by hour
    ax2 = axes[1]
    counts = hourly_glucose['count']
    ax2.bar(hours, counts, color='teal', alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Hour of Day', fontsize=11)
    ax2.set_ylabel('Number of Samples', fontsize=11)
    ax2.set_title('Data Coverage by Hour', fontsize=12)
    ax2.set_xticks(range(0, 24, 2))
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ 24-hour glucose cycle visualization complete")
else:
    print("⚠️ hourly_patterns not available")

# COMMAND ----------

# DBTITLE 1,Visualize 24-Hour Patterns for Insulin, Carbs, and Activity
import matplotlib.pyplot as plt
import numpy as np

if hourly_patterns is not None:
    print("Visualizing 24-Hour Patterns for Insulin, Carbs, and Activity:")
    print("=" * 80)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('24-Hour Patterns: Insulin, Carbs, and Activity', fontsize=14, fontweight='bold')
    
    # 1. Basal rate
    ax1 = axes[0, 0]
    hourly_basal = hourly_patterns['basal']
    ax1.plot(hourly_basal['hour'], hourly_basal['mean'], 'o-', linewidth=2, markersize=6, color='purple')
    ax1.fill_between(hourly_basal['hour'], 
                     hourly_basal['mean'] - hourly_basal['std'], 
                     hourly_basal['mean'] + hourly_basal['std'], 
                     alpha=0.2, color='purple')
    ax1.set_xlabel('Hour of Day', fontsize=10)
    ax1.set_ylabel('Basal Rate (U/hr)', fontsize=10)
    ax1.set_title('Basal Insulin by Hour', fontsize=11)
    ax1.set_xticks(range(0, 24, 2))
    ax1.grid(True, alpha=0.3)
    
    # 2. Bolus volume (total per hour)
    ax2 = axes[0, 1]
    hourly_bolus = hourly_patterns['bolus']
    ax2.bar(hourly_bolus['hour'], hourly_bolus['sum'], color='red', alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Hour of Day', fontsize=10)
    ax2.set_ylabel('Total Bolus (U)', fontsize=10)
    ax2.set_title('Bolus Insulin by Hour', fontsize=11)
    ax2.set_xticks(range(0, 24, 2))
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Carb input (total per hour)
    ax3 = axes[0, 2]
    hourly_carbs = hourly_patterns['carbs']
    ax3.bar(hourly_carbs['hour'], hourly_carbs['sum'], color='orange', alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Hour of Day', fontsize=10)
    ax3.set_ylabel('Total Carbs (g)', fontsize=10)
    ax3.set_title('Carbohydrate Intake by Hour', fontsize=11)
    ax3.set_xticks(range(0, 24, 2))
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Heart rate
    ax4 = axes[1, 0]
    hourly_hr = hourly_patterns['heart_rate']
    ax4.plot(hourly_hr['hour'], hourly_hr['mean'], 'o-', linewidth=2, markersize=6, color='red')
    ax4.fill_between(hourly_hr['hour'], 
                     hourly_hr['mean'] - hourly_hr['std'], 
                     hourly_hr['mean'] + hourly_hr['std'], 
                     alpha=0.2, color='red')
    ax4.set_xlabel('Hour of Day', fontsize=10)
    ax4.set_ylabel('Heart Rate (bpm)', fontsize=10)
    ax4.set_title('Heart Rate by Hour', fontsize=11)
    ax4.set_xticks(range(0, 24, 2))
    ax4.grid(True, alpha=0.3)
    
    # 5. Steps (total per hour)
    ax5 = axes[1, 1]
    hourly_steps = hourly_patterns['steps']
    ax5.bar(hourly_steps['hour'], hourly_steps['sum'], color='green', alpha=0.7, edgecolor='black')
    ax5.set_xlabel('Hour of Day', fontsize=10)
    ax5.set_ylabel('Total Steps', fontsize=10)
    ax5.set_title('Physical Activity by Hour', fontsize=11)
    ax5.set_xticks(range(0, 24, 2))
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Calories (total per hour)
    ax6 = axes[1, 2]
    hourly_calories = hourly_patterns['calories']
    ax6.bar(hourly_calories['hour'], hourly_calories['sum'], color='brown', alpha=0.7, edgecolor='black')
    ax6.set_xlabel('Hour of Day', fontsize=10)
    ax6.set_ylabel('Total Calories', fontsize=10)
    ax6.set_title('Calorie Expenditure by Hour', fontsize=11)
    ax6.set_xticks(range(0, 24, 2))
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ 24-hour insulin, carbs, and activity patterns visualization complete")
else:
    print("⚠️ hourly_patterns not available")

# COMMAND ----------

# DBTITLE 1,Calculate Weekly Cycle Patterns
import numpy as np
import pandas as pd

if baseline_dataset is not None and len(baseline_dataset) > 0:
    print("Calculating Weekly Cycle Patterns:")
    print("=" * 80)
    
    # Extract day of week from time
    baseline_with_dow = baseline_dataset.copy()
    baseline_with_dow['day_of_week'] = pd.to_datetime(baseline_with_dow['time']).dt.dayofweek
    baseline_with_dow['day_name'] = pd.to_datetime(baseline_with_dow['time']).dt.day_name()
    
    # Calculate daily statistics
    daily_glucose = baseline_with_dow.groupby('day_of_week')['glucose'].agg(['mean', 'std', 'count']).reset_index()
    daily_basal = baseline_with_dow.groupby('day_of_week')['basal_rate'].agg(['mean', 'std']).reset_index()
    daily_bolus = baseline_with_dow.groupby('day_of_week')['bolus_volume_delivered'].agg(['sum', 'mean']).reset_index()
    daily_carbs = baseline_with_dow.groupby('day_of_week')['carb_input'].agg(['sum', 'mean']).reset_index()
    daily_steps = baseline_with_dow.groupby('day_of_week')['steps'].agg(['sum', 'mean']).reset_index()
    
    # Add day names
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    daily_glucose['day_name'] = daily_glucose['day_of_week'].map(lambda x: day_names[x])
    
    print(f"\n✓ Calculated weekly patterns for all measures")
    print(f"  Days analyzed: Monday-Sunday")
    print(f"  Total records: {len(baseline_with_dow):,}")
    
    # Store for visualization
    weekly_patterns = {
        'glucose': daily_glucose,
        'basal': daily_basal,
        'bolus': daily_bolus,
        'carbs': daily_carbs,
        'steps': daily_steps,
        'day_names': day_names
    }
    
    print(f"\nGlucose weekly pattern:")
    print(f"  Highest day: {daily_glucose.loc[daily_glucose['mean'].idxmax(), 'day_name']} ({daily_glucose['mean'].max():.1f} mg/dL)")
    print(f"  Lowest day: {daily_glucose.loc[daily_glucose['mean'].idxmin(), 'day_name']} ({daily_glucose['mean'].min():.1f} mg/dL)")
    print(f"  Weekly variation: {daily_glucose['mean'].max() - daily_glucose['mean'].min():.1f} mg/dL")
else:
    print("⚠️ baseline_dataset not available for weekly analysis")
    weekly_patterns = None

# COMMAND ----------

# DBTITLE 1,Visualize Weekly Patterns
import matplotlib.pyplot as plt
import numpy as np

if weekly_patterns is not None:
    print("Visualizing Weekly Patterns:")
    print("=" * 80)
    
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle('Weekly Patterns: Day-of-Week Analysis', fontsize=14, fontweight='bold')
    
    day_names = weekly_patterns['day_names']
    
    # 1. Glucose by day of week
    ax1 = axes[0, 0]
    daily_glucose = weekly_patterns['glucose']
    ax1.bar(daily_glucose['day_of_week'], daily_glucose['mean'], color='blue', alpha=0.7, edgecolor='black')
    ax1.errorbar(daily_glucose['day_of_week'], daily_glucose['mean'], yerr=daily_glucose['std'], 
                 fmt='none', ecolor='black', capsize=5, alpha=0.5)
    ax1.axhline(daily_glucose['mean'].mean(), color='red', linestyle='--', linewidth=2, label='Weekly avg')
    ax1.set_xlabel('Day of Week', fontsize=10)
    ax1.set_ylabel('Mean Glucose (mg/dL)', fontsize=10)
    ax1.set_title('Glucose by Day of Week', fontsize=11)
    ax1.set_xticks(range(7))
    ax1.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], fontsize=9)
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # 2. Basal rate by day
    ax2 = axes[0, 1]
    daily_basal = weekly_patterns['basal']
    ax2.bar(daily_basal['day_of_week'], daily_basal['mean'], color='purple', alpha=0.7, edgecolor='black')
    ax2.set_xlabel('Day of Week', fontsize=10)
    ax2.set_ylabel('Mean Basal Rate (U/hr)', fontsize=10)
    ax2.set_title('Basal Insulin by Day', fontsize=11)
    ax2.set_xticks(range(7))
    ax2.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], fontsize=9)
    ax2.grid(True, alpha=0.3, axis='y')
    
    # 3. Total bolus by day
    ax3 = axes[0, 2]
    daily_bolus = weekly_patterns['bolus']
    ax3.bar(daily_bolus['day_of_week'], daily_bolus['sum'], color='red', alpha=0.7, edgecolor='black')
    ax3.set_xlabel('Day of Week', fontsize=10)
    ax3.set_ylabel('Total Bolus (U)', fontsize=10)
    ax3.set_title('Bolus Insulin by Day', fontsize=11)
    ax3.set_xticks(range(7))
    ax3.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], fontsize=9)
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Total carbs by day
    ax4 = axes[1, 0]
    daily_carbs = weekly_patterns['carbs']
    ax4.bar(daily_carbs['day_of_week'], daily_carbs['sum'], color='orange', alpha=0.7, edgecolor='black')
    ax4.set_xlabel('Day of Week', fontsize=10)
    ax4.set_ylabel('Total Carbs (g)', fontsize=10)
    ax4.set_title('Carbohydrate Intake by Day', fontsize=11)
    ax4.set_xticks(range(7))
    ax4.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], fontsize=9)
    ax4.grid(True, alpha=0.3, axis='y')
    
    # 5. Total steps by day
    ax5 = axes[1, 1]
    daily_steps = weekly_patterns['steps']
    ax5.bar(daily_steps['day_of_week'], daily_steps['sum'], color='green', alpha=0.7, edgecolor='black')
    ax5.set_xlabel('Day of Week', fontsize=10)
    ax5.set_ylabel('Total Steps', fontsize=10)
    ax5.set_title('Physical Activity by Day', fontsize=11)
    ax5.set_xticks(range(7))
    ax5.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'], fontsize=9)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Weekend vs Weekday comparison
    ax6 = axes[1, 2]
    baseline_with_dow['is_weekend'] = baseline_with_dow['day_of_week'].isin([5, 6])
    weekend_glucose = baseline_with_dow[baseline_with_dow['is_weekend']]['glucose'].dropna()
    weekday_glucose = baseline_with_dow[~baseline_with_dow['is_weekend']]['glucose'].dropna()
    
    ax6.hist([weekday_glucose, weekend_glucose], bins=40, label=['Weekday', 'Weekend'], 
             color=['blue', 'orange'], alpha=0.6, edgecolor='black')
    ax6.axvline(weekday_glucose.mean(), color='blue', linestyle='--', linewidth=2, label=f'Weekday: {weekday_glucose.mean():.1f}')
    ax6.axvline(weekend_glucose.mean(), color='orange', linestyle='--', linewidth=2, label=f'Weekend: {weekend_glucose.mean():.1f}')
    ax6.set_xlabel('Glucose (mg/dL)', fontsize=10)
    ax6.set_ylabel('Frequency', fontsize=10)
    ax6.set_title('Weekday vs Weekend Glucose', fontsize=11)
    ax6.legend(fontsize=9)
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ Weekly patterns visualization complete")
    print(f"\nKey findings:")
    print(f"  Weekday glucose: {weekday_glucose.mean():.1f} ± {weekday_glucose.std():.1f} mg/dL")
    print(f"  Weekend glucose: {weekend_glucose.mean():.1f} ± {weekend_glucose.std():.1f} mg/dL")
    print(f"  Difference: {abs(weekend_glucose.mean() - weekday_glucose.mean()):.1f} mg/dL")
else:
    print("⚠️ weekly_patterns not available")

# COMMAND ----------

# DBTITLE 1,Combined 24-Hour Heatmap Across All Measures
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if hourly_patterns is not None:
    print("Creating Combined 24-Hour Heatmap:")
    print("=" * 80)
    
    # Prepare data for heatmap (normalize each measure to 0-1 scale)
    measures = ['glucose', 'basal', 'bolus', 'carbs', 'heart_rate', 'steps', 'calories']
    measure_labels = ['Glucose\n(mg/dL)', 'Basal Rate\n(U/hr)', 'Bolus\n(U)', 'Carbs\n(g)', 
                      'Heart Rate\n(bpm)', 'Steps', 'Calories']
    
    heatmap_data = np.zeros((len(measures), 24))
    
    for i, measure in enumerate(measures):
        if measure == 'glucose':
            values = hourly_patterns['glucose']['mean'].values
        elif measure == 'basal':
            values = hourly_patterns['basal']['mean'].values
        elif measure == 'bolus':
            values = hourly_patterns['bolus']['sum'].values
        elif measure == 'carbs':
            values = hourly_patterns['carbs']['sum'].values
        elif measure == 'heart_rate':
            values = hourly_patterns['heart_rate']['mean'].values
        elif measure == 'steps':
            values = hourly_patterns['steps']['sum'].values
        elif measure == 'calories':
            values = hourly_patterns['calories']['sum'].values
        
        # Normalize to 0-1 scale
        if values.max() > values.min():
            normalized = (values - values.min()) / (values.max() - values.min())
        else:
            normalized = np.zeros_like(values)
        
        heatmap_data[i, :] = normalized
    
    # Create heatmap
    fig, ax = plt.subplots(figsize=(16, 8))
    
    im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto', interpolation='nearest')
    
    # Set ticks and labels
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(24)], fontsize=9)
    ax.set_yticks(range(len(measures)))
    ax.set_yticklabels(measure_labels, fontsize=10)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Normalized Intensity (0=min, 1=max)', fontsize=10)
    
    # Add values as text
    for i in range(len(measures)):
        for j in range(24):
            text = ax.text(j, i, f'{heatmap_data[i, j]:.2f}',
                          ha="center", va="center", color="black" if heatmap_data[i, j] < 0.5 else "white",
                          fontsize=7)
    
    ax.set_xlabel('Hour of Day', fontsize=11)
    ax.set_title('Combined 24-Hour Heatmap: All Measures (Normalized)', fontsize=13, fontweight='bold', pad=20)
    
    plt.tight_layout()
    plt.show()
    
    print(f"\n✓ Combined 24-hour heatmap visualization complete")
    
    # Print interpretation
    print(f"\nInterpretation:")
    print(f"  Red/Orange: High activity/values for that measure at that hour")
    print(f"  Yellow/White: Low activity/values for that measure at that hour")
    print(f"  Each row is independently normalized (0=min, 1=max for that measure)")
    
    print(f"\nKey patterns:")
    # Find peak hours for each measure
    for i, (measure, label) in enumerate(zip(measures, measure_labels)):
        peak_hour = np.argmax(heatmap_data[i, :])
        print(f"  {label.replace(chr(10), ' ')}: Peak at {peak_hour:02d}:00")
else:
    print("⚠️ hourly_patterns not available")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Save Generated Datasets to Unity Catalog

# COMMAND ----------

# DBTITLE 1,Save baseline_timeseries to UC
if baseline_dataset is not None:
    print("Saving baseline_timeseries to Unity Catalog...")
    print("=" * 80)

    # Keep only likely-downstream columns
    cols_baseline = [
        'window_id', 'window_days', 'window_quality_score',
        'patient_id', 'time',
        'glucose',
        'calories', 'heart_rate', 'steps',
        'basal_rate', 'bolus_volume_delivered', 'carb_input'
    ]
    # optional metadata
    if 'is_non_anchor_15min' in baseline_dataset.columns:
        cols_baseline.append('is_non_anchor_15min')

    cols_baseline = [c for c in cols_baseline if c in baseline_dataset.columns]
    baseline_for_save = baseline_dataset[cols_baseline].copy()

    # Convert datetime columns to strings for Spark parquet write
    datetime_cols = baseline_for_save.select_dtypes(include=['datetime64']).columns
    for col in datetime_cols:
        baseline_for_save[col] = baseline_for_save[col].astype(str)

    temp_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{VOLUME_NAME}/temp/baseline_timeseries.parquet"
    import os
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    baseline_for_save.to_parquet(temp_path, index=False, engine='pyarrow')
    print(f"  ✓ Written {len(baseline_for_save):,} rows to {temp_path}")

    baseline_spark = spark.read.parquet(temp_path)
    for col in datetime_cols:
        baseline_spark = baseline_spark.withColumn(col, F.to_timestamp(F.col(col)))

    table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries"
    baseline_spark.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_name)
    print(f"  ✓ Saved to {table_name}")
else:
    print("⚠️ baseline_dataset is None - cannot save baseline_timeseries")

# COMMAND ----------

# DBTITLE 1,Save baseline_windows_metadata to UC
if len(tier2_windows) > 0:
    print("\nSaving baseline_windows_metadata to Unity Catalog...")
    print("=" * 80)

    # Save tier2 as recommended windows metadata
    windows_cols = [
        'patient_id','window_days','start_date','end_date',
        'avg_presence_pct','min_daily_presence_pct','total_readings','quality_score'
    ]
    windows_cols = [c for c in windows_cols if c in tier2_windows.columns]
    windows_spark = spark.createDataFrame(tier2_windows[windows_cols])

    table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_windows_metadata"
    windows_spark.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table_name)

    print(f"  ✓ Saved to {table_name}")
    print(f"  Rows: {len(tier2_windows):,}")
    print(f"  Patients: {tier2_windows['patient_id'].nunique()}")
else:
    print("⚠️ tier2_windows is empty - cannot save baseline_windows_metadata")

# COMMAND ----------

# DBTITLE 1,Save diabetes_data_cleaned to UC
if 'all_patients_cleaned' in locals() and len(all_patients_cleaned) > 0:
    print("\nSaving diabetes_data_cleaned to Unity Catalog...")
    print("=" * 80)

    cols_cleaned = [
        'patient_id', 'time',
        'glucose',
        'calories', 'heart_rate', 'steps',
        'basal_rate', 'bolus_volume_delivered', 'carb_input'
    ]
    if 'is_non_anchor_15min' in all_patients_cleaned.columns:
        cols_cleaned.append('is_non_anchor_15min')

    cols_cleaned = [c for c in cols_cleaned if c in all_patients_cleaned.columns]
    cleaned_for_save = all_patients_cleaned[cols_cleaned].copy()

    # Workaround: strip Spark metadata issues by reconstructing from values
    cleaned_for_save = pd.DataFrame(cleaned_for_save.values, columns=cleaned_for_save.columns)

    # Restore datetime column types after values roundtrip
    cleaned_for_save['time'] = pd.to_datetime(cleaned_for_save['time']).astype(str)

    temp_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{VOLUME_NAME}/temp/diabetes_data_cleaned.parquet"
    import os
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)

    cleaned_for_save.to_parquet(temp_path, index=False, engine='pyarrow')
    print(f"  ✓ Written {len(cleaned_for_save):,} rows to {temp_path}")

    cleaned_spark = spark.read.parquet(temp_path).withColumn('time', F.to_timestamp(F.col('time')))

    table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data_cleaned"
    cleaned_spark.write.mode("overwrite").option("mergeSchema", "true").saveAsTable(table_name)

    print(f"  ✓ Saved to {table_name}")
else:
    print("⚠️ all_patients_cleaned not available - cannot save diabetes_data_cleaned")

# COMMAND ----------

# DBTITLE 1,Saved tables summary
print("\n" + "=" * 80)
print("SAVED TABLES SUMMARY")
print("=" * 80)

print(f"\nCatalog.Schema: {CATALOG_NAME}.{SCHEMA_NAME}")

print("\n1) baseline_timeseries")
print("   - 10–14 day windows on 5-min grid (may overlap)")
print("   - Slim schema: patient_id/time/glucose + calories/hr/steps + insulin/carbs + window metadata")

print("\n2) baseline_windows_metadata")
print("   - Window metadata for sampling/tracking")

print("\n3) diabetes_data_cleaned")
print("   - Full longitudinal slim feature table for QC and re-windowing")
print("   - No interpolation removal; no missingness modeling")

print("\nTo reload:")
print(f"  baseline_df = spark.table('{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries')")
print(f"  windows_df  = spark.table('{CATALOG_NAME}.{SCHEMA_NAME}.baseline_windows_metadata')")
print(f"  cleaned_df  = spark.table('{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data_cleaned')")

print("\n" + "=" * 80)
print("✓ Done")
print("=" * 80)


# COMMAND ----------

# DBTITLE 1,Sanity check: load tables + schema preview
baseline_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries"
windows_tbl  = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_windows_metadata"
cleaned_tbl  = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data_cleaned"

print("Sanity check: reading back saved tables...")
print("=" * 80)

baseline_df_spark = spark.table(baseline_tbl)
windows_df_spark  = spark.table(windows_tbl)
cleaned_df_spark  = spark.table(cleaned_tbl)

print("baseline_timeseries columns:")
print(baseline_df_spark.columns)

print("\nbaseline_windows_metadata columns:")
print(windows_df_spark.columns)

print("\ndiabetes_data_cleaned columns:")
print(cleaned_df_spark.columns)

display(baseline_df_spark.limit(5))
display(windows_df_spark.limit(5))
display(cleaned_df_spark.limit(5))

# COMMAND ----------

# DBTITLE 1,Sanity check: duplicates expected in baseline_timeseries
# baseline_timeseries may have duplicates on (patient_id, time) across different window_id.
from pyspark.sql import functions as F

dup_check = (baseline_df_spark
             .groupBy("patient_id","time")
             .agg(F.count("*").alias("n"))
             .filter(F.col("n") > 1)
             .count())

print(f"Duplicate (patient_id,time) rows in baseline_timeseries (expected if overlapping windows): {dup_check:,}")

# COMMAND ----------

# DBTITLE 1,Sanity check: daily counts on cleaned table (should be ~288)
daily_counts = (cleaned_df_spark
                .withColumn("date", F.to_date("time"))
                .groupBy("patient_id","date")
                .agg(F.count("*").alias("n"))
                .orderBy(F.desc("n")))

display(daily_counts.limit(20))

# COMMAND ----------

# DBTITLE 1,If you want NON-overlapping windows (optional alternative)
# Overlapping windows are OK for pseudo-patient generation, but if you want fewer duplicates,
# you can enforce non-overlap by taking only one window start per patient every N days.
#
# This is optional and not required for your stated use case.

# Example: keep only the best-quality window per patient (highest avg_presence_pct),
# then extract those windows (one per patient).
#
# best_windows = (tier2_windows.sort_values(['patient_id','avg_presence_pct'], ascending=[True, False])
#                            .groupby('patient_id')
#                            .head(1)
#                            .reset_index(drop=True))
#
# Then rebuild baseline_dataset using best_windows instead of recommended_windows.

# COMMAND ----------

# DBTITLE 1,review dups
# Duplicates in `baseline_timeseries` mean **the same `(patient_id, time)` row appears more than once**. They’re expected because `baseline_timeseries` is built by **extracting many 10–14 day windows**, and those windows often **overlap in time** for the same patient.

# ## How duplicates are identified
# A “duplicate” is defined as:

# - Same `patient_id`
# - Same `time`
# - Appears in **multiple rows** (typically because it belongs to multiple `window_id`s)

## In Spark,  identify them by grouping on `(patient_id, time)` and counting:

# from pyspark.sql import functions as F

# dup_df = (spark.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries")
#           .groupBy("patient_id", "time")
#           .agg(F.count("*").alias("n"))
#           .filter(F.col("n") > 1))

# dup_df.show()


## If  include `window_id`, can see *why* it duplicates (which windows contain the same timestamp):

# from pyspark.sql import functions as F

# baseline = spark.table(f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries")

# dups_with_windows = (baseline
#     .groupBy("patient_id", "time")
#     .agg(
#         F.count("*").alias("n"),
#         F.collect_set("window_id").alias("window_ids")
#     )
#     .filter(F.col("n") > 1))

# display(dups_with_windows)


# ## Why duplicates are expected
# Your windowing step does something like:

# - For each patient, slide a window across days (e.g., days 1–10, 2–11, 3–12, …)
# - Every window becomes a new `window_id`
# - The *same timestamp* can belong to multiple windows

# Example (one patient):

# - Window A: Jan 01–Jan 10  
# - Window B: Jan 02–Jan 11  

# All timestamps from **Jan 02–Jan 10** appear in both windows ⇒ duplicates on `(patient_id, time)`.

# So duplicates are not “bad data”; they’re a consequence of storing a **windowed training table** where the unique key is effectively:

# > `(window_id, time)` (and usually also `patient_id`)

# ### The proper “primary key”
# - In `diabetes_data_cleaned`: primary key is naturally `(patient_id, time)` (one row per timepoint).
# - In `baseline_timeseries`: primary key should be `(window_id, time)` (or `(window_id, patient_id, time)`).

# ## When duplicates matter
# - **Pseudo-patient generation:** duplicates are fine; you typically sample *by window_id*.
# - **Training/evaluation:** if you randomly split rows, duplicates can cause leakage (same timepoint in train and test via another window). Fix by splitting by:
#   - `patient_id` (best), or
#   - `window_id` (acceptable), not by row.

# >> build a non-overlapping `baseline_timeseries` (e.g., one best window per patient or windows stepped by 10–14 days) to eliminate most duplicates.

# COMMAND ----------

# DBTITLE 1,baseline ts summary stats
from pyspark.sql import functions as F

# Load baseline_timeseries table
baseline_tbl = f"{CATALOG_NAME}.{SCHEMA_NAME}.baseline_timeseries"
baseline_df = spark.table(baseline_tbl)

# Count distinct window_ids per patient_id
windows_per_patient = (baseline_df
    .groupBy("patient_id")
    .agg(
        F.countDistinct("window_id").alias("num_windows"),
        F.count("*").alias("total_records")
    )
    .orderBy(F.desc("num_windows"))
)

print("=" * 80)
print("DISTINCT WINDOW_IDs PER PATIENT_ID")
print("=" * 80)

windows_per_patient_pd = windows_per_patient.toPandas()

print(f"\nSummary Statistics:")
print(f"  Total patients: {len(windows_per_patient_pd)}")
print(f"  Total windows across all patients: {windows_per_patient_pd['num_windows'].sum()}")
print(f"  Average windows per patient: {windows_per_patient_pd['num_windows'].mean():.1f}")
print(f"  Median windows per patient: {windows_per_patient_pd['num_windows'].median():.0f}")
print(f"  Min windows per patient: {windows_per_patient_pd['num_windows'].min()}")
print(f"  Max windows per patient: {windows_per_patient_pd['num_windows'].max()}")

print(f"\nPer-Patient Breakdown:")
print("-" * 80)
for idx, row in windows_per_patient_pd.iterrows():
    avg_records_per_window = row['total_records'] / row['num_windows']
    print(f"  {row['patient_id']}: {row['num_windows']} windows, {row['total_records']:,} total records ({avg_records_per_window:.0f} records/window)")

print("\n" + "=" * 80)

# Display as table
display(windows_per_patient)

# COMMAND ----------

# DBTITLE 1,NOTES
# Window Distribution Analysis
# Summary Statistics:
# Total patients: 25
# Total windows: 909 across all patients
# Average: 36.4 windows per patient
# Median: 7 windows per patient
# Range: 1 to 567 windows per patient
# Key Findings:
# High-Volume Patients (Most Windows):

# HUPA0027P: 567 windows (13.6M records) - Dominant patient
# HUPA0026P: 135 windows (3.2M records)
# HUPA0028P: 83 windows (1.9M records)
# Moderate-Volume Patients:

# 11 patients with 7 windows each
# 4 patients with 6 windows each
# 3 patients with 4-8 windows each
# Low-Volume Patients:

# 5 patients with 1-5 windows each
# HUPA0006P and HUPA0021P: Only 1 window each
# Why So Many Windows?
# Overlapping windows are expected:

# Windows are 7-14 days long
# Windows can start on consecutive days
# Same timestamps appear in multiple windows
# Example for HUPA0027P (567 windows):

# If patient has 580 days of data
# With 14-day windows sliding daily
# You get ~567 possible windows (580 - 14 + 1)
# Records Per Window:
# HUPA0027P: ~24,021 records/window (very dense, ~14 days)
# HUPA0026P: ~23,475 records/window
# HUPA0028P: ~23,026 records/window
# Most others: ~10,366 records/window (~7-10 days)
# HUPA0006P/0021P: ~2,016 records/window (~7 days minimum)
# Implications for Pseudo-Patient Generation:
# Sampling strategy:

# You have 909 total windows to sample from
# 3 patients (HUPA0027P, 0026P, 0028P) dominate with 785 windows (86% of total)
# When generating 50K pseudo-patients, you'll heavily sample from these 3 patients
# Consider stratified sampling to ensure diversity across all 25 patients

# Recommendation:
# Sample proportionally from all patients, not just by window count
# Or deduplicate to 1 best window per patient for more balanced representation

