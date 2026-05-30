// Databricks Multi-Agent Supervisor API Client
// Authentication and endpoint routing are handled by the Flask backend (app.py).
// The frontend always calls /api/agent/query — never directly to Databricks.

/**
 * ALWAYS use the backend proxy to avoid CORS issues.
 * The Flask backend handles authentication and forwards requests to Databricks.
 * This works both locally (Vite proxy → Flask) and in production (Flask serves both app and API).
 */
export const callMultiAgentSupervisor = async (message, conversationHistory = [], conversationId = null) => {
  // Always use the backend proxy route - Flask handles the Databricks API call
  const endpoint_url = '/api/agent/query';
  
  // Build the messages array
  const messages = [
    ...conversationHistory.map(msg => ({
      role: msg.role,
      content: msg.content
    })),
    {
      role: 'user',
      content: message
    }
  ];

  const requestPayload = {
    messages: messages,
    conversation_id: conversationId
  };
  
  console.log('🔍 API Request Details:');
  console.log('Endpoint:', endpoint_url);
  console.log('Payload:', JSON.stringify(requestPayload, null, 2));
  console.log('Using backend proxy - auth handled server-side');
  
  // Headers - no Authorization needed, backend handles it
  const headers = {
    'Content-Type': 'application/json'
  };
  
  try {
    const response = await fetch(endpoint_url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(requestPayload)
    });

    console.log('📥 Response Status:', response.status, response.statusText);
    
    if (!response.ok) {
      // Try to get error details from response body
      let errorDetails;
      const contentType = response.headers.get('content-type');
      try {
        // Only read the body once based on content type
        if (contentType && contentType.includes('application/json')) {
          errorDetails = await response.json();
          console.error('❌ Error Response Body:', errorDetails);
        } else {
          errorDetails = await response.text();
          console.error('❌ Error Response Text:', errorDetails);
        }
      } catch (e) {
        console.error('❌ Could not parse error response:', e);
        errorDetails = 'Could not parse error response';
      }
      
      throw new Error(`API call failed: ${response.status} ${response.statusText}${errorDetails ? ' - ' + JSON.stringify(errorDetails) : ''}`);
    }

    const data = await response.json();
    console.log('✅ Response Data:', data);
    return data;
  } catch (error) {
    console.error('❌ Error calling multi-agent supervisor:', error);
    console.error('Error type:', error.name);
    console.error('Error message:', error.message);
    
    // Enhance error message for common issues
    if (error.message.includes('Failed to fetch')) {
      throw new Error('Failed to fetch: Unable to connect to backend API. Please ensure the Flask backend is running and accessible.');
    }
    
    throw error;
  }
};

export default {};

