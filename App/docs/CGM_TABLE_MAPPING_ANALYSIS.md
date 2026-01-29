# CGM Schema Table Mapping Analysis

**Date:** January 8, 2026  
**Schema:** `hls_glucosphere.cgm`  
**Current Schema:** `hls_glucosphere.medtech_ldp_1`

---

## Executive Summary

The CGM schema contains **34 tables** (after filtering out GEN_ and SUDO_ prefixes). Analysis shows:

✅ **2 exact table name matches** (with schema differences)  
⚠️ **1 table requires alternative mapping** (no direct equivalent)  
💡 **1 superior alternative table** recommended for better data

---

## Current Tables vs CGM Schema Mapping

### 1. ✅ **silver_patient_registry** → **silver_patient_registry** (EXACT MATCH)

**Current Table:** `hls_glucosphere.medtech_ldp_1.silver_patient_registry`  
**CGM Table:** `hls_glucosphere.cgm.silver_patient_registry`  
**Match Status:** ✅ Direct replacement available

#### Column Comparison:

| Current (medtech_ldp_1) | CGM Schema | Status | Notes |
|-------------------------|------------|--------|-------|
| `device_id` | `device_id` | ✅ Match | Same |
| `patient_id` | `patient_id` | ✅ Match | Same |
| `device_type` | `device_model` | ⚠️ Different Name | **RENAME REQUIRED** |
| - | `region` | ➕ New | Available in CGM |
| - | `patient_diagnosis` | ➕ New | Available in CGM |
| - | `activation_date` | ➕ New | Available in CGM |
| - | `birth_year` | ➕ New | Available in CGM |

**Current Usage:**
- Query: `SELECT COUNT(DISTINCT device_id) FROM ...`
- Function: `getDistinctDeviceCount()`

**Migration Impact:** 
- ✅ Direct table swap
- ⚠️ Update column reference: `device_type` → `device_model`

**Data Verification:**
- CGM table contains **999 device records** (vs 26,190 in medtech_ldp_1)
- Smaller dataset - ensure this is expected for your use case

---

### 2. ⚠️ **silver_device_telemetry_stream** → **gold_patient_device_readings** (DIFFERENT STRUCTURE)

**Current Table:** `hls_glucosphere.medtech_ldp_1.silver_device_telemetry_stream`  
**CGM Alternative:** `hls_glucosphere.cgm.gold_patient_device_readings`  
**Match Status:** ⚠️ Different structure - use Gold table instead

#### Why Not silver_device_telemetry_stream?

The CGM `silver_device_telemetry_stream` has completely different columns:
- Only contains: `patient_id, device_id, device_model, start_time, end_time, firmware_version`
- **Missing:** glucose readings, out_of_range flags, actual telemetry data
- Appears to track device **usage periods**, not readings

#### Recommended Alternative: gold_patient_device_readings

**CGM Table Columns:**
```
patient_id (string)
time (timestamp)                    ← replaces reading_timestamp
region (string)
patient_diagnosis (string)
activation_date (timestamp)
birth_year (bigint)
device_id (string)
device_model (string)               ← replaces device_type
firmware_version (double)
glucose (double)                    ← replaces glucose_value
glucose_out_of_range (int)          ← replaces out_of_range_flag (0/1 instead of boolean)
incident_type (string)              ← NEW: incident classification
steps (double)
basal_rate (double)
bolus_volume_delivered (double)
carb_input (double)
heart_rate (double)
calories (double)
basal_present (int)
bolus_event (int)
carb_event (int)
```

**Current Query Requirements:**
```sql
SELECT 
  device_id,
  reading_timestamp,
  firmware_version,
  glucose_value,
  out_of_range_flag,
  patient_id,
  device_type
```

**CGM Equivalent Columns:**
```sql
SELECT 
  device_id,               ✅ Same
  time,                    ✅ replaces reading_timestamp
  firmware_version,        ✅ Same
  glucose,                 ✅ replaces glucose_value
  glucose_out_of_range,    ✅ replaces out_of_range_flag (now 0/1 integer)
  patient_id,              ✅ Same
  device_model             ⚠️ replaces device_type
```

**Migration Impact:**
- ⚠️ Table name change: silver → gold (different medallion layer)
- ⚠️ Column renames:
  - `reading_timestamp` → `time`
  - `glucose_value` → `glucose`
  - `out_of_range_flag` → `glucose_out_of_range`
  - `device_type` → `device_model`
- ⚠️ Data type change: `out_of_range_flag` from boolean → integer (0/1)
- ✅ Richer data available (incident_type, patient diagnosis, etc.)

**Functions Affected:**
- `getOutOfRangeDevices()` - needs query rewrite

---

### 3. ❌ **gold_device_event_rates** → **No Direct Equivalent - Build Aggregation**

**Current Table:** `hls_glucosphere.medtech_ldp_1.gold_device_event_rates`  
**CGM Alternative:** None - must aggregate from `gold_patient_device_readings`  
**Match Status:** ❌ No pre-aggregated table available

#### Current Table Structure (medtech_ldp_1):
```
device_type (string)
firmware_version (string)
region (string)
out_of_range_events (int)          ← aggregated count
total_events (int)                 ← aggregated count
out_of_range_event_rate_pct (double)
date (date)
```

#### CGM Solution: Aggregate from gold_patient_device_readings

**Current Usage 1: Heatmap Data**
```sql
-- Current Query
SELECT device_type, firmware_version, SUM(out_of_range_events) as out_of_range_events 
FROM gold_device_event_rates 
GROUP BY device_type, firmware_version
```

**CGM Equivalent:**
```sql
-- Build aggregation on-the-fly
SELECT 
  device_model as device_type, 
  CAST(firmware_version AS STRING) as firmware_version,
  SUM(glucose_out_of_range) as out_of_range_events 
FROM hls_glucosphere.cgm.gold_patient_device_readings 
GROUP BY device_model, firmware_version
ORDER BY device_model, firmware_version
```

**Current Usage 2: Pattern Alerts**
```sql
-- Current Query
SELECT 
  device_type, firmware_version, region,
  SUM(out_of_range_events) as total_oor_events,
  SUM(total_events) as total_events,
  ROUND(AVG(out_of_range_event_rate_pct), 2) as avg_oor_rate_pct,
  COUNT(DISTINCT date) as days_tracked
FROM gold_device_event_rates
GROUP BY device_type, firmware_version, region
HAVING SUM(out_of_range_events) > 1000
```

**CGM Equivalent:**
```sql
-- Build aggregation from raw data
SELECT 
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  region,
  SUM(glucose_out_of_range) as total_oor_events,
  COUNT(*) as total_events,
  ROUND(AVG(CASE WHEN glucose_out_of_range = 1 THEN 100.0 ELSE 0.0 END), 2) as avg_oor_rate_pct,
  COUNT(DISTINCT DATE(time)) as days_tracked
FROM hls_glucosphere.cgm.gold_patient_device_readings
GROUP BY device_model, firmware_version, region
HAVING SUM(glucose_out_of_range) > 1000
ORDER BY avg_oor_rate_pct DESC
LIMIT 4
```

**Migration Impact:**
- ❌ No pre-aggregated table - queries will be more expensive
- ⚠️ Performance may be slower (aggregating on-the-fly vs reading pre-computed)
- ⚠️ Query logic changes from simple SELECT to GROUP BY with calculations
- 💡 **Recommendation:** Consider creating a materialized view or scheduled job to pre-aggregate

**Functions Affected:**
- `getDeviceHeatmapData()` - needs query rewrite
- `getDevicePatternAlerts()` - needs query rewrite

---

## Summary Table

| Current Table (medtech_ldp_1) | CGM Schema | Match Type | Migration Complexity |
|-------------------------------|------------|------------|---------------------|
| `silver_patient_registry` | `silver_patient_registry` | ✅ Exact Match | 🟢 Low (column rename only) |
| `silver_device_telemetry_stream` | `gold_patient_device_readings` | ⚠️ Alternative | 🟡 Medium (table + column changes) |
| `gold_device_event_rates` | *Create aggregation* | ❌ Build from gold | 🔴 High (query rewrite + performance) |

---

## Recommended Migration Path

### Phase 1: Low Risk (silver_patient_registry)
✅ Simple column rename: `device_type` → `device_model`

**Files to Update:**
- `src/api/databricksSQL.js` → `getDistinctDeviceCount()`

**Query Changes:**
```javascript
// OLD
const query = 'SELECT COUNT(DISTINCT device_id) FROM hls_glucosphere.medtech_ldp_1.silver_patient_registry';

// NEW
const query = 'SELECT COUNT(DISTINCT device_id) FROM hls_glucosphere.cgm.silver_patient_registry';
```

---

### Phase 2: Medium Risk (silver_device_telemetry_stream → gold_patient_device_readings)
⚠️ Multiple column renames + table change

**Files to Update:**
- `src/api/databricksSQL.js` → `getOutOfRangeDevices()`

**Query Changes:**
```javascript
// OLD columns
reading_timestamp → time
glucose_value → glucose
out_of_range_flag → glucose_out_of_range
device_type → device_model

// OLD table
hls_glucosphere.medtech_ldp_1.silver_device_telemetry_stream

// NEW table
hls_glucosphere.cgm.gold_patient_device_readings
```

**WHERE clause change:**
```sql
-- OLD
WHERE ds.out_of_range_flag = true

-- NEW
WHERE ds.glucose_out_of_range = 1
```

---

### Phase 3: High Risk (gold_device_event_rates → aggregated queries)
🔴 Major query rewrites + potential performance impact

**Files to Update:**
- `src/api/databricksSQL.js` → `getDeviceHeatmapData()`
- `src/api/databricksSQL.js` → `getDevicePatternAlerts()`

**Performance Considerations:**
- Pre-aggregated table had ~daily aggregations
- New approach aggregates millions of raw readings on-the-fly
- **Recommendation:** Add time filters (e.g., last 30 days) to improve performance
- **Long-term:** Create a scheduled job to materialize aggregations

---

## Additional CGM Tables of Interest

While not currently used, these CGM tables may be valuable:

### `patient_readings`
- Simpler than gold_patient_device_readings
- Contains: patient_id, time, glucose, activity metrics
- **Use case:** Patient-focused dashboards without device details

### `fleet_forecast_incident`
- Contains glucose predictions (15m, 30m ahead)
- Columns: pred_15m, pred_30m, delta_15m, delta_30m
- **Use case:** Predictive alerting for upcoming incidents

### `pseudo_incident_7d_labeled`
- Labeled incident data for ML training
- **Use case:** Analytics on incident patterns

---

## Data Volume Comparison

| Metric | medtech_ldp_1 | cgm | Change |
|--------|---------------|-----|--------|
| Patient/Device Records | 26,190 | 999 | -96.2% |

⚠️ **Important:** The CGM schema has significantly less data. Verify this aligns with your expected dataset.

---

## Next Steps

1. ✅ **Review this analysis** - Confirm table mappings make sense
2. 🔍 **Verify data completeness** - Ensure CGM tables have expected data
3. 🧪 **Test queries individually** - Run new queries in SQL editor first
4. 📝 **Update code** - Modify `src/api/databricksSQL.js` with new queries
5. 🧹 **Update column mappings** - Change all `device_type` → `device_model`
6. 🎯 **Test UI** - Verify dashboards display correctly
7. 📊 **Monitor performance** - Check query latency for aggregated queries

---

## Questions to Resolve

1. **Data Volume:** Why does CGM have only 999 records vs 26K in medtech_ldp_1?
2. **Aggregation Strategy:** Should we create a materialized view for device event rates?
3. **Time Range:** Should we limit aggregations to recent data (e.g., last 30-90 days)?
4. **Incident Data:** Should we leverage the `incident_type` field in gold_patient_device_readings?

---

**Status:** ✅ Analysis Complete - Ready for Review
