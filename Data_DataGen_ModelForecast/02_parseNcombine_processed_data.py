# Databricks notebook source
# DBTITLE 1,UC config
## specify widgets

dbutils.widgets.text(
    "CATALOG_NAME",
    "hls_glucosphere",
    'CATALOG'
)
dbutils.widgets.text(
    "SCHEMA_NAME",
    "cgm", #Continuous Glucose Monitoring
    "SCHEMA"
)
dbutils.widgets.text(
    "VOLUME_NAME",
    "data", #HUPA-UCM diabetes dataset
    "VOLUMES"
)

CATALOG_NAME = dbutils.widgets.get("CATALOG_NAME")
SCHEMA_NAME = dbutils.widgets.get("SCHEMA_NAME")
VOLUME_NAME = dbutils.widgets.get("VOLUME_NAME")

# COMMAND ----------

# DBTITLE 1,check data schema
# csv_file = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{VOLUME_NAME}/HUPA-UCM Diabetes Dataset/Preprocessed/HUPA0001P.csv"

csv_file = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{VOLUME_NAME}/HUPA-UCM Diabetes Dataset/Preprocessed/HUPA0002P.csv"


# Try with comma delimiter
print("Attempting to parse with comma delimiter...")
df = spark.read.option("header", "true") \
              .option("inferSchema", "true") \
              .option("delimiter", ";") \
              .csv(csv_file)

print(f"\nColumns found: {len(df.columns)}")
print("Column names:", df.columns)
print(f"Row count: {df.count()}")

display(df.limit(1000))

# COMMAND ----------

# DBTITLE 1,parse and combine all processed data
from pyspark.sql.functions import col, current_timestamp, regexp_extract
import os

csv_path = f"/Volumes/{CATALOG_NAME}/{SCHEMA_NAME}/{VOLUME_NAME}/HUPA-UCM Diabetes Dataset/Preprocessed/"
delta_table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_data"
summary_table_name = f"{CATALOG_NAME}.{SCHEMA_NAME}.diabetes_summary"

try:
    print("Reading all patient CSV files...")
    
    # Read all CSV files
    df = spark.read.option("header", "true") \
                   .option("inferSchema", "true") \
                   .option("delimiter", ";") \
                   .csv(csv_path + "*.csv")
    
    # Extract patient ID from filename
    df = (df
          .withColumn("patient_id", regexp_extract(col("_metadata.file_path"), "([^/]+)\\.csv$", 1))
          .withColumn("load_timestamp", current_timestamp()))
    
    print(f"Total rows: {df.count()}")
    print(f"Columns: {df.columns}")
    
    # Save with partitioning by patient_id for better query performance
    print(f"\nSaving to Delta table with partitioning...")
    df.write.format("delta") \
            .mode("overwrite") \
            .option("overwriteSchema", "true") \
            .partitionBy("patient_id") \
            .saveAsTable(delta_table_name)
    
    print(f"✓ SUCCESS! Data partitioned by patient_id")
    
    # Create patient summary
    print("\nCreating patient summary...")
    summary = spark.sql(f"""
        SELECT 
            patient_id,
            COUNT(*) as record_count,
            MIN(load_timestamp) as loaded_at
        FROM {delta_table_name}
        GROUP BY patient_id, load_timestamp
        ORDER BY patient_id
    """)
    
    display(summary)
    
    # Save summary to Delta table
    print(f"\nSaving summary to: {summary_table_name}")
    summary.write.format("delta") \
                 .mode("overwrite") \
                 .option("overwriteSchema", "true") \
                 .saveAsTable(summary_table_name)
    
    print(f"✓ SUCCESS! Summary saved to {summary_table_name}")
    
    # Display final statistics
    print("\n" + "=" * 70)
    print("FINAL STATISTICS")
    print("=" * 70)
    print(f"Total patients: {summary.count()}")
    print(f"Detailed table: {delta_table_name}")
    print(f"Summary table: {summary_table_name}")
    print("=" * 70)
    
except Exception as e:
    print(f"!!! Error: {e}")
    import traceback
    traceback.print_exc()

# COMMAND ----------

## ADDITIONAL Data Attributes to include:

## add demographics patient id | dob | age | region | gender | datetime of device use |
## device type == alpha beta etc. 
## device id (model) some alpha numeric || patient id + something 
## firmware version e.g. 4.1 -- related to issue ##


# COMMAND ----------

# MAGIC %md
# MAGIC
