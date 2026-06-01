// Diabetes Coach Dashboard Clinical Metrics - SQL Queries
// Uses gold_patient_device_readings for real-time clinical data
//
// All SQL queries here fetch catalog/schema from getConfig() (Flask /api/config
// sourced from app.yaml env vars). NEVER hardcode catalog/schema names inline.

import { executeSQLQuery } from '../../api/databricksSQL';
import { getConfig } from '../../api/config';

/**
 * Get population-level clinical metrics (last 24h)
 * @returns {Promise<Object>} Clinical metrics object
 */
export async function getPopulationMetrics() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT 
      ROUND(AVG(glucose), 1) as avg_glucose,
      ROUND(MIN(glucose), 1) as min_glucose,
      ROUND(MAX(glucose), 1) as max_glucose,
      ROUND(STDDEV(glucose), 1) as stddev_glucose,
      ROUND(AVG(CASE WHEN glucose BETWEEN 70 AND 180 THEN 1 ELSE 0 END) * 100, 1) as time_in_range,
      COUNT(DISTINCT CASE WHEN glucose < 70 THEN patient_id END) as patients_with_hypo,
      COUNT(DISTINCT CASE WHEN glucose > 180 THEN patient_id END) as patients_with_hyper,
      COUNT(CASE WHEN glucose < 70 THEN 1 END) as hypo_events,
      COUNT(CASE WHEN glucose > 180 THEN 1 END) as hyper_events,
      ROUND(AVG(CASE WHEN glucose < 70 THEN 1 ELSE 0 END) * 100, 1) as pct_time_below_range,
      ROUND(AVG(CASE WHEN glucose > 180 THEN 1 ELSE 0 END) * 100, 1) as pct_time_above_range,
      COUNT(DISTINCT patient_id) as total_patients_monitored
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 24 HOUR 
      FROM ${catalog}.${schema}.gold_patient_device_readings
    )
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        const firstRow = structuredContent.result.data_array[0];
        const values = firstRow.values || firstRow;
        
        const metrics = {
          avgGlucose: parseFloat(values[0]?.string_value || values[0]) || null,
          minGlucose: parseFloat(values[1]?.string_value || values[1]) || null,
          maxGlucose: parseFloat(values[2]?.string_value || values[2]) || null,
          stddevGlucose: parseFloat(values[3]?.string_value || values[3]) || null,
          timeInRange: parseFloat(values[4]?.string_value || values[4]) || null,
          patientsWithHypo: parseInt(values[5]?.string_value || values[5], 10) || null,
          patientsWithHyper: parseInt(values[6]?.string_value || values[6], 10) || null,
          hypoEvents: parseInt(values[7]?.string_value || values[7], 10) || null,
          hyperEvents: parseInt(values[8]?.string_value || values[8], 10) || null,
          pctTimeBelowRange: parseFloat(values[9]?.string_value || values[9]) || null,
          pctTimeAboveRange: parseFloat(values[10]?.string_value || values[10]) || null,
          totalPatientsMonitored: parseInt(values[11]?.string_value || values[11], 10) || null
        };
        
        console.log('✅ Population clinical metrics:', metrics);
        return metrics;
      }
    }
    
    console.warn('Could not parse population metrics from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get population metrics:', error);
    return null;
  }
}

/**
 * Get insulin delivery metrics (last 24h)
 * @returns {Promise<Object>} Insulin metrics object
 */
export async function getInsulinMetrics() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT 
      COUNT(CASE WHEN basal_present = 1 THEN 1 END) as basal_events,
      COUNT(CASE WHEN bolus_event = 1 THEN 1 END) as bolus_events,
      COUNT(CASE WHEN carb_event = 1 THEN 1 END) as carb_events,
      ROUND(AVG(CASE WHEN basal_rate > 0 THEN basal_rate END), 2) as avg_basal_rate,
      ROUND(AVG(CASE WHEN bolus_volume_delivered > 0 THEN bolus_volume_delivered END), 2) as avg_bolus_volume
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 24 HOUR 
      FROM ${catalog}.${schema}.gold_patient_device_readings
    )
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        const firstRow = structuredContent.result.data_array[0];
        const values = firstRow.values || firstRow;
        
        const metrics = {
          basalEvents: parseInt(values[0]?.string_value || values[0], 10) || null,
          bolusEvents: parseInt(values[1]?.string_value || values[1], 10) || null,
          carbEvents: parseInt(values[2]?.string_value || values[2], 10) || null,
          avgBasalRate: parseFloat(values[3]?.string_value || values[3]) || null,
          avgBolusVolume: parseFloat(values[4]?.string_value || values[4]) || null
        };
        
        console.log('✅ Insulin metrics:', metrics);
        return metrics;
      }
    }
    
    console.warn('Could not parse insulin metrics from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get insulin metrics:', error);
    return null;
  }
}

/**
 * Get device model distribution (last 24h)
 * @returns {Promise<Array>} Array of device models with counts
 */
export async function getDeviceDistribution() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT 
      device_model,
      COUNT(DISTINCT patient_id) as patient_count,
      COUNT(DISTINCT device_id) as device_count
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 24 HOUR 
      FROM ${catalog}.${schema}.gold_patient_device_readings
    )
    GROUP BY device_model
    ORDER BY patient_count DESC
    LIMIT 10
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        const rows = structuredContent.result.data_array;
        
        const devices = rows.map(row => {
          const values = row.values || row;
          return {
            model: values[0]?.string_value || values[0] || 'Unknown',
            patientCount: parseInt(values[1]?.string_value || values[1], 10) || 0,
            deviceCount: parseInt(values[2]?.string_value || values[2], 10) || 0
          };
        });
        
        console.log('✅ Device distribution:', devices);
        return devices;
      }
    }
    
    console.warn('Could not parse device distribution from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get device distribution:', error);
    return [];
  }
}

/**
 * Get regional patient distribution (last 24h)
 * @returns {Promise<Array>} Array of regions with patient counts
 */
export async function getRegionalDistribution() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT 
      region,
      COUNT(DISTINCT patient_id) as patient_count
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 24 HOUR 
      FROM ${catalog}.${schema}.gold_patient_device_readings
    )
    GROUP BY region
    ORDER BY patient_count DESC
  `;
  
  try {
    const result = await executeSQLQuery(query);
    
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        const rows = structuredContent.result.data_array;
        
        const regions = rows.map(row => {
          const values = row.values || row;
          return {
            region: values[0]?.string_value || values[0] || 'Unknown',
            patientCount: parseInt(values[1]?.string_value || values[1], 10) || 0
          };
        });
        
        console.log('✅ Regional distribution:', regions);
        return regions;
      }
    }
    
    console.warn('Could not parse regional distribution from response:', result);
    return [];
  } catch (error) {
    console.error('Failed to get regional distribution:', error);
    return [];
  }
}

// ── Per-patient view (GitHub #5: replaces the hardcoded Sarah-K. demo panel) ──
// All read-only SQL on the existing /api/sql/query path — no Lakebase needed.
// Patient identifiers are simulated PSEUDO_* IDs (no real PHI). User-supplied
// search/id is allow-listed to [A-Za-z0-9_] before interpolation (injection guard).

const safeToken = (s) => String(s ?? '').replace(/[^A-Za-z0-9_]/g, '');

/**
 * Typeahead patient picker — server-filtered (NOT load-all; ~1000 patients).
 * @param {string} filter - substring to match against patient_id
 * @returns {Promise<Array<{patientId,region,deviceModel}>>}
 */
export async function getPatientList(filter = '') {
  const { catalog, schema } = await getConfig();
  const safe = safeToken(filter);
  const where = safe ? `WHERE patient_id LIKE '%${safe}%'` : '';
  const query = `
    SELECT patient_id, region, device_model
    FROM ${catalog}.${schema}.silver_patient_registry
    ${where}
    ORDER BY patient_id
    LIMIT 50
  `;
  try {
    const result = await executeSQLQuery(query);
    const rows = result?.result?.structuredContent?.result?.data_array;
    if (rows && rows.length > 0) {
      return rows.map((r) => {
        const v = r.values || r;
        return {
          patientId: v[0]?.string_value ?? v[0],
          region: v[1]?.string_value ?? v[1],
          deviceModel: v[2]?.string_value ?? v[2],
        };
      });
    }
    return [];
  } catch (error) {
    console.error('Failed to get patient list:', error);
    return [];
  }
}

// Parse a single-row DBSQL result into its raw value array (or null).
const firstRowValues = (result) => {
  const rows = result?.result?.structuredContent?.result?.data_array;
  if (rows && rows.length > 0) return rows[0].values || rows[0];
  return null;
};

/**
 * Full per-patient detail: demographics (silver_patient_registry), observed-window
 * KPIs (gold_patient_device_readings), near-term 15/30-min forecast (one row per
 * patient in fleet_forecast_incident — real model output), and a 24h glucose series.
 * @param {string} patientId
 * @returns {Promise<Object|null>}
 */
export async function getPatientDetail(patientId) {
  const { catalog, schema } = await getConfig();
  const id = safeToken(patientId);
  if (!id) return null;
  const g = `${catalog}.${schema}.gold_patient_device_readings`;
  const reg = `${catalog}.${schema}.silver_patient_registry`;
  const fc = `${catalog}.${schema}.fleet_forecast_incident`;
  const inc = `${catalog}.${schema}.pseudo_incident_7d_labeled`;

  const demographicsQ = `
    SELECT YEAR(CURRENT_DATE()) - birth_year AS age, patient_diagnosis, device_model, region, device_id
    FROM ${reg} WHERE patient_id = '${id}' LIMIT 1`;
  const kpiQ = `
    SELECT
      ROUND(AVG(glucose), 0) as avg_glucose,
      ROUND(AVG(CASE WHEN glucose BETWEEN 70 AND 180 THEN 1 ELSE 0 END) * 100, 0) as tir,
      ROUND(AVG(CASE WHEN glucose < 70 THEN 1 ELSE 0 END) * 100, 0) as pct_hypo,
      ROUND(AVG(CASE WHEN glucose > 180 THEN 1 ELSE 0 END) * 100, 0) as pct_hyper,
      ROUND(STDDEV(glucose) / NULLIF(AVG(glucose), 0) * 100, 0) as cv,
      COUNT(*) as readings,
      MIN(time) as first_time,
      MAX(time) as last_time,
      MAX_BY(CAST(firmware_version AS STRING), time) as firmware,
      ROUND(AVG(CASE WHEN glucose < 54 THEN 1 ELSE 0 END) * 100, 0) as pct_very_low,
      ROUND(AVG(CASE WHEN glucose > 250 THEN 1 ELSE 0 END) * 100, 0) as pct_very_high
    FROM ${g} WHERE patient_id = '${id}'`;
  const forecastQ = `
    SELECT glucose_observed, pred_15m, pred_30m, delta_15m, delta_30m
    FROM ${fc} WHERE patient_id = '${id}' LIMIT 1`;
  // Full ~7-day window from the incident-labeled table so the device-fault window is
  // actually visible (incidents sit on earlier days, off the last-24h screen). We pull
  // BOTH observed (device-reported) and true glucose: outside the incident they overlap,
  // during it they diverge — the gap IS the calibration fault, made visible. incident_*
  // columns are constant per patient (the labeled window) → read off the first row.
  // Downsampled to ~15-min resolution (every 3rd 5-min reading) — cuts the payload ~3x
  // (≈2000 → ≈670 rows) so the Coach view (and the guided tour's final step, which waits
  // on it) loads noticeably faster. Uniform sampling keeps the x-axis time-accurate; the
  // incident's masked-severity divergence is a flat ±40 offset, so 15-min spacing (≈12
  // points across the 3h window) still shows it clearly.
  const seriesQ = `
    SELECT time, glucose_observed, glucose_true, incident_start_time, incident_end_time, incident_direction
    FROM ${inc}
    WHERE patient_id = '${id}'
      AND MINUTE(time) % 15 = 0
    ORDER BY time`;
  // Device-fault incident summary (in-incident window): bias direction + true-vs-observed.
  // Powers the "masked severity" alert — under-read (negative) device on a patient whose
  // TRUE glucose was hyper means the device under-reported danger.
  const incidentQ = `
    SELECT incident_direction,
      ROUND(AVG(glucose_true), 0) as true_mean,
      ROUND(MAX(glucose_true), 0) as true_max,
      ROUND(AVG(glucose_observed), 0) as obs_mean,
      ROUND(AVG(glucose_true - glucose_observed), 0) as bias_gap
    FROM ${inc}
    WHERE patient_id = '${id}' AND time >= incident_start_time AND time < incident_end_time
    GROUP BY incident_direction LIMIT 1`;

  try {
    const [demoRes, kpiRes, fcRes, seriesRes, incRes] = await Promise.all([
      executeSQLQuery(demographicsQ),
      executeSQLQuery(kpiQ),
      executeSQLQuery(forecastQ),
      executeSQLQuery(seriesQ),
      executeSQLQuery(incidentQ),
    ]);

    const demo = firstRowValues(demoRes);
    const kpi = firstRowValues(kpiRes);
    const fcv = firstRowValues(fcRes);
    const incv = firstRowValues(incRes);
    const num = (x) => (x == null ? null : parseFloat(x?.string_value ?? x));

    // Full-window series: observed + true glucose per reading for the profile chart.
    const seriesRows = seriesRes?.result?.structuredContent?.result?.data_array || [];
    const series = seriesRows.map((r) => {
      const v = r.values || r;
      const obs = num(v[1]);
      return { time: v[0]?.string_value ?? v[0], glucose: obs, observed: obs, glucoseTrue: num(v[2]) };
    }).filter((d) => d.observed != null);
    // Incident window for shading (constant per patient → read off the first row).
    const sr0 = seriesRows[0] ? (seriesRows[0].values || seriesRows[0]) : null;
    const incStart = sr0 ? (sr0[3]?.string_value ?? sr0[3]) : null;
    const incidentWindow = incStart ? {
      start: incStart,
      end: sr0[4]?.string_value ?? sr0[4],
      direction: sr0[5]?.string_value ?? sr0[5],
    } : null;

    return {
      patientId: id,
      demographics: demo ? {
        age: num(demo[0]),
        diagnosis: demo[1]?.string_value ?? demo[1],
        deviceModel: demo[2]?.string_value ?? demo[2],
        region: demo[3]?.string_value ?? demo[3],
        deviceId: demo[4]?.string_value ?? demo[4],
      } : null,
      kpis: kpi ? {
        avgGlucose: num(kpi[0]),
        timeInRange: num(kpi[1]),
        pctHypo: num(kpi[2]),
        pctHyper: num(kpi[3]),
        cv: num(kpi[4]),
        readings: parseInt(kpi[5]?.string_value ?? kpi[5], 10) || 0,
        firstTime: kpi[6]?.string_value ?? kpi[6],
        lastTime: kpi[7]?.string_value ?? kpi[7],
        firmware: kpi[8]?.string_value ?? kpi[8],
        pctVeryLow: num(kpi[9]),   // <54 mg/dL (level-2 Very Low, Battelino)
        pctVeryHigh: num(kpi[10]), // >250 mg/dL (level-2 Very High)
      } : null,
      forecast: fcv ? {
        glucoseObserved: num(fcv[0]),
        pred15m: num(fcv[1]),
        pred30m: num(fcv[2]),
        delta15m: num(fcv[3]),
        delta30m: num(fcv[4]),
      } : null,
      // Device-fault incident: bias direction + true-vs-observed during the incident.
      // maskedSeverity = under-read device whose TRUE glucose was hyper (>180) → the
      // device under-reported a dangerously-high patient.
      incident: incv ? (() => {
        const direction = incv[0]?.string_value ?? incv[0];
        const trueMean = num(incv[1]);
        const trueMax = num(incv[2]);
        const obsMean = num(incv[3]);
        const biasGap = num(incv[4]);
        return { direction, trueMean, trueMax, obsMean, biasGap, maskedSeverity: direction === 'negative' && trueMax != null && trueMax > 180 };
      })() : null,
      series,
      incidentWindow,
    };
  } catch (error) {
    console.error('Failed to get patient detail:', error);
    return null;
  }
}

export default {
  getPopulationMetrics,
  getInsulinMetrics,
  getDeviceDistribution,
  getRegionalDistribution,
  getPatientList,
  getPatientDetail
};
