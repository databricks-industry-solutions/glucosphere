# Databricks notebook source

# COMMAND ----------

%pip install pyyaml "mlflow[databricks]" databricks-sdk --quiet
dbutils.library.restartPython()

# COMMAND ----------
# DBTITLE 1,Verify YAML config exists
# ------------------------
# Verify existing YAML config file
# Uses configs/baseline_config.yaml (shared with other notebooks)
# ------------------------
import os
import yaml

config_file = "configs/baseline_config.yaml"

if os.path.exists(config_file):
    print(f"✓ Config file found: {config_file}")
    
    # Load and display summary
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    print(f"\nConfig summary:")
    print(f"  - dev: {len(config.get('dev', {}))} parameters")
    print(f"  - staging: {len(config.get('staging', {}))} parameters (+ inherits from dev)")
    print(f"  - prod: {len(config.get('prod', {}))} parameters (+ inherits from dev)")
    
    # Show key parameters
    dev_config = config.get('dev', {})
    print(f"\nKey dev parameters:")
    print(f"  num_pseudo: {dev_config.get('num_pseudo')}")
    print(f"  incident_pct: {dev_config.get('incident_pct')} ({dev_config.get('incident_pct', 0)*100:.0f}% of patients)")
    print(f"  calibration_bias_mgdl: {dev_config.get('calibration_bias_mgdl')} mg/dL")
    print(f"  demo_week_start: {dev_config.get('demo_week_start')}")
    print(f"  lags: {dev_config.get('lags')}")
    print(f"  max_depth: {dev_config.get('max_depth')}, eta: {dev_config.get('eta')}")
    
    print(f"\n✓ Config file ready for use in Cell 3")
else:
    print(f"⚠️  Config file not found: {config_file}")
    print(f"\nPlease ensure the config file exists at: {config_file}")
    print(f"\nIf missing, create it with the baseline notebook or copy from:")
    print(f"  /Users/may.merkletan@databricks.com/hls-glucosphere/Data/configs/baseline_config.yaml")

# COMMAND ----------

# DBTITLE 1,Essential Widgets (6 only - YAML config approach)
# ------------------------
# Essential Widgets (6 only - down from 50!)
# All other parameters loaded from YAML config
# ------------------------

# Remove all existing widgets first
dbutils.widgets.removeAll()

# Essential widgets only
dbutils.widgets.dropdown("ENV", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("CATALOG_NAME", "mmt_aws_usw2_catalog", "Catalog")
dbutils.widgets.text("SCHEMA_NAME", "glucosphere_dev", "Schema")
dbutils.widgets.dropdown("INCLUDE_INCIDENT", "false", ["false", "true"], "Include Incident")
dbutils.widgets.text("CONFIG_FILE", "configs/baseline_config.yaml", "Config File")
dbutils.widgets.text("NUM_PSEUDO_OVERRIDE", "", "Num Pseudo Override (optional)")

print("✓ Essential widgets created (6 total)")
print("\nWidget values:")
print(f"  ENV: {dbutils.widgets.get('ENV')}")
print(f"  CATALOG: {dbutils.widgets.get('CATALOG_NAME')}")
print(f"  SCHEMA: {dbutils.widgets.get('SCHEMA_NAME')}")
print(f"  INCLUDE_INCIDENT: {dbutils.widgets.get('INCLUDE_INCIDENT')}")
print(f"  CONFIG_FILE: {dbutils.widgets.get('CONFIG_FILE')}")
print(f"\nℹ️  All other parameters will be loaded from YAML config")

# COMMAND ----------

# DBTITLE 1,Configuration Loader (Hybrid: Widgets + cfg object)
# ------------------------
# Configuration Loader (YAML + Widget Overrides)
# Loads bulk config from YAML, overrides with widgets
# Exposes all parameters as UPPERCASE for backward compatibility
# ------------------------

import yaml
import os
from pathlib import Path

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
            print(f"   Please run Cell 5 to generate YAML content, then save it as {yaml_path}")
            print(f"   Using empty config - this cell will fail until config file is created.")
            return {}
        except Exception as e:
            print(f"⚠️  Error loading config: {str(e)}")
            return {}
    
    def __getattr__(self, name):
        """Get config value with widget override support (UPPERCASE)"""
        # Convert to uppercase for lookup
        name_upper = name.upper()
        
        # Use object.__getattribute__ to avoid recursion when accessing internal attributes
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
    
    def summary(self):
        """Print configuration summary"""
        print(f"✓ Configuration loaded (env={self._env})")
        print(f"\nData:")
        print(f"  BASELINE_TBL: {self.BASELINE_TBL}")
        print(f"  NUM_PSEUDO: {self.NUM_PSEUDO}, ROWS_7D: {self.SEG_DAYS * int((24*60)//self.CADENCE_MIN)}")
        print(f"\nTransformation:")
        print(f"  INCLUDE_INCIDENT: {self.INCLUDE_INCIDENT}")
        print(f"  GAIN: ({self.GAIN_LO}, {self.GAIN_HI})")
        print(f"  ALPHAS: (INS={self.ALPHA_INS}, CARB={self.ALPHA_CARB}, STEPS={self.ALPHA_STEPS})")
        print(f"  GLUCOSE_OFFSET: {self.GLUCOSE_OFFSET} mg/dL")
        print(f"\nFeatures:")
        print(f"  LAGS: {self.LAGS}, ROLL_WINDOWS: {self.get_list_int('ROLL_WINDOWS')}")
        print(f"  TRAIN_SAMPLE_FRAC: {self.TRAIN_SAMPLE_FRAC}")
        print(f"\nXGBoost:")
        print(f"  MAX_DEPTH: {self.MAX_DEPTH}, ETA: {self.ETA}")
        print(f"  N_ROUNDS: {self.N_ROUNDS}, EARLY_STOP: {self.EARLY_STOP}")

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

# Computed values (derived from config) - ONLY these are needed as globals
ROWS_PER_DAY = int((24*60)//cfg.CADENCE_MIN)
ROWS_7D = cfg.SEG_DAYS * ROWS_PER_DAY
HORIZONS = [1, 2, 3, 6]  # 5/10/15/30 min ahead
ROLL_WINDOWS = cfg.get_list_int('ROLL_WINDOWS')

# Computed incident timestamps (needed by multiple cells)
import pandas as pd
incident_start_ts = pd.Timestamp(cfg.DEMO_WEEK_START) + pd.Timedelta(days=cfg.INCIDENT_START_DAY, hours=cfg.INCIDENT_START_HOUR)
incident_end_ts = incident_start_ts + pd.Timedelta(minutes=cfg.INCIDENT_DURATION_MIN)  # Calculate from start + duration
demo_week_start = cfg.DEMO_WEEK_START

# Print summary
cfg.summary()
print(f"\n✓ Computed values: ROWS_PER_DAY={ROWS_PER_DAY}, ROWS_7D={ROWS_7D}, HORIZONS={HORIZONS}")
print(f"\n✓ Incident window: {incident_start_ts} to {incident_end_ts} ({cfg.INCIDENT_DURATION_MIN} min)")

# COMMAND ----------

# DBTITLE 1,Define Output Tables
# ------------------------
# Output Tables
# Using cfg object for clean access
# ------------------------

base2_tbl       = f"{cfg.catalog_name}.{cfg.schema_name}.gen_base_with_contigs_7d"
base2_clean_tbl = f"{cfg.catalog_name}.{cfg.schema_name}.gen_base_with_contigs_7d_clean"
contigs_tbl     = f"{cfg.catalog_name}.{cfg.schema_name}.gen_contig_registry_7d"
seg_tbl         = f"{cfg.catalog_name}.{cfg.schema_name}.gen_segment_registry_7d_stride{cfg.stride_days}"
plan_tbl        = f"{cfg.catalog_name}.{cfg.schema_name}.gen_pseudo_plan_7d"
joined_tbl      = f"{cfg.catalog_name}.{cfg.schema_name}.gen_joined_slices_7d"

pseudo_clean_tbl    = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_clean_7d"
pseudo_incident_tbl = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_incident_7d"

clean_labeled_tbl               = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_clean_7d_labeled"
incident_labeled_observed_tbl   = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_incident_7d_labeled_observed"
incident_labeled_true_tbl       = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_incident_7d_labeled_true"
incident_flag_tbl               = f"{cfg.catalog_name}.{cfg.schema_name}.pseudo_incident_7d_with_flag"

baseline_val_tbl = f"{cfg.catalog_name}.{cfg.schema_name}.baseline_for_validation_7d"

xgb_features_tbl   = f"{cfg.catalog_name}.{cfg.schema_name}.xgb_flat_min_lags{cfg.lags}"
fleet_forecast_tbl = f"{cfg.catalog_name}.{cfg.schema_name}.fleet_forecast_now"

# UC model names
uc_model_fqn_15m = f"{cfg.catalog_name}.{cfg.schema_name}.{cfg.uc_model_name_15m}"
uc_model_fqn_30m = f"{cfg.catalog_name}.{cfg.schema_name}.{cfg.uc_model_name_30m}"

# COMMAND ----------

# DBTITLE 1,Import libraries
from pyspark.sql import functions as F, Window
from pyspark.sql.types import *
import pandas as pd
import numpy as np

# COMMAND ----------

# DBTITLE 1,Endpoint Configuration
# ------------------------
# Model Serving Endpoint Configuration
# ------------------------
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    ServedEntityInput,
    EndpointCoreConfigInput,
    AutoCaptureConfigInput
)

# Initialize Databricks SDK
w = WorkspaceClient()

# Catalog and Schema (from config)
CATALOG = cfg.CATALOG_NAME
SCHEMA = cfg.SCHEMA_NAME

# Model names (fully qualified)
MODEL_15M = uc_model_fqn_15m  # hls_glucosphere.cgm.cgm_xgb_15m
MODEL_30M = uc_model_fqn_30m  # hls_glucosphere.cgm.cgm_xgb_30m

# Endpoint names
ENDPOINT_15M = "cgm-glucose-forecast-15min"
ENDPOINT_30M = "cgm-glucose-forecast-30min"

# Inference table name PREFIX (not full path - auto_capture_config adds catalog.schema automatically)
INFERENCE_TABLE_PREFIX_15M = "inference_log_15m"
INFERENCE_TABLE_PREFIX_30M = "inference_log_30m"

# Full table names (for reference/monitoring)
INFERENCE_TABLE_15M = f"{CATALOG}.{SCHEMA}.{INFERENCE_TABLE_PREFIX_15M}"
INFERENCE_TABLE_30M = f"{CATALOG}.{SCHEMA}.{INFERENCE_TABLE_PREFIX_30M}"

print("✓ Endpoint configuration")
print(f"\nCatalog & Schema:")
print(f"  Catalog: {CATALOG}")
print(f"  Schema: {SCHEMA}")
print(f"\nModels:")
print(f"  15-min: {MODEL_15M}@Champion")
print(f"  30-min: {MODEL_30M}@Champion")
print(f"\nEndpoints:")
print(f"  15-min: {ENDPOINT_15M}")
print(f"  30-min: {ENDPOINT_30M}")
print(f"\nInference tables (auto-created):")
print(f"  15-min: {INFERENCE_TABLE_15M}_payload")
print(f"  30-min: {INFERENCE_TABLE_30M}_payload")

# COMMAND ----------

# DBTITLE 1,Create 15-min Endpoint with AI Gateway
# ------------------------
# Create/Update 15-min Forecast Endpoint with AI Gateway Inference Tables
# Step 1: Create endpoint, Step 2: Wait for ready, Step 3: Configure AI Gateway
# ------------------------
import requests
import json
import time

print(f"Creating endpoint: {ENDPOINT_15M}...")

# Get the version number for Champion alias (or latest version)
from mlflow.tracking import MlflowClient
import mlflow

mlflow.set_registry_uri('databricks-uc')
mlflow_client = MlflowClient()

try:
    # Try to get Champion version
    model_versions = mlflow_client.get_model_version_by_alias(MODEL_15M, "Champion")
    champion_version = model_versions.version
    print(f"  Using Champion version: {champion_version}")
except Exception as e:
    # Fallback: get latest version
    try:
        all_versions = mlflow_client.search_model_versions(f"name='{MODEL_15M}'")
        if all_versions:
            latest = max(all_versions, key=lambda v: int(v.version))
            champion_version = latest.version
            print(f"  Champion alias not found, using latest version: {champion_version}")
        else:
            champion_version = "1"
            print(f"  No versions found, using version 1")
    except Exception as e2:
        champion_version = "1"
        print(f"  Could not determine version, using version 1")

# Check if endpoint exists
try:
    existing = w.serving_endpoints.get(name=ENDPOINT_15M)
    endpoint_exists = True
    print(f"  Endpoint exists, will update...")
except Exception as e:
    endpoint_exists = False
    print(f"  Endpoint doesn't exist, will create...")

# Create or update endpoint
if endpoint_exists:
    # Update existing endpoint
    w.serving_endpoints.update_config(
        name=ENDPOINT_15M,
        served_entities=[
            ServedEntityInput(
                entity_name=MODEL_15M,
                entity_version=champion_version,
                scale_to_zero_enabled=True,
                workload_size="Small"
            )
        ]
    )
    print(f"✓ Updated endpoint: {ENDPOINT_15M}")
else:
    # Create new endpoint
    w.serving_endpoints.create(
        name=ENDPOINT_15M,
        config=EndpointCoreConfigInput(
            name=ENDPOINT_15M,
            served_entities=[
                ServedEntityInput(
                    entity_name=MODEL_15M,
                    entity_version=champion_version,
                    scale_to_zero_enabled=True,
                    workload_size="Small"
                )
            ]
        )
    )
    print(f"✓ Created endpoint: {ENDPOINT_15M}")

# STEP 2: Wait for endpoint to be fully ready before configuring AI Gateway
print(f"\nWaiting for endpoint to be ready before configuring AI Gateway...")
max_wait = 600  # 10 minutes
wait_interval = 15  # 15 seconds
elapsed = 0

while elapsed < max_wait:
    try:
        endpoint_status = w.serving_endpoints.get(name=ENDPOINT_15M)
        config_update = str(endpoint_status.state.config_update) if endpoint_status.state and endpoint_status.state.config_update else "UNKNOWN"
        ready_status = str(endpoint_status.state.ready) if endpoint_status.state and endpoint_status.state.ready else "UNKNOWN"
        
        # Check if endpoint is fully ready (NOT_UPDATING and READY)
        if "NOT_UPDATING" in config_update and "READY" in ready_status:
            print(f"  ✓ Endpoint is READY (elapsed: {elapsed}s)")
            break
        
        print(f"  Status: {config_update} | Ready: {ready_status} | Elapsed: {elapsed}s")
        time.sleep(wait_interval)
        elapsed += wait_interval
    except Exception as wait_error:
        print(f"  Waiting... {elapsed}s")
        time.sleep(wait_interval)
        elapsed += wait_interval

if elapsed >= max_wait:
    print(f"  ⚠️  Timeout waiting for endpoint - skipping AI Gateway config")
    print(f"  You can configure it manually later in the UI")
else:
    # STEP 3: Configure AI Gateway with inference tables using REST API
    print(f"\nConfiguring AI Gateway inference tables...")

    # Get workspace URL and token
    workspace_url = w.config.host
    if not workspace_url.startswith('http'):
        workspace_url = f"https://{workspace_url}"

    # Get token from dbutils (works on serverless)
    try:
        token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    except:
        token = w.config.token

    # AI Gateway configuration payload
    ai_gateway_config = {
        "inference_table_config": {
            "catalog_name": CATALOG,
            "schema_name": SCHEMA,
            "table_name_prefix": INFERENCE_TABLE_PREFIX_15M,
            "enabled": True
        }
    }

    # PUT request to configure AI Gateway
    api_url = f"{workspace_url}/api/2.0/serving-endpoints/{ENDPOINT_15M}/ai-gateway"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.put(api_url, headers=headers, json=ai_gateway_config)
        
        if response.status_code in [200, 201]:
            print(f"✓ AI Gateway inference tables configured")
            print(f"  Table: {INFERENCE_TABLE_15M}_payload (auto-created on first request)")
        else:
            print(f"⚠️  AI Gateway configuration response: {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"⚠️  Could not configure AI Gateway: {str(e)}")
        print(f"  You can configure it manually in the UI: AI Gateway tab > Enable Inference tables")

# Get endpoint URL
workspace_url = w.config.host
if not workspace_url.startswith('http'):
    workspace_url = f"https://{workspace_url}"
endpoint_url = f"{workspace_url}/ml/endpoints/{ENDPOINT_15M}"

print(f"\nEndpoint URL: {endpoint_url}")
print(f"\n✅ Using AI Gateway (modern approach) for inference tables")

# COMMAND ----------

# DBTITLE 1,Create 30-min Endpoint with AI Gateway
# ------------------------
# Create/Update 30-min Forecast Endpoint with AI Gateway Inference Tables
# Step 1: Create endpoint, Step 2: Wait for ready, Step 3: Configure AI Gateway
# ------------------------
import requests
import json
import time

print(f"Creating endpoint: {ENDPOINT_30M}...")

# Get the version number for Champion alias (or latest version)
try:
    # Try to get Champion version
    model_versions = mlflow_client.get_model_version_by_alias(MODEL_30M, "Champion")
    champion_version = model_versions.version
    print(f"  Using Champion version: {champion_version}")
except Exception as e:
    # Fallback: get latest version
    try:
        all_versions = mlflow_client.search_model_versions(f"name='{MODEL_30M}'")
        if all_versions:
            latest = max(all_versions, key=lambda v: int(v.version))
            champion_version = latest.version
            print(f"  Champion alias not found, using latest version: {champion_version}")
        else:
            champion_version = "1"
            print(f"  No versions found, using version 1")
    except Exception as e2:
        champion_version = "1"
        print(f"  Could not determine version, using version 1")

# Check if endpoint exists
try:
    existing = w.serving_endpoints.get(name=ENDPOINT_30M)
    endpoint_exists = True
    print(f"  Endpoint exists, will update...")
except Exception as e:
    endpoint_exists = False
    print(f"  Endpoint doesn't exist, will create...")

# Create or update endpoint
if endpoint_exists:
    # Update existing endpoint
    w.serving_endpoints.update_config(
        name=ENDPOINT_30M,
        served_entities=[
            ServedEntityInput(
                entity_name=MODEL_30M,
                entity_version=champion_version,
                scale_to_zero_enabled=True,
                workload_size="Medium"
            )
        ]
    )
    print(f"✓ Updated endpoint: {ENDPOINT_30M}")
else:
    # Create new endpoint
    w.serving_endpoints.create(
        name=ENDPOINT_30M,
        config=EndpointCoreConfigInput(
            name=ENDPOINT_30M,
            served_entities=[
                ServedEntityInput(
                    entity_name=MODEL_30M,
                    entity_version=champion_version,
                    scale_to_zero_enabled=True,
                    workload_size="Medium"
                )
            ]
        )
    )
    print(f"✓ Created endpoint: {ENDPOINT_30M}")

# STEP 2: Wait for endpoint to be fully ready before configuring AI Gateway
print(f"\nWaiting for endpoint to be ready before configuring AI Gateway...")
max_wait = 600  # 10 minutes
wait_interval = 15  # 15 seconds
elapsed = 0

while elapsed < max_wait:
    try:
        endpoint_status = w.serving_endpoints.get(name=ENDPOINT_30M)
        config_update = str(endpoint_status.state.config_update) if endpoint_status.state and endpoint_status.state.config_update else "UNKNOWN"
        ready_status = str(endpoint_status.state.ready) if endpoint_status.state and endpoint_status.state.ready else "UNKNOWN"
        
        # Check if endpoint is fully ready (NOT_UPDATING and READY)
        if "NOT_UPDATING" in config_update and "READY" in ready_status:
            print(f"  ✓ Endpoint is READY (elapsed: {elapsed}s)")
            break
        
        print(f"  Status: {config_update} | Ready: {ready_status} | Elapsed: {elapsed}s")
        time.sleep(wait_interval)
        elapsed += wait_interval
    except Exception as wait_error:
        print(f"  Waiting... {elapsed}s")
        time.sleep(wait_interval)
        elapsed += wait_interval

if elapsed >= max_wait:
    print(f"  ⚠️  Timeout waiting for endpoint - skipping AI Gateway config")
    print(f"  You can configure it manually later in the UI")
else:
    # STEP 3: Configure AI Gateway with inference tables using REST API
    print(f"\nConfiguring AI Gateway inference tables...")

    # Get workspace URL and token
    workspace_url = w.config.host
    if not workspace_url.startswith('http'):
        workspace_url = f"https://{workspace_url}"

    # Get token from dbutils (works on serverless)
    try:
        token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().get()
    except:
        token = w.config.token

    # AI Gateway configuration payload
    ai_gateway_config = {
        "inference_table_config": {
            "catalog_name": CATALOG,
            "schema_name": SCHEMA,
            "table_name_prefix": INFERENCE_TABLE_PREFIX_30M,
            "enabled": True
        }
    }

    # PUT request to configure AI Gateway
    api_url = f"{workspace_url}/api/2.0/serving-endpoints/{ENDPOINT_30M}/ai-gateway"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.put(api_url, headers=headers, json=ai_gateway_config)
        
        if response.status_code in [200, 201]:
            print(f"✓ AI Gateway inference tables configured")
            print(f"  Table: {INFERENCE_TABLE_30M}_payload (auto-created on first request)")
        else:
            print(f"⚠️  AI Gateway configuration response: {response.status_code}")
            print(f"  Response: {response.text}")
    except Exception as e:
        print(f"⚠️  Could not configure AI Gateway: {str(e)}")
        print(f"  You can configure it manually in the UI: AI Gateway tab > Enable Inference tables")

# Get endpoint URL
workspace_url = w.config.host
if not workspace_url.startswith('http'):
    workspace_url = f"https://{workspace_url}"
endpoint_url = f"{workspace_url}/ml/endpoints/{ENDPOINT_30M}"

print(f"\nEndpoint URL: {endpoint_url}")
print(f"\n✅ Using AI Gateway (modern approach) for inference tables")

# COMMAND ----------

# DBTITLE 1,Wait for Endpoints to be Ready
# ------------------------
# Wait for Endpoints to be Ready
# ------------------------

import time

def wait_for_endpoint(endpoint_name, timeout_minutes=20):
    """Wait for endpoint to be ready"""
    print(f"Waiting for {endpoint_name} to be ready...")
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    try:
        while True:
            endpoint = w.serving_endpoints.get(name=endpoint_name)
            state = endpoint.state
            
            # Convert enum values to strings for comparison
            config_update_status = str(state.config_update) if state and state.config_update else "UNKNOWN"
            ready_status = str(state.ready) if state and state.ready else "UNKNOWN"
            
            # Check if endpoint is ready and not updating
            if "NOT_UPDATING" in config_update_status and "READY" in ready_status:
                print(f"✓ {endpoint_name} is READY")
                return True
            
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                print(f"✗ Timeout waiting for {endpoint_name}")
                return False
            
            print(f"  Status: {config_update_status} | Ready: {ready_status} | Elapsed: {int(elapsed)}s")
            time.sleep(30)
    except Exception as e:
        if "does not exist" in str(e).lower():
            print(f"✗ Endpoint '{endpoint_name}' does not exist")
            print(f"   Please run cells 8-9 to create the endpoints first")
            return False
        else:
            print(f"✗ Error checking endpoint: {str(e)}")
            raise

print("Waiting for endpoints to be ready (this may take 5-10 minutes)...\n")

ready_15m = wait_for_endpoint(ENDPOINT_15M)
ready_30m = wait_for_endpoint(ENDPOINT_30M)

if ready_15m and ready_30m:
    print("\n✓ Both endpoints are ready for inference!")
else:
    print("\n⚠️  Some endpoints are not ready yet. Check the status above.")

# COMMAND ----------

# DBTITLE 1,Test Endpoints with Sample Data
# ------------------------
# Test Endpoints with Sample Predictions
# ------------------------

# Get sample features from the feature table
sample_features = spark.table(xgb_features_tbl).limit(5).toPandas()

# Prepare input data (drop non-feature columns)
drop_cols = {"patient_id", "time", "day_idx"} | {f"y_tplus_{h}" for h in HORIZONS}
feature_cols = [c for c in sample_features.columns if c not in drop_cols]

# Create input records
input_data = sample_features[feature_cols].to_dict(orient='records')

print(f"Testing endpoints with {len(input_data)} sample records...")
print(f"Features: {len(feature_cols)} columns\n")

# Test 15-min endpoint
print(f"Testing {ENDPOINT_15M}...")
try:
    response_15m = w.serving_endpoints.query(
        name=ENDPOINT_15M,
        dataframe_records=input_data
    )
    predictions_15m = response_15m.predictions
    print(f"✓ 15-min predictions: {predictions_15m[:3]}")
except Exception as e:
    print(f"✗ Error: {str(e)}")

# Test 30-min endpoint
print(f"\nTesting {ENDPOINT_30M}...")
try:
    response_30m = w.serving_endpoints.query(
        name=ENDPOINT_30M,
        dataframe_records=input_data
    )
    predictions_30m = response_30m.predictions
    print(f"✓ 30-min predictions: {predictions_30m[:3]}")
except Exception as e:
    print(f"✗ Error: {str(e)}")

print("\n✓ Endpoint testing complete!")

# COMMAND ----------

# DBTITLE 1,Monitor Inference Tables
# ------------------------
# Monitor Inference Tables
# ------------------------

print("Checking inference table logging...\n")

# Check 15-min inference table
try:
    inf_15m = spark.table(INFERENCE_TABLE_15M)
    count_15m = inf_15m.count()
    print(f"✓ {INFERENCE_TABLE_15M}")
    print(f"   Total requests logged: {count_15m}")
    
    if count_15m > 0:
        # Show recent requests
        recent_15m = inf_15m.orderBy(F.col("timestamp").desc()).limit(5)
        print(f"\n   Recent requests:")
        display(recent_15m.select("timestamp", "request_id", "status_code"))
        
        # Show sample predictions
        print(f"\n   Sample predictions:")
        display(recent_15m.select("timestamp", "prediction"))
except Exception as e:
    print(f"⚠️  {INFERENCE_TABLE_15M} not available yet: {str(e)}")
    print(f"   Inference logging may take a few minutes to initialize")

print()

# Check 30-min inference table
try:
    inf_30m = spark.table(INFERENCE_TABLE_30M)
    count_30m = inf_30m.count()
    print(f"✓ {INFERENCE_TABLE_30M}")
    print(f"   Total requests logged: {count_30m}")
    
    if count_30m > 0:
        # Show recent requests
        recent_30m = inf_30m.orderBy(F.col("timestamp").desc()).limit(5)
        print(f"\n   Recent requests:")
        display(recent_30m.select("timestamp", "request_id", "status_code"))
        
        # Show sample predictions
        print(f"\n   Sample predictions:")
        display(recent_30m.select("timestamp", "prediction"))
except Exception as e:
    print(f"⚠️  {INFERENCE_TABLE_30M} not available yet: {str(e)}")
    print(f"   Inference logging may take a few minutes to initialize")

print("\n" + "="*70)
print("INFERENCE TABLE MONITORING SETUP COMPLETE")
print("="*70)
print("\nInference tables will automatically log:")
print("  • Request timestamp")
print("  • Request ID")
print("  • Input features")
print("  • Predictions")
print("  • Model version")
print("  • Status codes")
print("\nUse these tables for:")
print("  • Model performance monitoring")
print("  • Prediction drift detection")
print("  • Request volume tracking")
print("  • Error analysis")
