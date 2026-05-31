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
 * @returns {Promise<Array>} Heatmap data with device_type, firmware_version, out_of_range_events
 */
export async function getDeviceHeatmapData() {
  // CGM schema: count ONLY out-of-range readings by device type and firmware
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT 
      device_model as device_type, 
      CAST(firmware_version AS STRING) as firmware_version,
      COUNT(*) as out_of_range_events 
    FROM ${catalog}.${schema}.gold_patient_device_readings 
    WHERE glucose_out_of_range = 1
    GROUP BY device_model, firmware_version
    ORDER BY device_model, firmware_version
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
          if (row.values && row.values.length >= 3) {
            return {
              device_type: row.values[0].string_value,
              firmware_version: row.values[1].string_value,
              out_of_range_events: parseInt(row.values[2].string_value, 10)
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
  const query = `
    SELECT
      device_id,
      TIMESTAMPDIFF(MINUTE, time, (SELECT MAX(time) FROM ${catalog}.${schema}.gold_patient_device_readings)) as minutes_since_last_reading,
      patient_id,
      device_model as device_type,
      CAST(firmware_version AS STRING) as firmware_version,
      glucose as glucose_value
    FROM
      ${catalog}.${schema}.gold_patient_device_readings
    WHERE glucose_out_of_range = 1
      AND time >= (
        SELECT MAX(time) - INTERVAL 3 HOUR
        FROM ${catalog}.${schema}.gold_patient_device_readings
      )
    ORDER BY time DESC
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
              minutes_since_last_reading: parseInt(row.values[1].string_value, 10),
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
  const query = `
    SELECT 
      device_model as device_type,
      CAST(firmware_version AS STRING) as firmware_version,
      region,
      SUM(glucose_out_of_range) as total_oor_events,
      COUNT(*) as total_events,
      ROUND(AVG(CASE WHEN glucose_out_of_range = 1 THEN 100.0 ELSE 0.0 END), 2) as avg_oor_rate_pct,
      COUNT(DISTINCT DATE(time)) as days_tracked
    FROM ${catalog}.${schema}.gold_patient_device_readings
    GROUP BY device_model, firmware_version, region
    HAVING SUM(glucose_out_of_range) > 10
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
  const query = `
    SELECT
      DATE(g.time) as day,
      CAST(g.firmware_version AS STRING) as firmware_version,
      ROUND(AVG(ABS(p.glucose_observed - p.glucose_true)), 1) as mae,
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

// VIEW ③ → ACT — affected patients & devices per cohort: the outreach/recall
// roster. Cohort + per-patient hypo/hyper exposure (pseudo_incident_7d_labeled)
// joined to device/region (gold). One row per patient (firmware dropped to avoid
// per-firmware duplication). Identifiers are simulated — no real PHI.
export async function getCohortAffected() {
  const { catalog, schema } = await getConfig();
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
      SELECT DISTINCT patient_id, device_id, device_model, region
      FROM ${catalog}.${schema}.gold_patient_device_readings
    )
    SELECT a.patient_id, a.incident_direction, a.pct_hypo, a.pct_hyper,
      d.device_id, d.device_model, d.region
    FROM affected a
    LEFT JOIN dev d ON a.patient_id = d.patient_id
    ORDER BY a.incident_direction, GREATEST(a.pct_hypo, a.pct_hyper) DESC
    LIMIT 40
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

export default { executeSQLQuery, getDistinctDeviceCount, getDeviceHeatmapData, getOutOfRangeDevices, getDevicePatternAlerts, getDeviceRegionalDistribution, getFirmwareLifecycle, getPopulationRisk, getCohortAffected };

