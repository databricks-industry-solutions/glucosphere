// Databricks DBSQL MCP Server API Client
// Based on: https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp
//
// All SQL queries in this file fetch catalog/schema from getConfig() (which calls
// the Flask /api/config endpoint sourced from app.yaml env vars). NEVER hardcode
// catalog/schema names inline — keeps the app portable across workspaces.

import { getConfig } from './config';

/**
 * Execute a SQL query via Databricks DBSQL MCP server
 * @param {string} query - SQL query to execute
 * @returns {Promise<any>} Query results
 */
export async function executeSQLQuery(query) {
  const endpoint_url = '/api/sql/query';
  
  console.log('🔍 SQL Query Request:');
  console.log('Endpoint:', endpoint_url);
  console.log('Query:', query);
  
  try {
    const response = await fetch(endpoint_url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query })
    });

    console.log('📥 SQL Response Status:', response.status, response.statusText);
    
    if (!response.ok) {
      let errorDetails;
      try {
        errorDetails = await response.json();
        console.error('❌ SQL Error Response:', errorDetails);
      } catch (e) {
        errorDetails = await response.text();
        console.error('❌ SQL Error Text:', errorDetails);
      }
      
      throw new Error(`SQL query failed: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    console.log('✅ SQL Response Data:', data);
    return data;
  } catch (error) {
    console.error('❌ Error executing SQL query:', error);
    console.error('Error type:', error.name);
    console.error('Error message:', error.message);
    throw error;
  }
}

/**
 * Get count of distinct devices from patient registry
 * @returns {Promise<number>} Count of distinct devices
 */
export async function getDistinctDeviceCount() {
  const { catalog, schema } = await getConfig();
  const query = `SELECT COUNT(DISTINCT device_id) as device_count FROM ${catalog}.${schema}.silver_patient_registry`;

  try {
    const result = await executeSQLQuery(query);
    
    // Parse the DBSQL MCP server response
    // Response format from: https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      // Extract the value from data_array
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        const firstRow = structuredContent.result.data_array[0];
        if (firstRow.values && firstRow.values.length > 0) {
          const deviceCount = parseInt(firstRow.values[0].string_value, 10);
          console.log('✅ Device count from database:', deviceCount);
          return deviceCount;
        }
      }
    }
    
    // Fallback: return null if we can't parse the result
    console.warn('Could not parse device count from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get device count:', error);
    return null;
  }
}

/**
 * Get heatmap data for device anomalies by type and firmware version
 * @returns {Promise<Array>} Heatmap data with device_type, firmware_version, out_of_range_pct, out_of_range_events, total_readings
 */
export async function getDeviceHeatmapData() {
  // CGM schema: out-of-range RATE (%) by device type and firmware — a RATE
  // (AVG(glucose_out_of_range)*100), NOT a raw count, so a device model/firmware
  // with more patients isn't ranked "worse" purely for having more readings.
  // device_model comes from silver_patient_registry (per-patient SSOT) joined on
  // patient_id — NOT gold's per-reading device_model, which disagrees with the
  // registry for most patients and would make this heatmap inconsistent with the
  // Coach / Population Risk views. firmware_version is reading-level (gold).
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT
      r.device_model as device_type,
      CAST(g.firmware_version AS STRING) as firmware_version,
      ROUND(AVG(g.glucose_out_of_range) * 100, 1) as out_of_range_pct,
      SUM(g.glucose_out_of_range) as out_of_range_events,
      COUNT(*) as total_readings
    FROM ${catalog}.${schema}.gold_patient_device_readings g
    JOIN ${catalog}.${schema}.silver_patient_registry r ON g.patient_id = r.patient_id
    GROUP BY r.device_model, g.firmware_version
    ORDER BY r.device_model, g.firmware_version
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    // Parse the DBSQL MCP server response
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      // Extract rows from data_array
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const heatmapData = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 5) {
            return {
              device_type: row.values[0].string_value,
              firmware_version: row.values[1].string_value,
              out_of_range_pct: parseFloat(row.values[2].string_value),
              out_of_range_events: parseInt(row.values[3].string_value, 10),
              total_readings: parseInt(row.values[4].string_value, 10)
            };
          }
          return null;
        }).filter(item => item !== null);
        
        console.log('✅ Heatmap data from database:', heatmapData.length, 'rows');
        return heatmapData;
      }
    }
    
    // Fallback: return null if we can't parse the result
    console.warn('Could not parse heatmap data from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get heatmap data:', error);
    return null;
  }
}

/**
 * Get out-of-range device readings for Device Detail table
 * @returns {Promise<Array>} Device readings with glucose_out_of_range = 1
 */
export async function getOutOfRangeDevices() {
  // CGM schema: use gold_patient_device_readings (has all data in one table)
  // Time filter: only readings in the last 3-hour rolling window — matches
  // incident-window length and the "live state" framing of the rest of the
  // dashboard. Without this filter the panel was returning the 50 most-recent
  // OOR rows from the full 7-day window, which gave an inconsistent
  // implicit time scope.
  const { catalog, schema } = await getConfig();
  // device_model from silver_patient_registry (per-patient SSOT) joined on
  // patient_id — gold's per-reading device_model disagrees with the registry.
  const query = `
    SELECT
      g.device_id,
      DATE_FORMAT(g.time, 'yyyy-MM-dd HH:mm') as reading_time,
      g.patient_id,
      r.device_model as device_type,
      CAST(g.firmware_version AS STRING) as firmware_version,
      g.glucose as glucose_value
    FROM
      ${catalog}.${schema}.gold_patient_device_readings g
      JOIN ${catalog}.${schema}.silver_patient_registry r ON g.patient_id = r.patient_id
    WHERE g.glucose_out_of_range = 1
      AND g.time >= (
        SELECT MAX(time) - INTERVAL 3 HOUR
        FROM ${catalog}.${schema}.gold_patient_device_readings
      )
    ORDER BY g.time DESC
    LIMIT 50
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    // Parse the DBSQL MCP server response
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      // Extract rows from data_array
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const devices = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 6) {
            return {
              device_id: row.values[0].string_value,
              reading_time: row.values[1].string_value,
              patient_id: row.values[2].string_value,
              device_type: row.values[3].string_value,
              firmware_version: row.values[4].string_value,
              glucose_value: parseFloat(row.values[5].string_value)
            };
          }
          return null;
        }).filter(item => item !== null);
        
        console.log('✅ Out-of-range devices from database:', devices.length, 'rows');
        return devices;
      }
    }
    
    // Fallback: return null if we can't parse the result
    console.warn('Could not parse out-of-range devices from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get out-of-range devices:', error);
    return null;
  }
}

/**
 * Get device pattern alerts for the Emerging Pattern Alerts section
 * @returns {Promise<Array>} Device patterns with elevated metrics
 */
export async function getDevicePatternAlerts() {
  // CGM schema: aggregate from gold_patient_device_readings (no pre-aggregated table available)
  // Lower threshold from 1000 to 10 due to smaller dataset in CGM schema
  const { catalog, schema } = await getConfig();
  // device_model from silver_patient_registry (per-patient SSOT) joined on patient_id
  // — gold's per-reading device_model disagrees with the registry. region is consistent
  // across both tables (verified 0 mismatch), sourced from the registry here for SSOT.
  const query = `
    SELECT
      r.device_model as device_type,
      CAST(g.firmware_version AS STRING) as firmware_version,
      r.region,
      SUM(g.glucose_out_of_range) as total_oor_events,
      COUNT(*) as total_events,
      ROUND(AVG(CASE WHEN g.glucose_out_of_range = 1 THEN 100.0 ELSE 0.0 END), 2) as avg_oor_rate_pct,
      COUNT(DISTINCT DATE(g.time)) as days_tracked
    FROM ${catalog}.${schema}.gold_patient_device_readings g
    JOIN ${catalog}.${schema}.silver_patient_registry r ON g.patient_id = r.patient_id
    GROUP BY r.device_model, g.firmware_version, r.region
    HAVING SUM(g.glucose_out_of_range) > 10
    ORDER BY avg_oor_rate_pct DESC
    LIMIT 4
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    // Parse the DBSQL MCP server response
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      // Extract rows from data_array
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const alerts = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 7) {
            return {
              device_type: row.values[0].string_value,
              firmware_version: row.values[1].string_value,
              region: row.values[2].string_value,
              total_oor_events: parseInt(row.values[3].string_value, 10),
              total_events: parseInt(row.values[4].string_value, 10),
              avg_oor_rate_pct: parseFloat(row.values[5].string_value),
              days_tracked: parseInt(row.values[6].string_value, 10)
            };
          }
          return null;
        }).filter(item => item !== null);
        
        console.log('✅ Device pattern alerts from database:', alerts.length, 'patterns');
        return alerts;
      }
    }
    
    // Fallback: return null if we can't parse the result
    console.warn('Could not parse device pattern alerts from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get device pattern alerts:', error);
    return null;
  }
}

export async function getDeviceRegionalDistribution() {
  // Out-of-range events + monitored footprint per region (geo blast-radius view).
  // Verified columns on gold_patient_device_readings: region, glucose_out_of_range, patient_id.
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT
      region,
      SUM(glucose_out_of_range) as oor_events,
      COUNT(DISTINCT patient_id) as patient_count
    FROM ${catalog}.${schema}.gold_patient_device_readings
    GROUP BY region
    ORDER BY oor_events DESC
  `;

  try {
    const result = await executeSQLQuery(query);
    const structuredContent = result?.result?.structuredContent;
    const rows = structuredContent?.result?.data_array;

    if (rows && rows.length > 0) {
      const regions = rows.map(row => {
        const v = row.values || row;
        return {
          region: v[0]?.string_value || v[0] || 'Unknown',
          oorEvents: parseInt(v[1]?.string_value ?? v[1], 10) || 0,
          patientCount: parseInt(v[2]?.string_value ?? v[2], 10) || 0,
        };
      });
      console.log('✅ Device regional distribution:', regions.length, 'regions');
      return regions;
    }

    console.warn('Could not parse device regional distribution from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get device regional distribution:', error);
    return [];
  }
}

// VIEW ② Diagnose — Firmware Lifecycle: device calibration error (MAE =
// |observed − true|) per firmware version per day. Joins gold (firmware) to
// pseudo_incident_7d_labeled (observed/true) — same signal as the landing MAE
// chart. Clean firmwares sit near 0; the faulty version spikes during incident.
export async function getFirmwareLifecycle() {
  const { catalog, schema } = await getConfig();
  // MAE = mean |observed − true| device error per firmware per day, computed over the
  // AFFECTED (in-incident) readings so the chart shows the true fault magnitude (~40 mg/dL)
  // rather than a whole-day average that dilutes the ~3-hour incident to a few mg/dL.
  // Fallback to the all-readings mean (~0) on days/firmwares with no fault, so clean
  // firmwares stay flat at baseline. The COUNT(incident) > COUNT(DISTINCT incident device)
  // guard is defense-in-depth: it requires more than one in-incident reading per device
  // before showing the in-incident MAE. (Firmware-boundary row duplication — a reading at
  // the exact rollout instant landing in BOTH adjacent firmware intervals — is now fixed at
  // source via the half-open [start,end) join in transformations.sql, so the prior firmware
  // no longer catches a spurious boundary reading on the rollout day.)
  const query = `
    SELECT
      DATE(g.time) as day,
      CAST(g.firmware_version AS STRING) as firmware_version,
      CASE WHEN COUNT(CASE WHEN p.incident_type IS NOT NULL THEN 1 END)
              > COUNT(DISTINCT CASE WHEN p.incident_type IS NOT NULL THEN g.patient_id END)
           THEN ROUND(AVG(CASE WHEN p.incident_type IS NOT NULL THEN ABS(p.glucose_observed - p.glucose_true) END), 1)
           ELSE ROUND(AVG(ABS(p.glucose_observed - p.glucose_true)), 1)
      END as mae,
      COUNT(*) as readings
    FROM ${catalog}.${schema}.gold_patient_device_readings g
    JOIN ${catalog}.${schema}.pseudo_incident_7d_labeled p
      ON g.patient_id = p.patient_id AND g.time = p.time
    WHERE g.firmware_version IS NOT NULL
    GROUP BY DATE(g.time), CAST(g.firmware_version AS STRING)
    ORDER BY day, firmware_version
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map(r => {
        const v = r.values || r;
        return {
          day: v[0]?.string_value ?? v[0],
          firmwareVersion: v[1]?.string_value ?? v[1],
          mae: parseFloat(v[2]?.string_value ?? v[2]) || 0,
          readings: parseInt(v[3]?.string_value ?? v[3], 10) || 0,
        };
      });
    }
    console.warn('Could not parse firmware lifecycle from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get firmware lifecycle:', error);
    return [];
  }
}

// VIEW ③ Assess — Population Risk: % of device-observed readings in hypo (<70) /
// hyper (>180) range, per cohort. Baseline (outside any incident) vs the
// positive-bias cohort (over-reads → hyper) vs negative-bias (under-reads → hypo)
// during their incident windows = the clinical blast radius. Verified cols on
// pseudo_incident_7d_labeled (same table the landing incident charts query).
export async function getPopulationRisk() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH d AS (
      SELECT
        glucose_observed,
        incident_direction,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
    )
    SELECT
      CASE
        WHEN incident_period = 0 THEN 'Baseline'
        WHEN incident_direction = 'positive' THEN 'Positive cohort'
        WHEN incident_direction = 'negative' THEN 'Negative cohort'
        ELSE 'Other'
      END as cohort,
      ROUND(SUM(CASE WHEN glucose_observed < 70 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 1) as pct_hypo,
      ROUND(SUM(CASE WHEN glucose_observed > 180 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 1) as pct_hyper,
      COUNT(*) as readings
    FROM d
    GROUP BY 1
    ORDER BY cohort
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map(r => {
        const v = r.values || r;
        return {
          cohort: v[0]?.string_value ?? v[0],
          pctHypo: parseFloat(v[1]?.string_value ?? v[1]) || 0,
          pctHyper: parseFloat(v[2]?.string_value ?? v[2]) || 0,
          readings: parseInt(v[3]?.string_value ?? v[3], 10) || 0,
        };
      }).filter(r => r.cohort !== 'Other');
    }
    console.warn('Could not parse population risk from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get population risk:', error);
    return [];
  }
}

// VIEW ③ → ACT — affected patients & devices: the outreach/recall roster. Two
// DISTINCT, non-conflated axes per patient:
//   • Device bias (incident_direction) = over-read / under-read — the DEVICE FAULT
//     direction (device reports higher / lower than true). Orthogonal to glucose level.
//   • %hypo / %hyper = the patient's CLINICAL exposure over their full observed window
//     (glucose_observed) — matches the Coach's Observations exactly (verified: gold.glucose
//     and pseudo_incident.glucose_observed agree). A patient can be under-read AND hyper
//     (e.g. true glucose ~236, under-read to ~196 → still hyper). The two are independent.
// device_model/region from silver_patient_registry (SSOT). Simulated, no PHI.
export async function getCohortAffected(limit = 40) {
  const { catalog, schema } = await getConfig();
  // Severity-ranked outreach roster. `limit` = integer row cap; pass null/0 for
  // "all" (no LIMIT). Int-coerced + clamped so it can't be SQL-injected.
  const n = Number.isFinite(+limit) ? Math.max(0, Math.min(5000, Math.floor(+limit))) : 40;
  const limitClause = n > 0 ? `LIMIT ${n}` : '';
  const query = `
    WITH affected AS (
      SELECT patient_id, incident_direction,
        ROUND(SUM(CASE WHEN glucose_observed < 70 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 1) as pct_hypo,
        ROUND(SUM(CASE WHEN glucose_observed > 180 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0) * 100, 1) as pct_hyper
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE incident_direction IN ('positive','negative')
      GROUP BY patient_id, incident_direction
    ),
    dev AS (
      -- silver_patient_registry is the per-patient SSOT for device_model/region/device_id
      -- (one row per patient). gold readings carry a device_model that can disagree with
      -- the registry for the same device_id, so reading from gold here made the roster
      -- conflict with the Coach view + the summary bars. Registry keeps all views aligned.
      SELECT patient_id, device_id, device_model, region
      FROM ${catalog}.${schema}.silver_patient_registry
    )
    SELECT a.patient_id, a.incident_direction, a.pct_hypo, a.pct_hyper,
      d.device_id, d.device_model, d.region
    FROM affected a
    LEFT JOIN dev d ON a.patient_id = d.patient_id
    ORDER BY GREATEST(a.pct_hypo, a.pct_hyper) DESC
    ${limitClause}
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map(r => {
        const v = r.values || r;
        return {
          patientId: v[0]?.string_value ?? v[0],
          direction: v[1]?.string_value ?? v[1],
          pctHypo: parseFloat(v[2]?.string_value ?? v[2]) || 0,
          pctHyper: parseFloat(v[3]?.string_value ?? v[3]) || 0,
          deviceId: v[4]?.string_value ?? v[4],
          deviceModel: v[5]?.string_value ?? v[5],
          region: v[6]?.string_value ?? v[6],
        };
      });
    }
    console.warn('Could not parse cohort-affected roster from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get cohort-affected roster:', error);
    return [];
  }
}

// VIEW ② → ACT — per firmware, the AFFECTED fleet: distinct patients/devices that
// had an in-incident (calibration-fault) reading WHILE on that firmware. This is the
// recall/outreach number — NOT "ever ran the firmware", which double-counts cohorts
// that ran the version but stayed clean on it (verified: 600 ran FW 4.0 but only the
// 300 positive-cohort patients were actually faulted on it).
export async function getFirmwareImpact() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT
      CAST(g.firmware_version AS STRING) as firmware_version,
      COUNT(DISTINCT CASE WHEN p.time >= p.incident_start_time AND p.time < p.incident_end_time THEN g.patient_id END) as affected_patients,
      COUNT(DISTINCT CASE WHEN p.time >= p.incident_start_time AND p.time < p.incident_end_time THEN g.device_id END) as affected_devices
    FROM ${catalog}.${schema}.gold_patient_device_readings g
    JOIN ${catalog}.${schema}.pseudo_incident_7d_labeled p
      ON g.patient_id = p.patient_id AND g.time = p.time
    WHERE g.firmware_version IS NOT NULL
    GROUP BY CAST(g.firmware_version AS STRING)
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map(r => {
        const v = r.values || r;
        return {
          firmwareVersion: v[0]?.string_value ?? v[0],
          affectedPatients: parseInt(v[1]?.string_value ?? v[1], 10) || 0,
          affectedDevices: parseInt(v[2]?.string_value ?? v[2], 10) || 0,
        };
      });
    }
    console.warn('Could not parse firmware impact from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get firmware impact:', error);
    return [];
  }
}

// VIEW ③ — affected-cohort breakdown by region + device model, EACH split by error
// direction (positive=over-read, negative=under-read) so both sub-groups show. Full
// affected population (not the LIMIT-40 roster): distinct incident-cohort patients
// joined to their registry region/model. Powers the Population Risk summary bars.
export async function getCohortAffectedBreakdown() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH affected AS (
      SELECT DISTINCT patient_id, incident_direction FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE incident_direction IN ('positive','negative')
    ),
    reg AS (
      SELECT a.patient_id, a.incident_direction, r.region, r.device_model
      FROM affected a JOIN ${catalog}.${schema}.silver_patient_registry r ON a.patient_id = r.patient_id
    )
    SELECT 'region' as dim, region as label, incident_direction as dir, COUNT(*) as n FROM reg GROUP BY region, incident_direction
    UNION ALL
    SELECT 'model' as dim, device_model as label, incident_direction as dir, COUNT(*) as n FROM reg GROUP BY device_model, incident_direction
    ORDER BY dim, label, dir
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    const acc = { region: {}, model: {} };
    if (rows && rows.length > 0) {
      rows.forEach(r => {
        const v = r.values || r;
        const dim = v[0]?.string_value ?? v[0];
        const label = v[1]?.string_value ?? v[1];
        const dir = v[2]?.string_value ?? v[2];
        const n = parseInt(v[3]?.string_value ?? v[3], 10) || 0;
        const bucket = acc[dim] || (acc[dim] = {});
        const item = bucket[label] || (bucket[label] = { label, positive: 0, negative: 0, total: 0 });
        if (dir === 'positive') item.positive += n; else item.negative += n;
        item.total += n;
      });
    }
    const toSorted = (obj) => Object.values(obj).sort((a, b) => b.total - a.total);
    return { byRegion: toSorted(acc.region), byModel: toSorted(acc.model) };
  } catch (error) {
    console.error('Failed to get cohort affected breakdown:', error);
    return { byRegion: [], byModel: [] };
  }
}

/**
 * Get per-device-model calibration drift during the firmware-4.0 incident windows.
 *
 * WHY THIS METRIC: the Device Out-of-Range heatmap aggregates over the whole 7-day
 * window, where the real HUPA-UCM baseline already sits at ~33% out-of-range — so a
 * 3-hour calibration fault on 30% of the fleet is diluted into the background and the
 * heatmap looks flat. Calibration drift (|observed − true|) instead measures the
 * device fault DIRECTLY: it is ~0 mg/dL for calibrated devices and ≈±40 mg/dL during
 * the incident, regardless of the underlying glucose distribution — so the fault pops
 * cleanly AND honestly (it's the same signal as the model MAE-shift, just measured at
 * the source rather than via residuals).
 *
 * The two incident windows are mutually-exclusive cohorts (see
 * 05_incident_inference_bidirectional.py): Window 1 = over-read (+bias, Alpha/Gamma),
 * Window 2 = under-read (−bias, Beta/Delta). incident_direction ('positive'/'negative')
 * identifies the window; signed drift is rounded so over/under reads opposite signs.
 * glucose_true / glucose_observed live in pseudo_incident_7d_labeled (NOT gold);
 * device_model comes from silver_patient_registry (per-patient SSOT), matching the
 * other device views. This is read-only — NO pipeline change.
 *
 * @returns {Promise<Array>} [{ device_model, direction, window_start, devices, signed_drift, abs_drift }]
 */
export async function getCalibrationDrift() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH cohort AS (
      SELECT
        p.patient_id,
        p.incident_direction,
        p.incident_start_time,
        p.glucose_observed,
        p.glucose_true
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled p
      WHERE p.has_incident = 1
        AND p.time >= p.incident_start_time
        AND p.time <  p.incident_end_time
    )
    SELECT
      r.device_model            AS device_model,
      c.incident_direction      AS direction,
      CAST(MIN(c.incident_start_time) AS STRING) AS window_start,
      COUNT(DISTINCT c.patient_id) AS devices,
      ROUND(AVG(c.glucose_observed - c.glucose_true), 1)      AS signed_drift,
      ROUND(AVG(ABS(c.glucose_observed - c.glucose_true)), 1) AS abs_drift
    FROM cohort c
    JOIN ${catalog}.${schema}.silver_patient_registry r ON c.patient_id = r.patient_id
    GROUP BY r.device_model, c.incident_direction
    ORDER BY c.incident_direction, r.device_model
  `;

  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      const drift = rows.map(row => {
        const v = row.values || row;
        return {
          device_model: v[0]?.string_value ?? v[0],
          direction: v[1]?.string_value ?? v[1],        // 'positive' (over-read) | 'negative' (under-read)
          window_start: v[2]?.string_value ?? v[2],
          devices: parseInt(v[3]?.string_value ?? v[3], 10) || 0,
          signed_drift: parseFloat(v[4]?.string_value ?? v[4]) || 0,
          abs_drift: parseFloat(v[5]?.string_value ?? v[5]) || 0,
        };
      });
      console.log('✅ Calibration drift from database:', drift.length, 'rows');
      return drift;
    }
    console.warn('Could not parse calibration drift from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get calibration drift:', error);
    return [];
  }
}

// Per-firmware fault cohort: which DEVICE MODELS were faulted on each firmware, in which
// DIRECTION (over- vs under-read), with device counts. Lets the Device Error by Firmware × Day
// heatmap annotate each firmware row with its drift direction + affected models — folding in
// what the (now-retired) Calibration Drift panel used to show. Data-derived (NOT hardcoded):
// firmware ← gold, direction ← pseudo incident, device_model ← registry SSOT — so if a cohort
// ever shifts, the labels track it. Only in-incident ('calibration_bias') readings count.
export async function getFirmwareCohorts() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH cohort AS (
      SELECT p.patient_id, p.incident_direction,
             CAST(g.firmware_version AS STRING) AS firmware_version
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled p
      JOIN ${catalog}.${schema}.gold_patient_device_readings g
        ON p.patient_id = g.patient_id AND p.time = g.time
      WHERE p.incident_type = 'calibration_bias'
    )
    SELECT c.firmware_version            AS firmware_version,
           c.incident_direction          AS direction,
           r.device_model                AS device_model,
           COUNT(DISTINCT c.patient_id)  AS devices
    FROM cohort c
    JOIN ${catalog}.${schema}.silver_patient_registry r ON c.patient_id = r.patient_id
    GROUP BY c.firmware_version, c.incident_direction, r.device_model
    ORDER BY c.firmware_version, devices DESC
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map(row => {
        const v = row.values || row;
        return {
          firmware_version: v[0]?.string_value ?? v[0],
          direction: v[1]?.string_value ?? v[1],        // 'positive' (over-read) | 'negative' (under-read)
          device_model: v[2]?.string_value ?? v[2],
          devices: parseInt(v[3]?.string_value ?? v[3], 10) || 0,
        };
      });
    }
    console.warn('Could not parse firmware cohorts from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get firmware cohorts:', error);
    return [];
  }
}

export default { executeSQLQuery, getDistinctDeviceCount, getDeviceHeatmapData, getOutOfRangeDevices, getDevicePatternAlerts, getDeviceRegionalDistribution, getFirmwareLifecycle, getPopulationRisk, getCohortAffected, getFirmwareImpact, getCohortAffectedBreakdown, getCalibrationDrift, getFirmwareCohorts };

