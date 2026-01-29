# CGM Genie Schema Update Instructions

## Issue
The CGM Genie space (`01f0e4fa62aa1a598c2801bc934dbc5d`) is configured to use the old `medtech_ldp_1` schema, but the app now uses `cgm.gold_patient_device_readings`.

## Current Behavior
- Queries execute successfully
- But return "no results" because the old tables are empty or non-existent

## Solution Options

### Option 1: Create New Genie Space (Recommended)
Create a new Genie space through the Databricks UI with the correct schema:

1. Go to Databricks workspace: https://fe-vm-industry-solutions-buildathon.cloud.databricks.com
2. Navigate to **Genie** from the left sidebar
3. Click **"Create Genie Space"**
4. Configure:
   - **Name:** "CGM Analytics Genie"
   - **Description:** "Natural language queries for CGM patient and device data"
   - **Tables:** Select `hls_glucosphere.cgm.gold_patient_device_readings`
   - **SQL Warehouse:** Select an active warehouse

5. Add instructions in the space configuration:
```
Use hls_glucosphere.cgm.gold_patient_device_readings for all queries.

Key columns:
- patient_id, device_id, device_model, time
- glucose (mg/dL), glucose_out_of_range (1=out of range, 0=in range)
- region (NA, EMEA, APAC)
- patient_diagnosis, activation_date, birth_year
- firmware_version, incident_type
- basal_rate, bolus_volume_delivered, carb_input
- steps, heart_rate, calories

Definitions:
- Hypoglycemia: glucose < 70
- Hyperglycemia: glucose > 180
- Time in Range: glucose BETWEEN 70 AND 180
```

6. Get the new Space ID from the URL
7. Update `databricks/app.py` line 82 with the new space ID:
```python
space_id = 'YOUR_NEW_SPACE_ID'
```

### Option 2: Manual UI Update (Alternative)
1. Go to the existing Genie space in Databricks UI
2. Click **"Configure"** or **"Settings"**
3. Remove old tables from data sources
4. Add `hls_glucosphere.cgm.gold_patient_device_readings`
5. Save and wait for reindexing (5-10 minutes)

## Testing
After updating, test with these queries:
- "How many patients are in the system?"
- "What is the average glucose level?"
- "Show patients with hypoglycemia in the last 24 hours"

All queries should now return actual data instead of empty results.

## Update App Configuration
Once you have a new Space ID, update:

**File:** `databricks/app.py`  
**Line:** ~82  
**Change:**
```python
# OLD
space_id = '01f0e4fa62aa1a598c2801bc934dbc5d'

# NEW
space_id = 'YOUR_NEW_SPACE_ID'
```

Then redeploy:
```bash
npm run build
python3 scripts/deploy.py buildathon
```
