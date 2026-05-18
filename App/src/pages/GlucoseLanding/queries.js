// Landing Page Metrics - SQL Queries
// Uses CGM schema data for real-time metrics
//
// All SQL queries here fetch catalog/schema from getConfig() (Flask /api/config
// sourced from app.yaml env vars). NEVER hardcode catalog/schema names inline.

import { executeSQLQuery } from '../../api/databricksSQL';
import { getConfig } from '../../api/config';

/**
 * Get count of active patients (patients with readings in last 24h of available data)
 * @returns {Promise<number>} Count of active patients
 */
export async function getActivePatients() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT COUNT(DISTINCT patient_id) as active_patients
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
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT COUNT(DISTINCT device_id) as devices_online
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE time >= (
      SELECT MAX(time) - INTERVAL 1 DAY
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
 * Get count of patients with at least one device-bias-induced incident in
 * the last 7 days. Cumulative count tied directly to the device-bias story —
 * answers "how many patients had calibration bug events this week?"
 *
 * @returns {Promise<number>} Count of distinct patients with incident_type
 *   set (i.e., a device-bias incident was active for them) in the last 7d
 */
export async function getIncidentAffectedPatients() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT COUNT(DISTINCT patient_id) as incident_affected
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE event_type IS NOT NULL
      AND event_type NOT IN ('in_range')
      AND time >= (
        SELECT MAX(time) - INTERVAL 7 DAY
        FROM ${catalog}.${schema}.gold_patient_device_readings
      )
      AND patient_id IN (
        SELECT DISTINCT patient_id
        FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
        WHERE incident_direction IS NOT NULL
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
          console.log('✅ Device-incident-affected patients (past 7d):', count);
          return count;
        }
      }
    }
    console.warn('Could not parse incident_affected from response:', result);
    return 0;
  } catch (error) {
    console.error('Failed to get incident-affected patients:', error);
    return 0;
  }
}

/**
 * Get count of out-of-range patients in the last 3-hour rolling window.
 *
 * 3h matches an incident-window length so a live incident shifts the count
 * clearly above the natural baseline. With a 24h window the natural diabetic
 * OOR baseline dominates (~943 patients) and an incident only nudges it
 * slightly. 3h gives a baseline of ~495 patients during clean periods and
 * an expected ~800 (baseline + 300-patient cohort) during an active
 * incident — a usable signal-to-noise ratio for a fleet operator's
 * live monitoring tile.
 *
 * @returns {Promise<number>} Count of patients with at least one OOR
 *   reading in the last 3 hours of data
 */
export async function getHighRiskAlerts() {
  const { catalog, schema } = await getConfig();
  const query = `
    SELECT COUNT(DISTINCT patient_id) as high_risk_patients
    FROM ${catalog}.${schema}.gold_patient_device_readings
    WHERE glucose_out_of_range = 1
      AND time >= (
        SELECT MAX(time) - INTERVAL 3 HOUR
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
