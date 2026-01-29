# ✅ CGM Schema Migration Complete

**Date:** January 8, 2026  
**Status:** ✅ Deployed Locally - Ready for Testing

---

## What Was Changed

All SQL queries in `src/api/databricksSQL.js` have been updated to use the **CGM schema** (`hls_glucosphere.cgm`) instead of the previous `medtech_ldp_1` schema.

---

## Updated Functions

### 1. ✅ `getDistinctDeviceCount()`

**Change:** Simple schema swap

```sql
-- OLD
FROM hls_glucosphere.medtech_ldp_1.silver_patient_registry

-- NEW
FROM hls_glucosphere.cgm.silver_patient_registry
```

**Result:** ✅ Returns **999 devices** (vs 26,190 in old schema)

---

### 2. ✅ `getDeviceHeatmapData()`

**Change:** Built aggregation from gold_patient_device_readings

```sql
-- NEW Query
SELECT 
  device_model as device_type, 
  CAST(firmware_version AS STRING) as firmware_version,
  SUM(glucose_out_of_range) as out_of_range_events 
FROM hls_glucosphere.cgm.gold_patient_device_readings 
GROUP BY device_model, firmware_version
ORDER BY device_model, firmware_version
```

**Changes:**
- ⚠️ No pre-aggregated table - aggregating on-the-fly
- ✅ Column renames: `device_type` → `device_model`, `out_of_range_events` → `glucose_out_of_range`
- ✅ Cast firmware_version to STRING for consistency

**Result:** ✅ Returns heatmap data successfully

---

### 3. ✅ `getOutOfRangeDevices()`

**Change:** Switched to gold_patient_device_readings (single table, no JOIN needed)

```sql
-- NEW Query
SELECT 
  device_id,
  TIMESTAMPDIFF(MINUTE, time, (SELECT MAX(time) FROM hls_glucosphere.cgm.gold_patient_device_readings)) as minutes_since_last_reading,
  patient_id,
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  glucose as glucose_value
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE glucose_out_of_range = 1
ORDER BY time DESC
LIMIT 50
```

**Changes:**
- ✅ Single table instead of JOIN (data already combined in gold layer)
- ✅ Column renames:
  - `reading_timestamp` → `time`
  - `glucose_value` → `glucose`
  - `device_type` → `device_model`
- ✅ Filter change: `out_of_range_flag = true` → `glucose_out_of_range = 1`

**Result:** ✅ Returns out-of-range devices successfully

---

### 4. ✅ `getDevicePatternAlerts()`

**Change:** Built complex aggregation from gold_patient_device_readings

```sql
-- NEW Query
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
HAVING SUM(glucose_out_of_range) > 10
ORDER BY avg_oor_rate_pct DESC
LIMIT 4
```

**Changes:**
- ⚠️ No pre-aggregated table - aggregating on-the-fly
- ✅ Threshold lowered: 1000 → 10 (due to smaller CGM dataset)
- ✅ Calculate percentage rate on-the-fly using CASE statement
- ✅ All column renames applied

**Result:** ✅ Returns pattern alerts successfully

---

## Test Results

All queries tested and verified working:

| Function | Test Result | Data Returned |
|----------|-------------|---------------|
| `getDistinctDeviceCount()` | ✅ Pass | 999 devices |
| `getDeviceHeatmapData()` | ✅ Pass | Multiple device/firmware combinations |
| `getOutOfRangeDevices()` | ✅ Pass | Out-of-range glucose readings |
| `getDevicePatternAlerts()` | ✅ Pass | Pattern alerts by region/device |

---

## Local Deployment Status

✅ **Backend:** Running on http://localhost:8000  
✅ **Frontend:** Running on http://localhost:5173  
✅ **All Queries:** Tested and working

---

## Key Differences from Old Schema

### Data Volume
- **Old (medtech_ldp_1):** 26,190 device records
- **New (cgm):** 999 device records
- **Impact:** Dashboards will show less data (expected for CGM-specific dataset)

### Table Structure
1. **silver_patient_registry:** Nearly identical (just column name changes)
2. **silver_device_telemetry_stream:** Replaced with **gold_patient_device_readings** (better data model)
3. **gold_device_event_rates:** No equivalent - now aggregated on-the-fly

### Performance Considerations
- ⚠️ Queries 2 and 4 now aggregate raw data instead of reading pre-computed aggregations
- ✅ Dataset is smaller (999 vs 26K), so performance impact is minimal
- 💡 For production with larger datasets, consider creating materialized views

---

## Column Mapping Reference

| Old Column Name | New Column Name | Notes |
|----------------|-----------------|-------|
| `device_type` | `device_model` | Renamed in CGM schema |
| `reading_timestamp` | `time` | Renamed in CGM schema |
| `glucose_value` | `glucose` | Renamed in CGM schema |
| `out_of_range_flag` (boolean) | `glucose_out_of_range` (int 0/1) | Type changed |
| `out_of_range_events` | `glucose_out_of_range` (sum) | Now aggregated from flags |
| `out_of_range_event_rate_pct` | Calculated via CASE | Now computed on-the-fly |

---

## What to Test in the UI

### Device Support Dashboard
1. **Header Metric:** "Devices Monitored" should show **999**
2. **Anomaly Heatmap:** Should display device models with out-of-range counts
3. **Device Detail Table:** Should show out-of-range devices with glucose readings
4. **Pattern Alerts:** Should show top 4 patterns with elevated out-of-range rates

### Expected Behavior
- ✅ All data should load without errors
- ✅ Console logs should show "CGM" in query strings
- ✅ Metrics should reflect the smaller CGM dataset (999 devices vs 26K)

---

## Next Steps

1. ✅ **Code Updated:** All queries migrated to CGM schema
2. ✅ **Queries Tested:** All 4 functions verified working
3. ✅ **Services Running:** Backend and frontend deployed locally
4. 🔍 **Manual Testing:** Review the UI at http://localhost:5173
5. 📊 **Verify Dashboards:** Check Device Support Dashboard displays correctly

---

## Files Modified

- ✅ `src/api/databricksSQL.js` - All 4 query functions updated

---

## Rollback Instructions (if needed)

If you need to revert to the old schema:

```bash
git diff src/api/databricksSQL.js
git checkout src/api/databricksSQL.js
```

Or manually change:
- `hls_glucosphere.cgm` → `hls_glucosphere.medtech_ldp_1`
- `device_model` → `device_type`
- `time` → `reading_timestamp`
- `glucose` → `glucose_value`
- `glucose_out_of_range` → `out_of_range_flag`

---

## Additional Notes

### Threshold Adjustment
- **Pattern Alerts** threshold reduced from 1000 to 10 due to smaller dataset
- If this returns too many results, increase the threshold in `getDevicePatternAlerts()`

### Future Optimizations
For production with larger CGM datasets:
1. Create materialized views for aggregations
2. Add date range filters (e.g., last 30 days)
3. Consider scheduled jobs to pre-compute metrics
4. Monitor query performance and add indexes if needed

---

**Status:** ✅ **Migration Complete - Ready for UI Testing**

Visit http://localhost:5173 and navigate to the Device Support Dashboard to see the CGM data in action!
