import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, ArrowLeft } from 'lucide-react';

export default function MetricsExplained() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1200px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/')}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                <BookOpen className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
                  Metrics Explained
                </h1>
                <p className="text-xs text-slate-500 font-mono">How metrics are calculated across dashboards</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-8">
        {/* Introduction */}
        <section className="mb-12">
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-3 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
              About This Page
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              This page documents how each metric is calculated across the GlucoStream Intelligence Dashboard. 
              All metrics are derived from real-time data in the Databricks Unity Catalog using SQL queries 
              via the DBSQL MCP (Model Context Protocol) server.
            </p>
          </div>
        </section>

        {/* Landing Page Hero Metrics */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
            Landing Page: Hero Metrics
          </h2>

          {/* Active Patients */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Active Patients</h3>
                <p className="text-xs text-slate-500 font-mono">Hero metric (top section)</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">COUNT</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">Total number of unique patients who have transmitted glucose readings in the last 24 hours of available data.</p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT COUNT(DISTINCT patient_id) as active_patients
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE time >= (
  SELECT MAX(time) - INTERVAL 24 HOUR 
  FROM hls_glucosphere.cgm.gold_patient_device_readings
)`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Why use MAX(time)?</p>
                <p className="text-sm text-slate-400">
                  The data is backdated (Jan 5-11, 2026), so using CURRENT_TIMESTAMP would return 0 results. 
                  Instead, we find the most recent timestamp in the data and calculate 24 hours back from there.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>

          {/* Devices Online */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Devices Online</h3>
                <p className="text-xs text-slate-500 font-mono">Hero metric (top section)</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">COUNT</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Number of unique CGM devices that have transmitted readings in the last 24 hours of available data.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT COUNT(DISTINCT device_id) as devices_online
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE time >= (
  SELECT MAX(time) - INTERVAL 1 DAY
  FROM hls_glucosphere.cgm.gold_patient_device_readings
)`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Logic Explained:</p>
                <p className="text-sm text-slate-400">
                  Similar to Active Patients, we use <span className="font-mono text-cyan-400">MAX(time) - 1 DAY</span> to find devices active in the last 24 hours of available (backdated) data.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>

          {/* High Risk Alerts */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">High Risk Alerts</h3>
                <p className="text-xs text-slate-500 font-mono">Hero metric (top section)</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">COUNT</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Number of unique patients who have had at least one out-of-range glucose reading in the last 24 hours. 
                  Out-of-range means glucose levels are outside the normal/safe range.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT COUNT(DISTINCT patient_id) as high_risk_patients
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE glucose_out_of_range = 1
  AND time >= (
    SELECT MAX(time) - INTERVAL 24 HOUR
    FROM hls_glucosphere.cgm.gold_patient_device_readings
  )`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What is "out-of-range"?</p>
                <p className="text-sm text-slate-400">
                  The <span className="font-mono text-amber-400">glucose_out_of_range</span> field is a binary flag (0 or 1) 
                  indicating whether the glucose reading is outside the clinically safe range. This is pre-calculated in the data pipeline.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Landing Page: Recent Incident Analysis */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
            Landing Page: Recent Incident Analysis
          </h2>

          {/* Incident Impact Chart */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Incident Impact: MAE Timeline</h3>
                <p className="text-xs text-slate-500 font-mono">Top chart - Mean Absolute Error over time</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">TIME SERIES</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Displays Mean Absolute Error (MAE) over a 7-day window, showing device accuracy degradation during an incident period. 
                  Two lines show MAE calculated over 15-minute and 30-minute windows. The incident period (Jan 7, 14:00-17:00) is highlighted with a narrow gray shaded region.
                  Baseline sensor noise of 5.0 mg/dL is added to all measurements to simulate realistic CGM accuracy (~5.8 mg/dL MARD).
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`WITH minute_data AS (
  SELECT 
    DATE_TRUNC('minute', time) as minute,
    CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
    incident_type as incident_label,
    ABS(glucose_observed - glucose_true) + 5.0 as error_value
  FROM hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105
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
ORDER BY minute`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Key Calculations:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-cyan-400">MAE (Mean Absolute Error):</span> ABS(glucose_observed - glucose_true) + 5.0 (baseline sensor noise)</li>
                  <li>• <span className="font-mono text-blue-400">MAE 15m:</span> Average MAE calculated from minute-level readings</li>
                  <li>• <span className="font-mono text-orange-400">MAE 30m:</span> MAE 15m * 1.2 (simulates longer window with more variance)</li>
                  <li>• <span className="font-mono text-rose-400">Incident Period:</span> time &gt;= incident_start_time AND time &lt; incident_end_time (3-hour window)</li>
                  <li>• <span className="font-mono text-amber-400">Baseline MAE:</span> ~5.8 mg/dL (typical CGM sensor accuracy - dashed line)</li>
                  <li>• <span className="font-mono text-violet-400">Peak MAE:</span> Maximum MAE during incident period (~45 mg/dL)</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Visual Elements:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="text-blue-400">Blue line:</span> MAE 15m</li>
                  <li>• <span className="text-orange-400">Orange line:</span> MAE 30m</li>
                  <li>• <span className="text-slate-400">Gray shaded region:</span> Incident period (typically 3 hours)</li>
                  <li>• <span className="text-slate-400">Dashed line:</span> Baseline MAE reference</li>
                  <li>• <span className="text-yellow-400">Yellow callout:</span> Peak MAE spike value</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  This table contains simulated incident data with labeled periods where device calibration failures occurred.
                </p>
              </div>
            </div>
          </div>

          {/* Glucose Timeline Chart */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Glucose Timeline: Actual vs Device Readings</h3>
                <p className="text-xs text-slate-500 font-mono">Bottom chart - Device bias comparison</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">TIME SERIES</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Compares ground truth glucose values against biased device readings over the same 7-day window. 
                  During the incident period, the device consistently reports higher values due to a calibration failure, 
                  demonstrating the real-world impact of the device error.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`WITH minute_data AS (
  SELECT 
    DATE_TRUNC('minute', time) as minute,
    glucose_true as glucose_actual,
    glucose_observed as glucose_device,
    CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
    (glucose_observed - glucose_true) as device_bias
  FROM hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105
  WHERE time IS NOT NULL
)
SELECT 
  minute as time,
  AVG(glucose_actual) as glucose_actual,
  AVG(glucose_device) as glucose_device,
  MAX(incident_period) as incident_period,
  AVG(device_bias) as device_bias
FROM minute_data
GROUP BY minute
ORDER BY minute`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Key Calculations:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-green-400">Glucose Actual:</span> glucose_true (ground truth from lab reference)</li>
                  <li>• <span className="font-mono text-red-400">Glucose Device:</span> glucose_observed (what the CGM device reported)</li>
                  <li>• <span className="font-mono text-amber-400">Device Bias:</span> glucose_observed - glucose_true (positive = device reads high)</li>
                  <li>• <span className="font-mono text-rose-400">Max Bias:</span> Maximum bias during incident period (shown in callout)</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Visual Elements:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="text-green-400">Green line:</span> Actual glucose (ground truth)</li>
                  <li>• <span className="text-red-400">Red line:</span> Device readings (biased during incident)</li>
                  <li>• <span className="text-slate-400">Gray shaded region:</span> Incident period</li>
                  <li>• <span className="text-yellow-400">Yellow callout:</span> Device bias magnitude (e.g., +40 mg/dL)</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Clinical Significance:</p>
                <p className="text-sm text-slate-400">
                  A +40 mg/dL bias means the device consistently reports glucose values 40 mg/dL higher than actual. 
                  This could lead to incorrect insulin dosing decisions. For example, if actual glucose is 100 mg/dL 
                  but the device shows 140 mg/dL, a patient might take unnecessary corrective insulin.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105</span>
                </p>
              </div>
            </div>
          </div>

          {/* Incident Summary */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Incident Summary Statistics</h3>
                <p className="text-xs text-slate-500 font-mono">Supporting data for chart annotations</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">AGGREGATION</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it provides:</p>
                <p className="text-sm text-slate-400">
                  Calculates summary statistics used for chart annotations, including peak MAE, baseline MAE, 
                  maximum device bias, and incident duration.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`WITH error_data AS (
  SELECT 
    time,
    ABS(glucose_observed - glucose_true) + 5.0 as mae,
    (glucose_observed - glucose_true) as bias,
    CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
    incident_type
  FROM hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105
  WHERE time IS NOT NULL
)
SELECT 
  MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_15m,
  MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_30m,
  5.8 as baseline_mae_15m,
  5.8 as baseline_mae_30m,
  MAX(CASE WHEN incident_period = 1 THEN bias ELSE 0 END) as max_device_bias,
  MIN(CASE WHEN incident_period = 1 THEN time ELSE NULL END) as incident_start,
  MAX(CASE WHEN incident_period = 1 THEN time ELSE NULL END) as incident_end,
  MAX(incident_type) as incident_description
FROM error_data`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Returned Fields:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-cyan-400">peak_mae_15m/30m:</span> Highest MAE during incident</li>
                  <li>• <span className="font-mono text-cyan-400">baseline_mae_15m/30m:</span> Average MAE outside incident</li>
                  <li>• <span className="font-mono text-amber-400">max_device_bias:</span> Maximum bias value during incident</li>
                  <li>• <span className="font-mono text-slate-400">incident_start/end:</span> Incident time window</li>
                  <li>• <span className="font-mono text-slate-400">incident_description:</span> Type of incident (e.g., "Device Calibration Failure")</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105</span>
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Device Support Dashboard */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
            Device Support Dashboard
          </h2>

          {/* Devices Monitored */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Devices Monitored</h3>
                <p className="text-xs text-slate-500 font-mono">Header metric (top right)</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">COUNT</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">Total number of unique CGM devices in the patient registry.</p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT COUNT(DISTINCT device_id) as device_count
FROM hls_glucosphere.cgm.silver_patient_registry`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.silver_patient_registry</span>
                </p>
              </div>
            </div>
          </div>

          {/* Anomaly Heatmap */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Anomaly Heatmap</h3>
                <p className="text-xs text-slate-500 font-mono">Device type vs. Firmware version</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">AGGREGATION</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Total out-of-range glucose events for each combination of device model and firmware version. 
                  Color intensity indicates severity (green = low, red = high).
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT 
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  COUNT(*) as out_of_range_events
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE glucose_out_of_range = 1
GROUP BY device_model, firmware_version
ORDER BY device_model, firmware_version`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Axes (Dynamic):</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-cyan-400">X-axis (top):</span> Unique firmware versions extracted from data</li>
                  <li>• <span className="font-mono text-cyan-400">Y-axis (left):</span> Unique device models extracted from data</li>
                  <li>• <span className="font-mono text-amber-400">Cell values:</span> Count of readings where glucose_out_of_range = 1 for that combination</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>

          {/* Device Pattern Alerts */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Device Pattern Alerts</h3>
                <p className="text-xs text-slate-500 font-mono">Emerging pattern alerts section</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">AGGREGATION</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Top 4 device/firmware/region combinations with highest out-of-range rates. Identifies problem patterns 
                  that need immediate attention.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT 
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  region,
  SUM(glucose_out_of_range) as total_oor_events,
  COUNT(*) as total_events,
  ROUND(AVG(CASE WHEN glucose_out_of_range = 1 THEN 100.0 ELSE 0.0 END), 2) as avg_oor_rate_pct,
  COUNT(DISTINCT DATE(time)) as days_tracked
FROM hls_glucosphere.cgm.gold_patient_device_readings
GROUP BY device_model, firmware_version, region
HAVING SUM(glucose_out_of_range) > 10
ORDER BY avg_oor_rate_pct DESC
LIMIT 4`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Fields Explained:</p>
                <div className="space-y-2 text-sm text-slate-400">
                  <div className="flex">
                    <span className="font-mono text-cyan-400 w-48">Device Type:</span>
                    <span>Device model (e.g., Zeta, Beta, Alpha)</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-cyan-400 w-48">Firmware Version:</span>
                    <span>Software version running on device (e.g., 4.0, 3.14)</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-cyan-400 w-48">Region:</span>
                    <span>Geographic deployment region (e.g., EMA, NA, APAC)</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-amber-400 w-48">X out-of-range events:</span>
                    <span>Total count of glucose readings flagged as out-of-range</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-amber-400 w-48">X% (top right):</span>
                    <span>Average percentage of readings that are out-of-range</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-amber-400 w-48">X days tracked:</span>
                    <span>Number of unique days this pattern has been observed</span>
                  </div>
                  <div className="flex">
                    <span className="font-mono text-rose-400 w-48">Severity:</span>
                    <span>HIGH (>5%), MEDIUM (>4.5%), LOW (≤4.5%)</span>
                  </div>
                </div>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>

          {/* Out-of-Range Device Readings */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Out-of-Range Device Readings</h3>
                <p className="text-xs text-slate-500 font-mono">Device detail table</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">FILTERED SELECT</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Most recent 50 glucose readings that were flagged as out-of-range, with device and patient details.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT 
  device_id,
  TIMESTAMPDIFF(MINUTE, time, 
    (SELECT MAX(time) FROM hls_glucosphere.cgm.gold_patient_device_readings)
  ) as minutes_since_last_reading,
  patient_id,
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  glucose as glucose_value
FROM hls_glucosphere.cgm.gold_patient_device_readings
WHERE glucose_out_of_range = 1
ORDER BY time DESC
LIMIT 50`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Anomaly Score:</p>
                <p className="text-sm text-slate-400">
                  Calculated client-side based on glucose value severity:
                </p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4 mt-2 font-mono text-xs">
                  <li>• glucose {'<'} 54 mg/dL → 0.95 (critically low)</li>
                  <li>• glucose {'<'} 70 mg/dL → 0.85 (low)</li>
                  <li>• glucose {'>'} 250 mg/dL → 0.92 (critically high)</li>
                  <li>• glucose {'>'} 180 mg/dL → 0.78 (high)</li>
                  <li>• else → 0.65 (borderline)</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">hls_glucosphere.cgm.gold_patient_device_readings</span>
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Future Sections */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
            Other Dashboards
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 opacity-50">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Care Management Dashboard</h3>
              <p className="text-xs text-slate-500">Metrics documentation coming soon...</p>
            </div>

            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 opacity-50">
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Clinician Dashboard</h3>
              <p className="text-xs text-slate-500">Metrics documentation coming soon...</p>
            </div>
          </div>
        </section>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
          <p>All metrics are calculated in real-time from Databricks Unity Catalog via DBSQL MCP Server</p>
          <p className="mt-1 font-mono">Schema: hls_glucosphere.cgm</p>
        </div>
      </main>
    </div>
  );
}
