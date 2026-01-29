# Databricks notebook source
# MAGIC %md
# MAGIC ### HUPA-UCM diabetes dataset 
# MAGIC - Ref Research Data: https://www.sciencedirect.com/science/article/pii/S2352340924005262
# MAGIC - Dataset: https://data.mendeley.com/datasets/3hbcscwz44/1 

# COMMAND ----------

# dbutils.widgets.removeAll()

# COMMAND ----------

# DBTITLE 1,UC config.
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

# DBTITLE 1,Create Catalog.Schema.Vols if not exist
# spark.sql(
#     f"CREATE CATALOG IF NOT EXISTS {CATALOG_NAME}"
# ) ## permissions required depending on workspace
spark.sql(
    f"CREATE SCHEMA IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}"
)
spark.sql(
    f"CREATE VOLUME IF NOT EXISTS {CATALOG_NAME}.{SCHEMA_NAME}.{VOLUME_NAME}"
)

# COMMAND ----------

# DBTITLE 1,Check if Vol is created
# display(spark.sql(f"SHOW TABLES IN {CATALOG_NAME}.{SCHEMA_NAME}"))
display(spark.sql(f"SHOW VOLUMES IN {CATALOG_NAME}.{SCHEMA_NAME}"))

# COMMAND ----------

# DBTITLE 1,Download HUPA-UCM diabetes dataset
import requests
import zipfile
import os
import shutil

# Configuration
url = "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/3hbcscwz44-1.zip"
catalog = CATALOG_NAME
schema = SCHEMA_NAME
volume = VOLUME_NAME
volume_path = f"/Volumes/{catalog}/{schema}/{volume}"
temp_dir = "/tmp/download_temp"

try:
    # Step 1: Create Unity Catalog structure
    print("Creating Unity Catalog structure...")
    # spark.sql(f"CREATE CATALOG IF NOT EXISTS {catalog}")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")
    print(f"✓ Volume created: {catalog}.{schema}.{volume}\n")
    
    # Step 2: Download file
    print(f"Downloading from URL...")
    os.makedirs(temp_dir, exist_ok=True)
    zip_path = os.path.join(temp_dir, "data.zip")
    
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    
    total_size = 0
    with open(zip_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                total_size += len(chunk)
    
    print(f"✓ Downloaded {total_size / (1024*1024):.2f} MB\n")
    
    # Step 3: Extract to Unity Catalog volume
    print(f"Extracting to {volume_path}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(volume_path)
    
    print(f"✓ Extraction complete\n")
    
    # Step 4: Cleanup
    shutil.rmtree(temp_dir)
    
    # Step 5: Display results
    print("=" * 70)
    print(f"VOLUME CONTENTS: {catalog}.{schema}.{volume}")
    print("=" * 70)
    
    for root, dirs, files in os.walk(volume_path):
        level = root.replace(volume_path, '').count(os.sep)
        indent = '  ' * level
        folder = os.path.basename(root) or volume
        print(f"{indent}📁 {folder}/")
        
        subindent = '  ' * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path) / 1024
            print(f"{subindent}📄 {file} ({size:.2f} KB)")
    
    print("=" * 70)
    print(f"\n✓ SUCCESS! Data available at: {volume_path}")
    
except Exception as e:
    print(f"!!! Error: {e}")
    import traceback
    traceback.print_exc()

# COMMAND ----------

# MAGIC %md
# MAGIC
