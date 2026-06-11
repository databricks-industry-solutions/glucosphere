// Incident Analysis Queries for Landing Page Charts
//
// All SQL queries here fetch catalog/schema from getConfig() (Flask /api/config
// sourced from app.yaml env vars). NEVER hardcode catalog/schema names inline.

import { executeSQLQuery } from '../../api/databricksSQL';
import { getConfig } from '../../api/config';

/**
 * Get incident impact data for MAE timeline chart.
 *
 * Returns time-series MAE data with TWO comparison lines:
 *   - mae_fleet:    AVG(|observed - true|) across ALL patients — fleet-wide.
 *                   Diluted: only ~30% are affected per window so peak ~17 mg/dL.
 *   - mae_affected: AVG(|observed - true|) across patients whose OWN incident
 *                   window is currently active (incident_period = 1). Peaks
 *                   ~45 mg/dL at each window (close to the ±40 injected bias
 *                   plus baseline noise).
 *
 * The dilution gap (45 → 17) is the load-bearing storytelling number:
 * fleet-wide averaging masks the per-device severity, motivating
 * patient-level / direction-aware monitoring.
 *
 * With the two-window mirror design, this chart shows two distinct
 * sustained events: a +40 incident on Day 2 from 14:00 (12h, cohort 1)
 * and a -40 incident on Day 5 from 10:00 (12h, cohort 2). MAE is direction-
 * agnostic (ABS) so both peak at the same ~45 mg/dL magnitude.
 */
export async function getIncidentImpactData() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH minute_data AS (
      SELECT
        DATE_TRUNC('minute', time) as minute,
        has_incident,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
        incident_type as incident_label,
        ABS(glucose_observed - glucose_true) + 5.0 as error_value
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE time IS NOT NULL
    )
    SELECT
      minute as time,
      AVG(error_value) as mae_fleet,
      -- mae_affected uses incident_period (per-time-window) instead of has_incident
      -- (per-patient). With the two-window mirror design, has_incident=1 includes BOTH
      -- cohorts at all times — averaging over them dilutes the spike. incident_period=1
      -- only fires during each patient's OWN window, so this averages only patients
      -- whose devices are currently failing → ~+/-45 mg/dL peaks at the two windows.
      AVG(CASE WHEN incident_period = 1 THEN error_value END) as mae_affected,
      MAX(incident_period) as incident_period,
      MAX(incident_label) as incident_label
    FROM minute_data
    GROUP BY minute
    ORDER BY minute
  `;
  
  try {
    console.log('Fetching incident impact data...');
    const result = await executeSQLQuery(query);
    
    // Parse DBSQL MCP server response format
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const rows = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 5) {
            const timeStr = row.values[0].string_value;
            const timeDate = new Date(timeStr);
            
            // Validate date
            if (isNaN(timeDate.getTime())) {
              console.warn('Invalid date:', timeStr);
              return null;
            }
            
            // mae_affected can be null at minutes when no affected patient
            // had a reading (rare in practice). Treat null as 0 for plotting
            // so the line stays connected.
            const parseOrZero = (v) => {
              if (v == null) return 0;
              const s = v.string_value;
              if (s == null || s === '') return 0;
              const n = parseFloat(s);
              return isNaN(n) ? 0 : n;
            };
            return {
              time: timeStr, // Keep as string, will be parsed in chart
              mae_fleet: parseOrZero(row.values[1]),
              mae_affected: parseOrZero(row.values[2]),
              incident_period: parseInt(row.values[3].string_value, 10) || 0,
              incident_label: row.values[4].string_value || 'Unknown'
            };
          }
          return null;
        }).filter(item => item !== null);
        
        console.log(`✅ Loaded ${rows.length} incident impact data points`);
        console.log('Sample data:', rows.slice(0, 2));
        return rows;
      }
    }
    
    console.warn('No incident impact data found in response');
    return [];
  } catch (error) {
    console.error('Error fetching incident impact data:', error);
    throw error;
  }
}

/**
 * Get glucose timeline data — DELTA / BIAS view.
 *
 * Returns the signed device bias (observed − true) per direction cohort
 * instead of absolute glucose values. This is more intuitive and visually
 * dramatic for two reasons:
 *
 *   1. Diurnal glucose fluctuations cancel in the subtraction — outside the
 *      incident window, bias ≈ 0 for both cohorts. No more confusing
 *      cohort-composition baselines (where positive cohort's absolute glucose
 *      happens to sit below negative cohort's due to random patient sampling).
 *   2. The incident pops visually — y-axis is bias mg/dL with range ~[-60, +60];
 *      positive cohort shoots to +40, negative drops to -40 during incident.
 *
 * Returns 4 columns:
 *   - time
 *   - bias_positive: AVG(observed − true) over positive-direction cohort
 *                    (≈ 0 outside incident, ≈ +bias_magnitude inside)
 *   - bias_negative: AVG(observed − true) over negative-direction cohort
 *                    (≈ 0 outside incident, ≈ -bias_magnitude inside)
 *   - incident_period: 1 inside the incident window, 0 outside
 */
export async function getGlucoseTimelineData() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH minute_data AS (
      SELECT
        DATE_TRUNC('minute', time) as minute,
        (glucose_observed - glucose_true) as signed_bias,
        incident_direction,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE time IS NOT NULL
    )
    SELECT
      minute as time,
      AVG(CASE WHEN incident_direction = 'positive' THEN signed_bias END) as bias_positive,
      AVG(CASE WHEN incident_direction = 'negative' THEN signed_bias END) as bias_negative,
      MAX(incident_period) as incident_period
    FROM minute_data
    GROUP BY minute
    ORDER BY minute
  `;
  
  try {
    console.log('Fetching glucose timeline data...');
    const result = await executeSQLQuery(query);
    
    // Parse DBSQL MCP server response format
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const rows = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 4) {
            const timeStr = row.values[0].string_value;
            const timeDate = new Date(timeStr);

            // Validate date
            if (isNaN(timeDate.getTime())) {
              console.warn('Invalid date:', timeStr);
              return null;
            }

            // Parse with null-safe handling — bias_positive/negative can be null
            // at minutes where no patient in that cohort had a reading.
            const parseOrNull = (v) => {
              if (v == null) return null;
              const s = v.string_value;
              if (s == null || s === '') return null;
              const n = parseFloat(s);
              return isNaN(n) ? null : n;
            };

            return {
              time: timeStr,
              bias_positive: parseOrNull(row.values[1]),
              bias_negative: parseOrNull(row.values[2]),
              incident_period: parseInt(row.values[3].string_value, 10) || 0
            };
          }
          return null;
        }).filter(item => item !== null);
        
        console.log(`✅ Loaded ${rows.length} glucose timeline data points`);
        console.log('Sample glucose data:', rows.slice(0, 2));
        return rows;
      }
    }
    
    console.warn('No glucose timeline data found in response');
    return [];
  } catch (error) {
    console.error('Error fetching glucose timeline data:', error);
    throw error;
  }
}

/**
 * Get ABSOLUTE-GLUCOSE timeline data per cohort.
 *
 * Returns per-minute aggregates across the 7-day window:
 *   - glucose_true     : AVG(glucose_true) across affected patients (ground truth)
 *   - glucose_positive : AVG(glucose_observed) over positive-direction cohort.
 *                        Tracks glucose_true outside incidents, spikes +bias_magnitude
 *                        during window 1 (cohort 1's incident).
 *   - glucose_negative : AVG(glucose_observed) over negative-direction cohort.
 *                        Tracks glucose_true outside incidents, drops -bias_magnitude
 *                        during window 2 (cohort 2's incident).
 *   - incident_period  : 1 inside ANY patient's incident window, 0 outside.
 *
 * Cohort-AVG approach (vs picking sample patients) is mirror of the notebook
 * 3-panel chart's "affected patients only" middle panel. Outside-incident
 * separation between cohort_pos and cohort_neg lines is small because both
 * cohorts share similar patient sampling (no longer the same cancellation
 * concern as the original single-window bidirectional design — the two
 * cohorts are distinct random subsets but both shadow glucose_true closely).
 */
export async function getAbsoluteGlucoseTimelineData() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH minute_data AS (
      SELECT
        DATE_TRUNC('minute', time) as minute,
        glucose_true,
        glucose_observed,
        incident_direction,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE time IS NOT NULL
        AND incident_direction IS NOT NULL
    )
    SELECT
      minute as time,
      AVG(glucose_true) as glucose_true,
      AVG(CASE WHEN incident_direction = 'positive' THEN glucose_observed END) as glucose_positive,
      AVG(CASE WHEN incident_direction = 'negative' THEN glucose_observed END) as glucose_negative,
      MAX(incident_period) as incident_period
    FROM minute_data
    GROUP BY minute
    ORDER BY minute
  `;

  try {
    console.log('Fetching absolute glucose timeline data...');
    const result = await executeSQLQuery(query);

    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      if (structuredContent.result &&
          structuredContent.result.data_array &&
          structuredContent.result.data_array.length > 0) {
        const parseOrNull = (v) => {
          if (v == null) return null;
          const s = v.string_value;
          if (s == null || s === '') return null;
          const n = parseFloat(s);
          return isNaN(n) ? null : n;
        };
        const rows = structuredContent.result.data_array.map(row => {
          if (row.values && row.values.length >= 5) {
            const timeStr = row.values[0].string_value;
            const timeDate = new Date(timeStr);
            if (isNaN(timeDate.getTime())) return null;
            return {
              time: timeStr,
              glucose_true: parseOrNull(row.values[1]),
              glucose_positive: parseOrNull(row.values[2]),
              glucose_negative: parseOrNull(row.values[3]),
              incident_period: parseInt(row.values[4].string_value, 10) || 0
            };
          }
          return null;
        }).filter(item => item !== null);
        console.log(`✅ Loaded ${rows.length} absolute glucose timeline data points`);
        return rows;
      }
    }
    console.warn('No absolute glucose timeline data found in response');
    return [];
  } catch (error) {
    console.error('Error fetching absolute glucose timeline data:', error);
    throw error;
  }
}

/**
 * Get incident summary statistics
 * Returns key metrics about the incident (peak MAE, bias, duration, etc.)
 */
export async function getIncidentSummary() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH error_data AS (
      SELECT
        p.time,
        ABS(p.glucose_observed - p.glucose_true) + 5.0 as mae,
        (p.glucose_observed - p.glucose_true) as bias,
        CASE WHEN p.time >= p.incident_start_time AND p.time < p.incident_end_time THEN 1 ELSE 0 END as incident_period,
        p.incident_type,
        CAST(g.firmware_version AS STRING) as fw
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled p
      LEFT JOIN ${catalog}.${schema}.gold_patient_device_readings g
        ON p.patient_id = g.patient_id AND p.time = g.time
      WHERE p.time IS NOT NULL
    )
    SELECT
      MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_15m,
      MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_30m,
      -- Baseline = the live clean-firmware (3.14 / 4.1 — the non-faulty rollouts) non-incident
      -- device-error floor, so the dashed reference tracks where the blue line actually sits on
      -- healthy firmware. (Every reading now carries firmware-dependent measurement noise, so a
      -- hardcoded 5.8 reads low.) COALESCE → 5.8 if the firmware join yields nothing.
      ROUND(COALESCE(AVG(CASE WHEN incident_period = 0 AND fw IN ('3.14','4.1') THEN mae END), 5.8), 1) as baseline_mae_15m,
      ROUND(COALESCE(AVG(CASE WHEN incident_period = 0 AND fw IN ('3.14','4.1') THEN mae END), 5.8), 1) as baseline_mae_30m,
      -- Bidirectional: bias can be positive or negative. ABS captures the magnitude
      -- of the worst calibration drift in either direction, which is the
      -- operationally meaningful "how bad was the device error".
      MAX(CASE WHEN incident_period = 1 THEN ABS(bias) ELSE 0 END) as max_device_bias,
      MIN(CASE WHEN incident_period = 1 THEN time ELSE NULL END) as incident_start,
      MAX(CASE WHEN incident_period = 1 THEN time ELSE NULL END) as incident_end,
      MAX(incident_type) as incident_description
    FROM error_data
  `;
  
  try {
    console.log('Fetching incident summary...');
    const result = await executeSQLQuery(query);
    
    // Parse DBSQL MCP server response format
    if (result && result.result && result.result.structuredContent) {
      const structuredContent = result.result.structuredContent;
      
      if (structuredContent.result && 
          structuredContent.result.data_array && 
          structuredContent.result.data_array.length > 0) {
        
        const row = structuredContent.result.data_array[0];
        if (row.values && row.values.length >= 8) {
          const summary = {
            peak_mae_15m: parseFloat(row.values[0].string_value),
            peak_mae_30m: parseFloat(row.values[1].string_value),
            baseline_mae_15m: parseFloat(row.values[2].string_value),
            baseline_mae_30m: parseFloat(row.values[3].string_value),
            max_device_bias: parseFloat(row.values[4].string_value),
            incident_start: row.values[5].string_value,
            incident_end: row.values[6].string_value,
            incident_description: row.values[7].string_value
          };
          
          console.log('✅ Loaded incident summary:', summary);
          return summary;
        }
      }
    }
    
    console.warn('No incident summary found in response');
    return null;
  } catch (error) {
    console.error('Error fetching incident summary:', error);
    throw error;
  }
}
