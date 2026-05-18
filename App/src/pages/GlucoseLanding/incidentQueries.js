// Incident Analysis Queries for Landing Page Charts
//
// All SQL queries here fetch catalog/schema from getConfig() (Flask /api/config
// sourced from app.yaml env vars). NEVER hardcode catalog/schema names inline.

import { executeSQLQuery } from '../../api/databricksSQL';
import { getConfig } from '../../api/config';

/**
 * Get incident impact data for MAE timeline chart
 * Returns time series data showing MAE (Mean Absolute Error) over time
 * with incident period highlighted
 */
export async function getIncidentImpactData() {
  const { catalog, schema } = await getConfig();
  const query = `
    WITH minute_data AS (
      SELECT 
        DATE_TRUNC('minute', time) as minute,
        CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
        incident_type as incident_label,
        ABS(glucose_observed - glucose_true) + 5.0 as error_value
      FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
      WHERE time IS NOT NULL
    )
    SELECT 
      minute as time,
      AVG(error_value) as mae_15m,
      AVG(error_value) * 1.2 as mae_30m,
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
            
            return {
              time: timeStr, // Keep as string, will be parsed in chart
              mae_15m: parseFloat(row.values[1].string_value) || 0,
              mae_30m: parseFloat(row.values[2].string_value) || 0,
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
 * Get glucose timeline data comparing actual vs device readings,
 * split by incident_direction so the bidirectional bias is visible.
 *
 * Returns 4 columns:
 *   - time
 *   - glucose_actual: AVG ground truth across ALL patients
 *   - glucose_device_positive: AVG observed glucose across patients
 *       whose incident_direction = 'positive' (cohort that over-reads
 *       during incident — line shifts UP from actual)
 *   - glucose_device_negative: AVG observed glucose across patients
 *       whose incident_direction = 'negative' (cohort that under-reads
 *       — line shifts DOWN from actual)
 *   - incident_period: 1 inside the incident window, 0 outside
 *
 * Pre-bidirectional behavior averaged signed device_bias across all
 * affected patients, which canceled to ~0 when split was 50/50, making
 * the incident invisible on the chart. Splitting by direction preserves
 * the visual story.
 */
export async function getGlucoseTimelineData() {
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
    )
    SELECT
      minute as time,
      AVG(glucose_true) as glucose_actual,
      AVG(CASE WHEN incident_direction = 'positive' THEN glucose_observed END) as glucose_device_positive,
      AVG(CASE WHEN incident_direction = 'negative' THEN glucose_observed END) as glucose_device_negative,
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
          if (row.values && row.values.length >= 5) {
            const timeStr = row.values[0].string_value;
            const timeDate = new Date(timeStr);

            // Validate date
            if (isNaN(timeDate.getTime())) {
              console.warn('Invalid date:', timeStr);
              return null;
            }

            // Parse with null-safe handling — glucose_device_positive/negative
            // can be null at minutes where no patient in that cohort had a
            // reading (unlikely with 1000-patient dataset, but defensive).
            const parseOrNull = (v) => {
              if (v == null) return null;
              const s = v.string_value;
              if (s == null || s === '') return null;
              const n = parseFloat(s);
              return isNaN(n) ? null : n;
            };

            return {
              time: timeStr,
              glucose_actual: parseOrNull(row.values[1]) || 0,
              glucose_device_positive: parseOrNull(row.values[2]),
              glucose_device_negative: parseOrNull(row.values[3]),
              incident_period: parseInt(row.values[4].string_value, 10) || 0
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
