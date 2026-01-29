# Landing Page Metrics - CGM Schema Analysis

**Date:** January 8, 2026  
**Branch:** `feature/landing-page-metrics`  
**Goal:** Determine which CGM schema tables/data can populate the 4 main landing page metrics

---

## Current Landing Page Metrics (To Replace)

1. **Active Patients** - Currently hardcoded/animated
2. **Devices Online** - Currently hardcoded/animated  
3. **High Risk Alerts** - Currently hardcoded/animated
4. **Average Response Time** - Currently hardcoded/animated

---

## CGM Schema Tables Analyzed

### Tables Examined:
1. ✅ `silver_patient_registry` - Patient and device registration
2. ✅ `silver_patient_readings` - Patient glucose readings with incidents
3. ✅ `silver_device_telemetry_stream` - Device online/offline periods
4. ✅ `patient_readings` - Simpler patient readings (no incidents)
5. ✅ `patient_device` - Patient-device mapping
6. ✅ `gold_patient_device_readings` - Combined patient + device data
7. ✅ `diabetes_summary` - Patient record counts
8. ✅ `diabetes_data` - Raw diabetes data

---

## Table Structures

### silver_patient_registry
```
patient_id         string
device_id          string
region             string
patient_diagnosis  string
activation_date    timestamp
birth_year         bigint
device_model       string
```
- **Total patients:** 999
- **Use case:** Patient counts, demographics

### silver_patient_readings
```
patient_id                string
time                      timestamp
incident_type             string
glucose_out_of_range      int (0/1)
glucose                   double
steps, basal_rate, etc.   various
```
- **Data range:** 2026-01-05 to 2026-01-11 (7 days)
- **Incidents tracked:** "calibration_bias" (10,764 occurrences)
- **Use case:** Active patients, high-risk alerts

### silver_device_telemetry_stream
```
patient_id           string
device_id            string
device_model         string
start_time           timestamp
end_time             timestamp
firmware_version     double
```
- **Use case:** Device online/offline status, active device count

### diabetes_summary
```
patient_id      string
record_count    bigint
loaded_at       timestamp
```
- **Use case:** Data quality metrics

---

## Metric Mapping Analysis

### 1. ✅ Active Patients

**Definition:** Patients with glucose readings in the last 24 hours

**Available Data:** ✅ YES
- Table: `silver_patient_readings`
- Query:
```sql
SELECT COUNT(DISTINCT patient_id) as active_patients
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE time >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR
```

**Result:** **999 active patients** (last 24h)

**Recommendation:** ✅ Use this - real data available

---

### 2. ✅ Devices Online

**Definition:** Devices currently transmitting or recently active

**Available Data:** ✅ YES (with caveats)
- Table: `silver_device_telemetry_stream`
- Query:
```sql
SELECT COUNT(DISTINCT device_id) as devices_online
FROM hls_glucosphere.cgm.silver_device_telemetry_stream
WHERE end_time >= CURRENT_TIMESTAMP - INTERVAL 1 DAY
   OR end_time IS NULL  -- NULL end_time = still active
```

**Alternative (simpler):**
```sql
-- Count devices with recent readings
SELECT COUNT(DISTINCT pr.device_id) as devices_online
FROM hls_glucosphere.cgm.silver_patient_readings pr
INNER JOIN hls_glucosphere.cgm.silver_patient_registry reg
  ON pr.patient_id = reg.patient_id
WHERE pr.time >= CURRENT_TIMESTAMP - INTERVAL 1 HOUR
```

**Recommendation:** ✅ Use telemetry stream for "truly online" or recent readings for "active devices"

---

### 3. ⚠️ High Risk Alerts

**Definition:** Patients with critical glucose levels or incidents

**Available Data:** ⚠️ PARTIAL
- Table: `silver_patient_readings`
- Fields:
  - `glucose_out_of_range` = 1 (out of normal range)
  - `incident_type` = "calibration_bias" (only type found)
  
**Problem:** 
- Query for last 24h returned **0 high-risk alerts**
- Data range is 2026-01-05 to 2026-01-11 (past dates)
- `CURRENT_TIMESTAMP - INTERVAL 24 HOUR` = ~2026-01-08 20:00
- Latest data = 2026-01-11 23:55
- So last 24h query doesn't match because data is in the "future"

**Options:**

**Option A: Use Most Recent Day in Data**
```sql
SELECT COUNT(*) as high_risk_alerts
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE glucose_out_of_range = 1
  AND time >= (SELECT MAX(time) - INTERVAL 24 HOUR FROM hls_glucosphere.cgm.silver_patient_readings)
```

**Option B: Count All Out-of-Range Events**
```sql
SELECT COUNT(DISTINCT patient_id) as patients_with_alerts
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE glucose_out_of_range = 1
```

**Option C: Count Incidents**
```sql
SELECT COUNT(*) as incidents
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE incident_type IS NOT NULL
```

**Total out-of-range readings:** 85,000+ across all time
**Calibration bias incidents:** 10,764

**Recommendation:** ⚠️ Use Option A (recent data window) or Option B (patients with alerts)

---

### 4. ❌ Average Response Time

**Definition:** Time to respond to high-risk alerts

**Available Data:** ❌ NO
- No "alert acknowledged" timestamp
- No "response time" field
- No "action taken" timestamp
- No workflow/ticketing data

**What We Have:**
- Incident occurrences (timestamp when incident happened)
- No data on when/if anyone responded

**Possible Alternatives:**

**Alternative A: Average Time Between Readings**
```sql
-- How frequently are readings being taken?
SELECT AVG(reading_interval_minutes) as avg_reading_frequency
FROM (
  SELECT 
    patient_id,
    TIMESTAMPDIFF(MINUTE, 
      LAG(time) OVER (PARTITION BY patient_id ORDER BY time),
      time
    ) as reading_interval_minutes
  FROM hls_glucosphere.cgm.silver_patient_readings
)
WHERE reading_interval_minutes IS NOT NULL
```

**Alternative B: Data Latency**
```sql
-- Time between data generation and load
-- (if we had load timestamps)
```

**Alternative C: Incident Detection Lag**
```sql
-- Time from out-of-range reading to incident flagging
-- (requires both timestamps - may not be separate)
```

**Recommendation:** ❌ Cannot accurately calculate "response time" - suggest different metric or keep as placeholder

---

## Final Recommendations

| Metric | Status | Recommended Table | Recommended Query | Notes |
|--------|--------|-------------------|-------------------|-------|
| **Active Patients** | ✅ Available | `silver_patient_readings` | Count distinct patients with readings in recent window | Use "last day in dataset" since data is backdated |
| **Devices Online** | ✅ Available | `silver_device_telemetry_stream` or `silver_patient_readings` | Count devices with end_time=NULL or recent readings | Use telemetry for "online", readings for "active" |
| **High Risk Alerts** | ⚠️ Partial | `silver_patient_readings` | Count patients with glucose_out_of_range=1 or incident_type!=NULL | Data exists but need to use relative time window |
| **Average Response Time** | ❌ Not Available | N/A | Cannot calculate without response/action timestamps | **Suggest alternative metric** |

---

## Alternative Metrics for "Response Time"

Since we don't have response time data, here are alternatives:

### Option 1: Average Reading Frequency
- **What:** How often patients transmit readings
- **Value:** "Every 5 minutes" or "12 readings/hour"
- **Table:** `silver_patient_readings`

### Option 2: Data Completeness Rate
- **What:** % of patients with readings in last hour
- **Value:** "98.5%" 
- **Table:** `silver_patient_readings` + `silver_patient_registry`

### Option 3: System Uptime
- **What:** % of devices currently active
- **Value:** "99.2% uptime"
- **Table:** `silver_device_telemetry_stream`

### Option 4: Incident Rate
- **What:** Incidents per 1000 readings
- **Value:** "2.3 incidents/1000 readings"
- **Table:** `silver_patient_readings`

**Recommendation:** Use **Option 1 (Average Reading Frequency)** or **Option 3 (System Uptime)**

---

## Proposed Updated Metrics

### Updated Landing Page - 4 Metrics:

1. **Active Patients** → ✅ Real data from CGM
   - Count distinct patients with readings in last 24h (of available data)
   - Current result: **999 patients**

2. **Devices Online** → ✅ Real data from CGM
   - Count devices with NULL end_time or recent activity
   - Current result: **999 devices**

3. **High Risk Alerts** → ⚠️ Real data (with adjustment)
   - Count patients with out-of-range readings in recent window
   - Or: Count total out-of-range events
   - Need to use relative time window due to backdated data

4. **Average Reading Frequency** → ✅ NEW METRIC (replaces response time)
   - Calculate average time between readings
   - Display as "1 reading every X minutes"
   - Alternative: Show "System Uptime: XX%"

---

## Implementation Plan

### Step 1: Create Query Functions
```javascript
// In new file: src/pages/GlucoseLanding/queries.js

export async function getActivePatients() {
  // Count patients with readings in last day of available data
}

export async function getDevicesOnline() {
  // Count devices from telemetry stream
}

export async function getHighRiskAlerts() {
  // Count patients with out-of-range readings
}

export async function getAverageReadingFrequency() {
  // Calculate avg minutes between readings
}
```

### Step 2: Update Landing Page
- Replace animated/fake data with real queries
- Update metric labels if needed
- Add loading states
- Add fallbacks for errors

### Step 3: Update Metrics Explained Page
- Document new metrics
- Explain calculations
- Add SQL queries

---

## Sample Queries to Implement

### Active Patients
```sql
SELECT COUNT(DISTINCT patient_id) as active_patients
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE time >= (SELECT MAX(time) - INTERVAL 24 HOUR 
               FROM hls_glucosphere.cgm.silver_patient_readings)
```

### Devices Online
```sql
SELECT COUNT(DISTINCT device_id) as devices_online
FROM hls_glucosphere.cgm.silver_device_telemetry_stream
WHERE end_time IS NULL
   OR end_time >= (SELECT MAX(end_time) - INTERVAL 1 DAY
                   FROM hls_glucosphere.cgm.silver_device_telemetry_stream)
```

### High Risk Alerts
```sql
SELECT COUNT(DISTINCT patient_id) as high_risk_patients
FROM hls_glucosphere.cgm.silver_patient_readings
WHERE glucose_out_of_range = 1
  AND time >= (SELECT MAX(time) - INTERVAL 24 HOUR
               FROM hls_glucosphere.cgm.silver_patient_readings)
```

### Average Reading Frequency (NEW)
```sql
WITH reading_intervals AS (
  SELECT 
    TIMESTAMPDIFF(MINUTE,
      LAG(time) OVER (PARTITION BY patient_id ORDER BY time),
      time
    ) as minutes_between_readings
  FROM hls_glucosphere.cgm.silver_patient_readings
)
SELECT 
  ROUND(AVG(minutes_between_readings), 1) as avg_minutes_between_readings,
  ROUND(60.0 / AVG(minutes_between_readings), 1) as readings_per_hour
FROM reading_intervals
WHERE minutes_between_readings IS NOT NULL
  AND minutes_between_readings < 60  -- Filter out gaps (e.g., overnight)
```

---

## Data Quality Notes

### Time Range Issue
- Data spans: 2026-01-05 to 2026-01-11
- Queries using `CURRENT_TIMESTAMP` may return 0 results
- **Solution:** Use `MAX(time)` to find latest data point, then calculate relative windows

### Example:
```sql
-- Instead of:
WHERE time >= CURRENT_TIMESTAMP - INTERVAL 24 HOUR

-- Use:
WHERE time >= (SELECT MAX(time) - INTERVAL 24 HOUR FROM table_name)
```

---

## Next Steps

1. ✅ Analysis complete
2. Create query functions for landing page
3. Update GlucoseLandingDashboard with real data
4. Replace "Average Response Time" with "Average Reading Frequency"
5. Update Metrics Explained page
6. Test with real data
7. Commit and push to feature branch

---

**Status:** ✅ Analysis complete - 3 of 4 metrics have available data, 1 metric needs replacement
