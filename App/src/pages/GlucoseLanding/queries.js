// Landing Page Metrics - SQL Queries
// Uses CGM schema data for real-time metrics

import { executeSQLQuery } from '../../api/databricksSQL';

/**
 * Get count of active patients (patients with readings in last 24h of available data)
 * @returns {Promise<number>} Count of active patients
 */
export async function getActivePatients() {
  const query = `
    SELECT COUNT(DISTINCT patient_id) as active_patients
    FROM hls_glucosphere.cgm.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 24 HOUR 
      FROM hls_glucosphere.cgm.gold_patient_device_readings
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
        if (firstRow.values && firstRow.values.length > 0) {
          const count = parseInt(firstRow.values[0].string_value, 10);
          console.log('✅ Active patients from database:', count);
          return count;
        }
      }
    }
    
    console.warn('Could not parse active patients from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get active patients:', error);
    return null;
  }
}

/**
 * Get count of devices currently online or recently active
 * @returns {Promise<number>} Count of online devices
 */
export async function getDevicesOnline() {
  const query = `
    SELECT COUNT(DISTINCT device_id) as devices_online
    FROM hls_glucosphere.cgm.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 1 DAY
      FROM hls_glucosphere.cgm.gold_patient_device_readings
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
        if (firstRow.values && firstRow.values.length > 0) {
          const count = parseInt(firstRow.values[0].string_value, 10);
          console.log('✅ Devices online from database:', count);
          return count;
        }
      }
    }
    
    console.warn('Could not parse devices online from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get devices online:', error);
    return null;
  }
}

/**
 * Get count of high risk alerts (patients with out-of-range readings in recent window)
 * @returns {Promise<number>} Count of high risk patients
 */
export async function getHighRiskAlerts() {
  const query = `
    SELECT COUNT(DISTINCT patient_id) as high_risk_patients
    FROM hls_glucosphere.cgm.gold_patient_device_readings
    WHERE glucose_out_of_range = 1
      AND time >= (
        SELECT MAX(time) - INTERVAL 24 HOUR
        FROM hls_glucosphere.cgm.gold_patient_device_readings
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
        if (firstRow.values && firstRow.values.length > 0) {
          const count = parseInt(firstRow.values[0].string_value, 10);
          console.log('✅ High risk alerts from database:', count);
          return count;
        }
      }
    }
    
    console.warn('Could not parse high risk alerts from response:', result);
    return null;
  } catch (error) {
    console.error('Failed to get high risk alerts:', error);
    return null;
  }
}

export default { getActivePatients, getDevicesOnline, getHighRiskAlerts };
