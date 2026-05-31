import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Wrench, AlertTriangle, Search, TrendingUp, ChevronDown, ChevronRight, Brain, Loader } from 'lucide-react';
import AgentChatInterface from '../components/AgentChatInterface';
import RegionMap from '../components/RegionMap';
import { getDistinctDeviceCount, getDeviceHeatmapData, getOutOfRangeDevices, getDevicePatternAlerts, getDeviceRegionalDistribution } from '../api/databricksSQL';
import { callMultiAgentSupervisor } from '../api/databricksAgent';
import ReactMarkdown from 'react-markdown';

export default function DeviceSupportDashboard() {
  const navigate = useNavigate();
  const [expandedDevice, setExpandedDevice] = useState(null);
  const [filterModel, setFilterModel] = useState('all');
  const [deviceCount, setDeviceCount] = useState('...');
  const [deviceCountLoading, setDeviceCountLoading] = useState(true);
  const [heatmapData, setHeatmapData] = useState([]);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [firmwareVersions, setFirmwareVersions] = useState([]);
  const [devices, setDevices] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [regions, setRegions] = useState([]);
  const [regionsLoading, setRegionsLoading] = useState(true);
  const [deviceAnalysis, setDeviceAnalysis] = useState({}); // Store analysis for each device
  const [analysisLoading, setAnalysisLoading] = useState({}); // Track loading state per device

  // Scroll to top when component mounts
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Fetch real device count from database
  useEffect(() => {
    const fetchDeviceCount = async () => {
      try {
        setDeviceCountLoading(true);
        const count = await getDistinctDeviceCount();
        if (count !== null) {
          setDeviceCount(count.toLocaleString());
        } else {
          setDeviceCount('0');
        }
      } catch (error) {
        console.error('Failed to fetch device count:', error);
        setDeviceCount('0');
      } finally {
        setDeviceCountLoading(false);
      }
    };

    fetchDeviceCount();
  }, []);

  // Fetch real heatmap data from database
  useEffect(() => {
    const fetchHeatmapData = async () => {
      try {
        setHeatmapLoading(true);
        const data = await getDeviceHeatmapData();
        
        if (data && data.length > 0) {
          setHeatmapData(data);
          
          // Extract unique device types and firmware versions
          const uniqueDeviceTypes = [...new Set(data.map(d => d.device_type))].sort();
          const uniqueFirmwareVersions = [...new Set(data.map(d => d.firmware_version))].sort();
          
          setDeviceTypes(uniqueDeviceTypes);
          setFirmwareVersions(uniqueFirmwareVersions);
          
          console.log('Heatmap data loaded:', data.length, 'rows');
          console.log('Device types:', uniqueDeviceTypes);
          console.log('Firmware versions:', uniqueFirmwareVersions);
        } else {
          // No data available
          setDeviceTypes([]);
          setFirmwareVersions([]);
          setHeatmapData([]);
        }
      } catch (error) {
        console.error('Failed to fetch heatmap data:', error);
        // No fallback - use empty data
        setDeviceTypes([]);
        setFirmwareVersions([]);
        setHeatmapData([]);
      } finally {
        setHeatmapLoading(false);
      }
    };

    fetchHeatmapData();
  }, []);

  // Fetch out-of-range device readings from database
  useEffect(() => {
    const fetchDevices = async () => {
      try {
        setDevicesLoading(true);
        const data = await getOutOfRangeDevices();
        
        if (data && data.length > 0) {
          // Transform data for display
          const transformedDevices = data.map(d => ({
            id: d.device_id,
            patient: d.patient_id,
            model: d.device_type,
            firmware: d.firmware_version,
            status: 'flagged', // All are out-of-range
            lastReading: formatTimeSince(d.minutes_since_last_reading),
            minutesSinceReading: d.minutes_since_last_reading,
            anomalyScore: calculateAnomalyScore(d.glucose_value),
            glucose_value: d.glucose_value
          }));
          
          setDevices(transformedDevices);
          console.log('Devices loaded:', transformedDevices.length);
        } else {
          // No data available
          setDevices([]);
        }
      } catch (error) {
        console.error('Failed to fetch devices:', error);
        // No fallback - use empty data
        setDevices([]);
      } finally {
        setDevicesLoading(false);
      }
    };

    fetchDevices();
  }, []);

  // Helper function to format time since last reading
  const formatTimeSince = (minutes) => {
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  // Helper function to calculate anomaly score based on glucose value
  // Normal range: 70-180 mg/dL
  const calculateAnomalyScore = (glucoseValue) => {
    if (glucoseValue < 54) return 0.95; // Critically low
    if (glucoseValue < 70) return 0.85; // Low
    if (glucoseValue > 250) return 0.92; // Critically high
    if (glucoseValue > 180) return 0.78; // High
    return 0.65; // Borderline
  };

  // Function to get deeper analysis for a specific device reading
  const handleDeeperAnalysis = async (device) => {
    const deviceKey = device.id;
    
    // Set loading state for this specific device
    setAnalysisLoading(prev => ({ ...prev, [deviceKey]: true }));
    
    try {
      // Construct prompt with device context - focusing on device troubleshooting
      const prompt = `Analyze this out-of-range glucose reading from a DEVICE TROUBLESHOOTING perspective (1-2 paragraphs maximum):

Device ID: ${device.id}
Device Model: ${device.model}
Firmware Version: ${device.firmware}
Patient ID: ${device.patient}
Glucose Reading: ${device.glucose_value} mg/dL
Time Since Last Reading: ${device.lastReading}
Status: OUT-OF-RANGE

As a biomedical equipment specialist, analyze:
1. Is this a device malfunction or calibration issue?
2. Are there known issues with this device model or firmware version?
3. Could this be a sensor failure, connectivity problem, or data transmission error?
4. What device diagnostics or troubleshooting steps should be taken?
5. Does this require device replacement, recalibration, or firmware update?

Focus on DEVICE technical issues, not patient clinical care. Provide actionable troubleshooting steps for biomedical technicians.`;

      console.log('Requesting deeper analysis for:', deviceKey);
      
      // Call multi-agent supervisor
      const response = await callMultiAgentSupervisor(prompt);
      
      // Extract the response content
      let analysisText = 'Analysis complete. Please review recommendations.';
      if (response.response) {
        analysisText = response.response;
      } else if (response.choices && response.choices[0]?.message?.content) {
        analysisText = response.choices[0].message.content;
      } else if (response.content) {
        analysisText = response.content;
      } else if (typeof response === 'string') {
        analysisText = response;
      }
      
      // Store analysis result
      setDeviceAnalysis(prev => ({ ...prev, [deviceKey]: analysisText }));
      
      console.log('Analysis completed for:', deviceKey);
    } catch (error) {
      console.error('Error getting deeper analysis:', error);
      setDeviceAnalysis(prev => ({ 
        ...prev, 
        [deviceKey]: `⚠️ Unable to complete analysis: ${error.message}. Please try again or contact support.`
      }));
    } finally {
      setAnalysisLoading(prev => ({ ...prev, [deviceKey]: false }));
    }
  };

  // Fetch regional distribution (geo panel)
  useEffect(() => {
    const fetchRegions = async () => {
      try {
        setRegionsLoading(true);
        const data = await getDeviceRegionalDistribution();
        setRegions(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch regional distribution:', error);
        setRegions([]);
      } finally {
        setRegionsLoading(false);
      }
    };
    fetchRegions();
  }, []);

  // Fetch device pattern alerts from database
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setAlertsLoading(true);
        const data = await getDevicePatternAlerts();
        
        if (data && data.length > 0) {
          // Transform data for display
          const transformedAlerts = data.map(d => ({
            device_type: d.device_type,
            firmware_version: d.firmware_version,
            region: d.region,
            rate_pct: d.avg_oor_rate_pct,
            affected: d.total_oor_events,
            days_tracked: d.days_tracked,
            severity: d.avg_oor_rate_pct > 5.0 ? 'high' : d.avg_oor_rate_pct > 4.5 ? 'medium' : 'low'
          }));
          
          setAlerts(transformedAlerts);
          console.log('Alerts loaded:', transformedAlerts.length);
        } else {
          // No data available
          setAlerts([]);
        }
      } catch (error) {
        console.error('Failed to fetch alerts:', error);
        // No fallback - use empty data
        setAlerts([]);
      } finally {
        setAlertsLoading(false);
      }
    };

    fetchAlerts();
  }, []);

  // Calculate dynamic min/max values for heatmap scaling
  const minOutOfRangeEvents = heatmapData.length > 0 
    ? Math.min(...heatmapData.map(d => d.out_of_range_events))
    : 0;
  
  const maxOutOfRangeEvents = heatmapData.length > 0 
    ? Math.max(...heatmapData.map(d => d.out_of_range_events))
    : 1;

  const getHeatmapColor = (events) => {
    if (events === 0) return 'rgb(51 65 85)'; // slate-700 for no data
    
    // Normalize based on actual data range (min to max), not 0 to max
    const normalized = (events - minOutOfRangeEvents) / (maxOutOfRangeEvents - minOutOfRangeEvents); // 0 to 1
    
    // Color spectrum: green → yellow → orange → red
    if (normalized < 0.25) {
      // Green to Yellow-Green (low events)
      const t = normalized / 0.25; // 0 to 1 within this range
      const r = Math.round(34 + (132 * t));   // 34 (emerald) → 166 (lime)
      const g = Math.round(197 + (23 * t));   // 197 → 220
      const b = Math.round(94 - (44 * t));    // 94 → 50
      return `rgb(${r} ${g} ${b})`;
    } else if (normalized < 0.5) {
      // Yellow-Green to Yellow (medium-low events)
      const t = (normalized - 0.25) / 0.25;
      const r = Math.round(166 + (88 * t));   // 166 → 254 (yellow)
      const g = Math.round(220 + (4 * t));    // 220 → 224
      const b = Math.round(50 - (36 * t));    // 50 → 14
      return `rgb(${r} ${g} ${b})`;
    } else if (normalized < 0.75) {
      // Yellow to Orange (medium-high events)
      const t = (normalized - 0.5) / 0.25;
      const r = Math.round(254 - (3 * t));    // 254 → 251 (orange)
      const g = Math.round(224 - (78 * t));   // 224 → 146
      const b = Math.round(14 - (5 * t));     // 14 → 9
      return `rgb(${r} ${g} ${b})`;
    } else {
      // Orange to Red (high events)
      const t = (normalized - 0.75) / 0.25;
      const r = Math.round(251 - (12 * t));   // 251 → 239 (rose/red)
      const g = Math.round(146 - (78 * t));   // 146 → 68
      const b = Math.round(9 + (59 * t));     // 9 → 68
      return `rgb(${r} ${g} ${b})`;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/')}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                <Wrench className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
                  Device Support Dashboard
                </h1>
                <p className="text-xs text-slate-500 font-mono">Biomedical Engineering & Device Health</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs text-slate-500 font-mono">Devices Monitored</p>
              <p className="text-lg font-mono font-bold text-slate-300">
                {deviceCountLoading ? (
                  <span className="text-slate-500">Loading...</span>
                ) : (
                  deviceCount
                )}
              </p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        {/* Population Overview */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-6 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
            Population Overview
          </h2>
          
          <div className="grid grid-cols-12 gap-6 items-stretch">
            {/* Heatmap */}
            <div data-tour="anomaly-heatmap" className="col-span-5 bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-slate-300 mb-1">Device Out-of-Range Events</h3>
                <p className="text-xs text-slate-500 font-mono">By device type and firmware version</p>
              </div>
              
              <div className="flex gap-4 items-stretch">
                {/* Heatmap grid */}
                <div className="flex-1 min-w-0">
                  {heatmapLoading ? (
                    <div className="flex items-center justify-center h-48 text-slate-500">
                      Loading heatmap data...
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {/* X-axis labels */}
                      <div className="flex items-center gap-3">
                        <div className="w-24" />
                        {firmwareVersions.map(fw => (
                          <div key={fw} className="flex-1 text-center">
                            <span className="text-sm font-mono text-slate-400">{fw}</span>
                          </div>
                        ))}
                      </div>

                      {/* Heatmap cells */}
                      {deviceTypes.map(deviceType => (
                        <div key={deviceType} className="flex items-center gap-3">
                          <div className="w-24 text-sm text-slate-300 font-mono">{deviceType}</div>
                          {firmwareVersions.map(fw => {
                            const data = heatmapData.find(d => d.device_type === deviceType && d.firmware_version === fw);
                            const outOfRangeEvents = data ? data.out_of_range_events : 0;

                            return (
                              <div
                                key={fw}
                                className="flex-1 h-10 rounded-lg cursor-pointer hover:ring-2 hover:ring-cyan-500 hover:ring-offset-2 hover:ring-offset-slate-900 transition-all group relative"
                                style={{
                                  backgroundColor: getHeatmapColor(outOfRangeEvents)
                                }}
                              >
                                <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                                  <div className="bg-slate-950 border border-cyan-500 rounded px-3 py-1.5 text-sm font-mono whitespace-nowrap shadow-xl">
                                    <span className="text-cyan-400 font-bold">{outOfRangeEvents}</span>
                                    <span className="text-slate-400"> events</span>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Vertical legend (colorbar) — to the right of the grid */}
                {!heatmapLoading && (
                  <div className="flex flex-col items-center gap-1 pt-8 shrink-0">
                    <span className="text-[10px] font-mono text-rose-400 font-bold">{maxOutOfRangeEvents}</span>
                    <span className="text-[10px] font-mono text-slate-500 mb-0.5">High</span>
                    <div className="flex flex-col rounded overflow-hidden">
                      {[1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1, 0.0].map((normalized, i) => (
                        <div
                          key={i}
                          className="w-3.5 h-4"
                          style={{ backgroundColor: getHeatmapColor(minOutOfRangeEvents + (normalized * (maxOutOfRangeEvents - minOutOfRangeEvents))) }}
                        />
                      ))}
                    </div>
                    <span className="text-[10px] font-mono text-slate-500 mt-0.5">Low</span>
                    <span className="text-[10px] font-mono text-cyan-400 font-bold">{minOutOfRangeEvents}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Regional distribution (geo) */}
            <div className="col-span-3 bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-slate-300 mb-1">Regional Distribution</h3>
                <p className="text-xs text-slate-500 font-mono">Footprint × out-of-range volume</p>
              </div>
              <div className="flex-1 flex flex-col justify-center">
                {regionsLoading ? (
                  <div className="flex items-center justify-center h-48 text-slate-500">Loading regions...</div>
                ) : (
                  <RegionMap regions={regions} />
                )}
              </div>
            </div>

            {/* Device Pattern Alerts */}
            <div className="col-span-4 bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
              <div className="mb-4">
                <h3 className="text-sm font-medium text-slate-300 mb-1">Device Pattern Alerts</h3>
                <p className="text-xs text-slate-500 font-mono">Detected device performance patterns</p>
              </div>
              
              {alertsLoading ? (
                <div className="flex items-center justify-center h-48 text-slate-500">
                  Loading device patterns...
                </div>
              ) : alerts.length === 0 ? (
                <div className="flex items-center justify-center h-48 text-slate-500">
                  No alerts at this time
                </div>
              ) : (
                (() => {
                  // Compact ranked list (no bars) — complements the heatmap matrix instead
                  // of echoing its colored bars. Top out-of-range patterns by event volume.
                  const dotColor = (s) => s === 'high' ? 'bg-rose-400' : s === 'medium' ? 'bg-amber-400' : 'bg-yellow-400';
                  return (
                    <ol className="flex-1 flex flex-col justify-between divide-y divide-slate-800/70">
                      {[...alerts].sort((a, b) => b.affected - a.affected).map((alert, idx) => (
                        <li key={idx} className="flex items-center gap-3 py-3">
                          <span className="text-xs font-mono text-slate-600 w-4 text-right shrink-0">{idx + 1}</span>
                          <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor(alert.severity)}`} title={alert.severity} />
                          <span className="text-sm font-mono text-slate-200 truncate flex-1 min-w-0">
                            {alert.device_type} {alert.firmware_version}<span className="text-slate-600"> · {alert.region} · {alert.days_tracked}d tracked</span>
                          </span>
                          <span className="text-sm font-mono text-amber-400 shrink-0">{alert.affected.toLocaleString()}</span>
                          <span className="text-xs font-mono text-slate-500 shrink-0 w-14 text-right">{alert.rate_pct}%</span>
                        </li>
                      ))}
                    </ol>
                  );
                })()
              )}
            </div>
          </div>
        </section>

        {/* Device Troubleshooting Intelligence - AI Chat */}
        <section className="mb-8">
          <h2 className="text-lg font-semibold mb-6 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
            Device Troubleshooting Intelligence
          </h2>
          
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <AgentChatInterface />
          </div>
        </section>

        {/* Device Detail Table */}
        <section>
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
                Out-of-Range Device Readings
              </h2>
              <p className="text-xs text-slate-500 font-mono mt-1">Real-time flagged readings from patient devices</p>
            </div>
            <select 
              value={filterModel}
              onChange={(e) => setFilterModel(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-300 font-mono focus:outline-none focus:border-cyan-500"
            >
              <option value="all">All Models</option>
              {deviceTypes.map(model => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
          </div>
          
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden">
            {devicesLoading ? (
              <div className="flex items-center justify-center h-48 text-slate-500">
                Loading device readings...
              </div>
            ) : (
              <div className="max-h-[600px] overflow-y-auto">
                <table className="w-full">
                  <thead className="sticky top-0 bg-slate-900 z-10">
                    <tr className="border-b border-slate-800">
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Device ID</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Patient</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Model</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Firmware</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Last Reading</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Glucose</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Risk Score</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {devices
                      .filter(device => filterModel === 'all' || device.model === filterModel)
                      .map((device, idx) => (
                  <React.Fragment key={idx}>
                    <tr 
                      className="border-b border-slate-800 hover:bg-slate-800/50 transition-colors cursor-pointer"
                      onClick={() => setExpandedDevice(expandedDevice === idx ? null : idx)}
                    >
                      <td className="px-4 py-3 text-sm font-mono text-cyan-400">{device.id}</td>
                      <td className="px-4 py-3 text-sm font-mono text-slate-400">{device.patient}</td>
                      <td className="px-4 py-3 text-sm text-slate-300">{device.model}</td>
                      <td className="px-4 py-3 text-sm font-mono text-slate-400">{device.firmware}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 rounded-full text-xs font-mono bg-rose-500/10 text-rose-400 border border-rose-500/30">
                          OUT-OF-RANGE
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm font-mono text-slate-400">{device.lastReading}</td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-mono font-bold ${
                          device.glucose_value < 70 ? 'text-amber-400' : 'text-rose-400'
                        }`}>
                          {device.glucose_value ? `${device.glucose_value} mg/dL` : 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div 
                              className={`h-full ${
                                device.anomalyScore > 0.85 ? 'bg-rose-500' :
                                device.anomalyScore > 0.7 ? 'bg-amber-500' :
                                'bg-yellow-500'
                              }`}
                              style={{ width: `${device.anomalyScore * 100}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono text-slate-400 w-10">{(device.anomalyScore * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {expandedDevice === idx ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
                      </td>
                    </tr>
                    
                    {expandedDevice === idx && (
                      <tr className="border-b border-slate-800 bg-slate-900">
                        <td colSpan="9" className="px-4 py-4">
                          <div className="grid grid-cols-2 gap-6">
                            {/* Reading Details */}
                            <div>
                              <h4 className="text-sm font-medium text-slate-300 mb-3">Reading Details</h4>
                              <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Glucose Value:</span>
                                  <span className={`font-mono font-bold ${
                                    device.glucose_value < 70 ? 'text-amber-400' : 'text-rose-400'
                                  }`}>
                                    {device.glucose_value} mg/dL
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Range Status:</span>
                                  <span className="text-slate-300">
                                    {device.glucose_value < 54 ? 'Critically Low (<54)' :
                                     device.glucose_value < 70 ? 'Low (54-70)' :
                                     device.glucose_value > 250 ? 'Critically High (>250)' :
                                     'High (180-250)'}
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Time Since Reading:</span>
                                  <span className="text-slate-300 font-mono">{device.lastReading}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Risk Score:</span>
                                  <span className="text-slate-300 font-mono">{(device.anomalyScore * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                              
                              <div className="mt-4 p-3 bg-rose-500/5 border border-rose-500/20 rounded text-xs text-rose-300">
                                ⚠️ <strong>Action Required:</strong> This reading is outside normal range. Consider patient notification and clinical review.
                              </div>
                            </div>
                            
                            {/* Clinical Analysis */}
                            <div>
                              <h4 className="text-sm font-medium text-slate-300 mb-3">Clinical Analysis</h4>
                              
                              {!deviceAnalysis[device.id] && !analysisLoading[device.id] && (
                                <div className="text-center py-8">
                                  <Brain className="w-12 h-12 text-cyan-400 mx-auto mb-3 opacity-50" />
                                  <p className="text-sm text-slate-400 mb-4">
                                    Get AI-powered clinical analysis and recommendations<br/>
                                    for this patient based on device readings and medical context.
                                  </p>
                                  <button 
                                    onClick={() => handleDeeperAnalysis(device)}
                                    className="px-4 py-2 bg-cyan-500 hover:bg-cyan-600 border border-cyan-400 rounded-lg text-sm text-white font-medium transition-colors flex items-center gap-2 mx-auto"
                                  >
                                    <Brain className="w-4 h-4" />
                                    Deeper Analysis
                                  </button>
                                </div>
                              )}
                              
                              {analysisLoading[device.id] && (
                                <div className="text-center py-8">
                                  <Loader className="w-8 h-8 text-cyan-400 mx-auto mb-3 animate-spin" />
                                  <p className="text-sm text-slate-400">
                                    Analyzing patient data and device readings...<br/>
                                    <span className="text-xs text-slate-500">This may take 30-60 seconds</span>
                                  </p>
                                </div>
                              )}
                              
                              {deviceAnalysis[device.id] && !analysisLoading[device.id] && (
                                <div>
                                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-sm text-slate-300 prose prose-invert prose-sm max-w-none">
                                    <ReactMarkdown>{deviceAnalysis[device.id]}</ReactMarkdown>
                                  </div>
                                  <div className="mt-4 flex gap-2">
                                    <button 
                                      onClick={() => handleDeeperAnalysis(device)}
                                      className="px-3 py-2 bg-slate-800 border border-slate-700 rounded text-xs text-slate-400 hover:bg-slate-700 transition-colors flex items-center gap-1"
                                    >
                                      <Brain className="w-3 h-3" />
                                      Refresh Analysis
                                    </button>
                                    <button
                                      disabled
                                      title="Not yet implemented — planned: comparative-stats chart (this device vs fleet)"
                                      className="px-3 py-2 bg-slate-800/40 border border-slate-700 rounded text-xs text-slate-500 italic cursor-not-allowed"
                                    >
                                      Export to Chart (placeholder)
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                    </React.Fragment>
                  ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

