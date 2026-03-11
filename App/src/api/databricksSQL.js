// Databricks DBSQL MCP Server API Client
// Based on: https://docs.databricks.com/aws/en/generative-ai/mcp/managed-mcp

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
  const query = 'SELECT COUNT(DISTINCT device_id) as device_count FROM ws_ward_pixels_catalog.glucosphere.silver_patient_registry';
  
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
  const query = `
    SELECT 
      device_model as device_type, 
      CAST(firmware_version AS STRING) as firmware_version,
      COUNT(*) as out_of_range_events 
    FROM ws_ward_pixels_catalog.glucosphere.gold_patient_device_readings 
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
  const query = `
    SELECT 
      device_id,
      TIMESTAMPDIFF(MINUTE, time, (SELECT MAX(time) FROM ws_ward_pixels_catalog.glucosphere.gold_patient_device_readings)) as minutes_since_last_reading,
      patient_id,
      device_model as device_type,
      CAST(firmware_version AS STRING) as firmware_version,
      glucose as glucose_value
    FROM 
      ws_ward_pixels_catalog.glucosphere.gold_patient_device_readings
    WHERE glucose_out_of_range = 1
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
  const query = `
    SELECT 
      device_model as device_type,
      CAST(firmware_version AS STRING) as firmware_version,
      region,
      SUM(glucose_out_of_range) as total_oor_events,
      COUNT(*) as total_events,
      ROUND(AVG(CASE WHEN glucose_out_of_range = 1 THEN 100.0 ELSE 0.0 END), 2) as avg_oor_rate_pct,
      COUNT(DISTINCT DATE(time)) as days_tracked
    FROM ws_ward_pixels_catalog.glucosphere.gold_patient_device_readings
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

export default { executeSQLQuery, getDistinctDeviceCount, getDeviceHeatmapData, getOutOfRangeDevices, getDevicePatternAlerts };

