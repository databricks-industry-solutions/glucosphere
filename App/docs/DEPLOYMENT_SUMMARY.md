# ✅ CGM Schema Migration - Deployment Summary

**Date:** January 8, 2026  
**Status:** ✅ Deployed Locally - Ready for Testing

---

## 🎯 What Was Done

### 1. ✅ Migrated All Queries to CGM Schema
- Changed from `hls_glucosphere.medtech_ldp_1` → `hls_glucosphere.cgm`
- Updated all 4 SQL query functions in `src/api/databricksSQL.js`

### 2. ✅ Removed ALL Hardcoded Data
- No more fallback device models (Dexcom G6, FreeStyle Libre 2, etc.)
- No more fallback firmware versions (v2.1, v2.2, v2.3, v3.0, v3.1)
- No more fake device IDs (DX-47821, FL-92341, etc.)
- Everything is now **100% data-driven**

### 3. ✅ Dynamic Heatmap Axes
- **Firmware versions** (top axis): Automatically populated from database
- **Device models** (left axis): Automatically populated from database
- **Adapts automatically** when new firmware or devices are added

---

## 📊 Current CGM Data

### Device Count
- **999 devices** in `silver_patient_registry`

### Device Models (6 types)
- Alpha
- Beta
- Delta
- Epsilon
- Gamma
- Zeta

### Firmware Versions (3 versions)
- 3.14
- 4.0
- 4.1

### Heatmap
- **6 rows** (device models) × **3 columns** (firmware versions)
- Shows actual out-of-range glucose events per combination

---

## 🔄 How It Works Now

### Heatmap Behavior
1. Query runs: `SELECT device_model, firmware_version, SUM(glucose_out_of_range) FROM gold_patient_device_readings GROUP BY device_model, firmware_version`
2. Extract unique device models → populate Y-axis
3. Extract unique firmware versions → populate X-axis
4. Display heatmap with actual data

### If New Data Appears
- ✅ New firmware version (e.g., 4.2) → automatically adds new column
- ✅ New device model (e.g., Theta) → automatically adds new row
- ✅ No code changes needed

---

## 🚀 Services Running

- **Backend:** http://localhost:8000 ✅
- **Frontend:** http://localhost:5173 ✅

---

## 🧪 How to Test

### 1. Open the Dashboard
```
http://localhost:5173
```

### 2. Navigate to Device Support Dashboard
Click "Device Support" in the navigation

### 3. Verify Dynamic Data

#### Check Header Metrics
- **Devices Monitored:** Should show **999**
- Should NOT show 2,891 (old hardcoded value)

#### Check Anomaly Heatmap
- **Top axis (firmware versions):** Should show **3.14, 4.0, 4.1**
- **Left axis (device models):** Should show **Alpha, Beta, Delta, Epsilon, Gamma, Zeta**
- Should NOT show: v2.1, v2.2, v2.3, v3.0, v3.1 (old hardcoded values)
- Should NOT show: Dexcom G6, FreeStyle Libre 2, Guardian 3, Eversense

#### Check Device Detail Table
- Should show real device IDs from database
- Should show real patient IDs
- Should show actual glucose values
- Should NOT show: DX-47821, FL-92341, GD-18273 (old hardcoded values)

#### Check Pattern Alerts
- Should show real patterns from database
- Each alert should have device model, firmware, region, and out-of-range rate

---

## 📝 Console Logs to Look For

Open browser console (F12) and look for:

```
✅ Device count from database: 999
✅ Heatmap data from database: X rows
Device types: ["Alpha", "Beta", "Delta", "Epsilon", "Gamma", "Zeta"]
Firmware versions: ["3.14", "4.0", "4.1"]
✅ Out-of-range devices from database: X rows
✅ Device pattern alerts from database: X patterns
```

---

## 🔍 SQL Queries Being Used

### 1. Device Count
```sql
SELECT COUNT(DISTINCT device_id) 
FROM hls_glucosphere.cgm.silver_patient_registry
```

### 2. Heatmap Data
```sql
SELECT 
  device_model as device_type, 
  CAST(firmware_version AS STRING) as firmware_version,
  SUM(glucose_out_of_range) as out_of_range_events 
FROM hls_glucosphere.cgm.gold_patient_device_readings 
GROUP BY device_model, firmware_version
ORDER BY device_model, firmware_version
```

### 3. Out-of-Range Devices
```sql
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

### 4. Pattern Alerts
```sql
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

---

## 📂 Files Modified

| File | Changes |
|------|---------|
| `src/api/databricksSQL.js` | All 4 query functions updated to use CGM schema |
| `src/pages/DeviceSupportDashboard.jsx` | Removed all hardcoded fallback data |

---

## 🎉 Key Benefits

### 1. Fully Data-Driven
- No manual updates needed when new firmware versions appear
- No manual updates needed when new device models appear
- Heatmap automatically adapts to data

### 2. Accurate Representation
- Only shows what's actually in the database
- No confusing fake/sample data
- Clear empty states when no data available

### 3. Production Ready
- Works with any CGM schema data
- Scales automatically with data growth
- No hardcoded assumptions

---

## 🔧 Troubleshooting

### If Heatmap Shows Wrong Versions
1. Check what's in the database:
```bash
curl -X POST http://localhost:8000/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT DISTINCT firmware_version FROM hls_glucosphere.cgm.gold_patient_device_readings"}'
```

### If Device Count is Wrong
1. Check the actual count:
```bash
curl -X POST http://localhost:8000/api/sql/query \
  -H "Content-Type: application/json" \
  -d '{"query":"SELECT COUNT(DISTINCT device_id) FROM hls_glucosphere.cgm.silver_patient_registry"}'
```

### If No Data Appears
1. Check browser console for errors
2. Check backend logs for SQL errors
3. Verify CGM schema has data

---

## 📊 Expected vs Actual

| Metric | Old (medtech_ldp_1) | New (cgm) |
|--------|---------------------|-----------|
| Device Count | 26,190 | 999 |
| Device Models | Hardcoded (4) | Dynamic (6) |
| Firmware Versions | Hardcoded (5) | Dynamic (3) |
| Heatmap Size | 4×5 = 20 cells | 6×3 = 18 cells |
| Data Source | Pre-aggregated table | On-the-fly aggregation |

---

**Status:** ✅ **Ready for Testing**

Open http://localhost:5173 and check out the Device Support Dashboard with real CGM data!
