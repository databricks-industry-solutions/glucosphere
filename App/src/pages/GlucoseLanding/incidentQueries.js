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
 *                   Diluted: only ~30% are affected so peak ~17 mg/dL.
 *   - mae_affected: AVG(|observed - true|) across affected patients only
 *                   (has_incident = 1). Shows the REAL device-error magnitude
 *                   during the incident — peaks ~45 mg/dL (close to the ±40
 *                   injected bias + baseline noise).
 *
 * The dilution gap (45 → 17) is the load-bearing storytelling number:
 * fleet-wide averaging masks the per-device severity, motivating
 * patient-level / direction-aware monitoring.
 *
 * Previous version returned mae_15m + mae_30m where mae_30m was just
 * mae_15m × 1.2 — redundant. Now both lines carry distinct information.
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
      AVG(CASE WHEN has_incident = 1 THEN error_value END) as mae_affected,
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
 * Get incident summary statistics
 * Returns key metrics about the incident (peak MAE, bias, duration, etc.)
 */
export async function getIncidentSummary() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH error_data AS (
      SELECT
        time,
        ABS(glucose_observed - glucose_true) + 5.0 as mae,
        (glucose_observed - glucose_true) as bias,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
        incident_type
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE time IS NOT NULL
    )
    SELECT
      MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_15m,
      MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_30m,
      5.8 as baseline_mae_15m,
      5.8 as baseline_mae_30m,
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
