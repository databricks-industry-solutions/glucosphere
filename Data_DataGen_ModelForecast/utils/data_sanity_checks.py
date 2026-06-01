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
print(f"Sanity-checking {CATALOG_NAME}.{SCHEMA_NAME}")

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
        "Data sanity checks FAILED — clinically-impossible records present:\n" + lines +
        "\n\nFix the data-gen (notebooks 04/05/06 for glucose; the registry generator for "
        "diagnosis-by-age) and re-run. This gate exists so implausible data never reaches the demo."
    )
print("\n[SUCCESS] All data sanity checks passed — no clinically-impossible records.")
