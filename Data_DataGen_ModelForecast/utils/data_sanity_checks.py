# Databricks notebook source
# MAGIC %md
# MAGIC # Data Sanity Checks (clinical-plausibility gate)
# MAGIC
# MAGIC Fails the job if the generated data contains clinically-impossible records, so an
# MAGIC implausible row (e.g. a 9-year-old with Type 2 diabetes, a >55yo "gestational" patient,
# MAGIC a glucose reading of 0 mg/dL) can never silently reach the app/demo again.
# MAGIC
# MAGIC Runs AFTER the DLT pipeline builds `gold_patient_device_readings` (so it checks the
# MAGIC consumption-layer table the app actually reads) + `fleet_forecast_incident`.
# MAGIC
# MAGIC Thresholds are intentionally **buffered** (e.g. T2D flagged only < 13, gestational only
# MAGIC < 15 or > 55) so a 1-year drift between the generator's reference year and the gate's
# MAGIC `CURRENT_DATE` can't cause a false failure — the gate catches the *egregious*, not the borderline.

# COMMAND ----------

dbutils.widgets.text("CATALOG_NAME", "your_workspace_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere", "Schema")
CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME = dbutils.widgets.get("SCHEMA_NAME")
G = f"{CATALOG_NAME}.{SCHEMA_NAME}.gold_patient_device_readings"
R = f"{CATALOG_NAME}.{SCHEMA_NAME}.silver_patient_registry"
F = f"{CATALOG_NAME}.{SCHEMA_NAME}.fleet_forecast_incident"
P = f"{CATALOG_NAME}.{SCHEMA_NAME}.pseudo_incident_7d_labeled"
print(f"Sanity-checking {CATALOG_NAME}.{SCHEMA_NAME}")

# COMMAND ----------

# MAGIC %run ./additional_patient_info/_device_model_spec

# COMMAND ----------

# device_model cohort gating uses the SAME shared spec the generators use, so the gate
# auto-tracks the single source of truth and FAILS the run if a future change ever
# decouples device_model from bias direction again (e.g. the old random fallback that
# biased all six models). POS_BIAS_MODELS / NEG_BIAS_MODELS / CLEAN_MODELS come from the
# %run above.
_in = lambda ms: ",".join(f"'{m}'" for m in ms)

# COMMAND ----------

# Each check: (label, SQL returning a single integer violation count, human description).
# A non-zero count is a FAILURE. Age uses the same YEAR(CURRENT_DATE()) - birth_year the app displays.
checks = [
    ("t2d_pediatric",
     f"SELECT COUNT(*) FROM {R} WHERE patient_diagnosis='T2D' AND (YEAR(CURRENT_DATE()) - birth_year) < 13",
     "Type 2 diabetes assigned to a patient under 13"),
    ("gestational_implausible_age",
     f"SELECT COUNT(*) FROM {R} WHERE patient_diagnosis='gestational' AND ((YEAR(CURRENT_DATE()) - birth_year) < 15 OR (YEAR(CURRENT_DATE()) - birth_year) > 55)",
     "Gestational diabetes outside plausible childbearing age (15-55)"),
    ("impossible_age",
     f"SELECT COUNT(*) FROM {R} WHERE (YEAR(CURRENT_DATE()) - birth_year) < 1 OR (YEAR(CURRENT_DATE()) - birth_year) > 100",
     "Patient age outside [1, 100]"),
    ("glucose_out_of_physio_range",
     f"SELECT COUNT(*) FROM {G} WHERE glucose < 40 OR glucose > 400",
     "Glucose reading outside the physiological CGM range [40, 400] mg/dL"),
    ("glucose_null",
     f"SELECT COUNT(*) FROM {G} WHERE glucose IS NULL",
     "Null glucose reading"),
    ("forecast_out_of_range",
     f"SELECT COUNT(*) FROM {F} WHERE pred_15m < 40 OR pred_15m > 400 OR pred_30m < 40 OR pred_30m > 400",
     "Forecast prediction outside [40, 400] mg/dL"),
    ("patients_without_forecast",
     f"SELECT COUNT(*) FROM (SELECT DISTINCT patient_id FROM {G}) g LEFT ANTI JOIN {F} f ON g.patient_id = f.patient_id",
     "Patient in gold with no forecast row (would render '—')"),
    ("clean_models_in_incident",
     f"SELECT COUNT(*) FROM (SELECT DISTINCT p.patient_id FROM {P} p JOIN {R} r ON p.patient_id=r.patient_id WHERE p.has_incident=1 AND r.device_model IN ({_in(CLEAN_MODELS)}))",
     f"Control device model ({'/'.join(CLEAN_MODELS)}) assigned to an incident cohort — must stay clean"),
    ("positive_cohort_wrong_model",
     f"SELECT COUNT(*) FROM (SELECT DISTINCT p.patient_id FROM {P} p JOIN {R} r ON p.patient_id=r.patient_id WHERE p.has_incident=1 AND p.incident_direction='positive' AND r.device_model NOT IN ({_in(POS_BIAS_MODELS)}))",
     f"Over-read (positive) incident on a device that is not {'/'.join(POS_BIAS_MODELS)}"),
    ("negative_cohort_wrong_model",
     f"SELECT COUNT(*) FROM (SELECT DISTINCT p.patient_id FROM {P} p JOIN {R} r ON p.patient_id=r.patient_id WHERE p.has_incident=1 AND p.incident_direction='negative' AND r.device_model NOT IN ({_in(NEG_BIAS_MODELS)}))",
     f"Under-read (negative) incident on a device that is not {'/'.join(NEG_BIAS_MODELS)}"),
]

violations = []
for name, sql, desc in checks:
    n = spark.sql(sql).collect()[0][0]
    status = "OK" if n == 0 else "FAIL"
    print(f"  [{status}] {name}: {n}  — {desc}")
    if n:
        violations.append((name, n, desc))

# COMMAND ----------

if violations:
    lines = "\n".join(f"  - {name}: {n} rows — {desc}" for name, n, desc in violations)
    raise RuntimeError(
        "Data sanity checks FAILED — implausible or inconsistent records present:\n" + lines +
        "\n\nFix the data-gen and re-run: notebooks 04/05/06 for glucose; the registry generator "
        "for diagnosis-by-age; the shared utils/additional_patient_info/_device_model_spec for any "
        "device_model cohort-gating failure (device_model must be a deterministic function of "
        "patient_id, identical across 05 + the registry + the telemetry generator). This gate "
        "exists so implausible/inconsistent data never reaches the demo."
    )
print("\n[SUCCESS] All data sanity checks passed — no clinically-impossible records.")
