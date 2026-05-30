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

export default { 
  getPopulationMetrics, 
  getInsulinMetrics, 
  getDeviceDistribution,
  getRegionalDistribution
};
