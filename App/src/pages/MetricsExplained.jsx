import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, ArrowLeft } from 'lucide-react';
import { getConfig } from '../api/config';
import fig4DistributionPng from '../assets/fig4_distribution_comparison_4panel.png';

export default function MetricsExplained() {
  const navigate = useNavigate();

  // Fetch catalog/schema from Flask /api/config so the SQL examples + display
  // text shown to users reflect the workspace this app is deployed to.
  // NEVER hardcode catalog/schema inline.
  const [catalog, setCatalog] = useState('');
  const [schema, setSchema] = useState('');
  useEffect(() => {
    getConfig().then(cfg => {
      setCatalog(cfg.catalog || '');
      setSchema(cfg.schema || '');
    }).catch(err => console.error('Failed to load config:', err));
  }, []);

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
            <p className="text-sm text-slate-400 leading-relaxed mt-3">
              <span className="text-amber-300 font-medium">Note on demo data:</span> patient identifiers,
              device metadata, and the ±40 mg/dL device-calibration-bug incidents shown across these charts
              are <span className="text-amber-300 font-medium">simulated</span> for demo purposes — there is
              no real adverse-event PHI. The underlying CGM glucose signal pattern is seeded from a real T1D
              dataset (HUPA-UCM) in the default <span className="font-mono text-cyan-400">real_from_source</span>{' '}
              baseline mode, so the forecasting model + monitoring stack are exercised against realistic clinical
              extremes (≈6.6% hypo, max 444 mg/dL). A fully-synthetic baseline mode is also available for clean
              demos without external data dependency — see <span className="font-mono text-cyan-400">baseline_source</span>{' '}
              in the deploy docs.
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
FROM ${catalog}.${schema}.gold_patient_device_readings
WHERE time >= (
  SELECT MAX(time) - INTERVAL 24 HOUR 
  FROM ${catalog}.${schema}.gold_patient_device_readings
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
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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
FROM ${catalog}.${schema}.gold_patient_device_readings
WHERE time >= (
  SELECT MAX(time) - INTERVAL 1 DAY
  FROM ${catalog}.${schema}.gold_patient_device_readings
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
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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
FROM ${catalog}.${schema}.gold_patient_device_readings
WHERE glucose_out_of_range = 1
  AND time >= (
    SELECT MAX(time) - INTERVAL 24 HOUR
    FROM ${catalog}.${schema}.gold_patient_device_readings
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
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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

          {/* Why this monitoring stack matters — frames the 3 incident charts that follow */}
          <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-semibold text-cyan-300 mb-1">Why this monitoring stack matters</h3>
                <p className="text-xs text-slate-500 font-mono">Platform value — what the three charts below detect</p>
              </div>
              <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 rounded text-xs font-mono text-cyan-300">FRAMING</span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Real-world CGM device calibration failures span <span className="font-medium">both directions</span> — Abbott FreeStyle Libre has FDA recalls on record for both <span className="text-red-300 font-medium">over-reading</span> and <span className="text-blue-300 font-medium">under-reading</span> sensors, each clinically dangerous in opposite ways (over-read → unwarranted corrective insulin → hypo risk; under-read → missed real highs → delayed correction). A fleet-monitoring layer that catches either failure mode with a single <span className="font-medium">direction-agnostic</span> metric (MAE rolling-window) and then lets operators drill in to <span className="font-medium">which</span> direction each device drifted (<span className="font-mono text-cyan-400">incident_direction</span> field on the alerts table) is what closes the loop from fleet-wide alert → per-device action.
            </p>
            <p className="text-sm text-slate-300 leading-relaxed mt-3">
              The three charts below walk through that detection chain:
              <span className="block ml-4 mt-1">(1) <span className="text-cyan-300 font-medium">MAE Timeline</span> — catches the magnitude (fleet-vs-affected dilution view).</span>
              <span className="block ml-4">(2) <span className="text-cyan-300 font-medium">How MAE alerts are triggered</span> — distribution shift explains <em>why</em> MAE spiked.</span>
              <span className="block ml-4">(3) <span className="text-cyan-300 font-medium">Device Calibration Bias Over Time</span> — signed-bias delta reveals <em>which</em> direction each cohort drifted.</span>
            </p>
          </div>

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
ORDER BY minute`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Key Calculations:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-cyan-400">MAE (Mean Absolute Error):</span> ABS(glucose_observed - glucose_true) + 5.0 (baseline sensor noise) — direction-agnostic, catches both positive and negative bias</li>
                  <li>• <span className="font-mono text-blue-400">MAE Fleet-wide:</span> AVG across ALL patients — diluted to ~17 mg/dL during incident because only ~30% are affected</li>
                  <li>• <span className="font-mono text-orange-400">MAE Affected-only:</span> AVG filtered to affected patients (has_incident = 1) — shows the TRUE device-error magnitude ~45 mg/dL during incident</li>
                  <li>• <span className="font-mono text-amber-400">Dilution gap (45 → 17):</span> Why patient-level monitoring matters — fleet-wide averages mask serious per-device errors</li>
                  <li>• <span className="font-mono text-rose-400">Incident Period:</span> time &gt;= incident_start_time AND time &lt; incident_end_time (3-hour window)</li>
                  <li>• <span className="font-mono text-amber-400">Baseline MAE:</span> ~5.8 mg/dL (typical CGM sensor accuracy - dashed line)</li>
                  <li>• <span className="font-mono text-violet-400">Peak MAE:</span> Maximum MAE during incident period (~45 mg/dL)</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Visual Elements:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="text-blue-400">Blue line:</span> MAE Fleet-wide (diluted across all patients — ~17 mg/dL peak)</li>
                  <li>• <span className="text-orange-400">Orange line:</span> MAE Affected-only (true bias magnitude — ~45 mg/dL peak)</li>
                  <li>• <span className="text-slate-400">Gray shaded region:</span> Incident period (typically 3 hours)</li>
                  <li>• <span className="text-slate-400">Dashed line:</span> Baseline MAE reference</li>
                  <li>• <span className="text-yellow-400">Yellow callout:</span> Peak MAE spike value</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">{catalog}.{schema}.pseudo_incident_7d_labeled</span>
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  This table contains simulated incident data with labeled periods where device calibration failures occurred.
                </p>
              </div>
            </div>
          </div>

          {/* How MAE alerts are triggered — distribution shift view (4-panel snapshot from dual_05 notebook) */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">How MAE alerts are triggered</h3>
                <p className="text-xs text-slate-500 font-mono">Distribution shift view — why MAE spikes signal device drift</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">DISTRIBUTION</span>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Why MAE spikes signal device drift:</p>
                <p className="text-sm text-slate-400 leading-relaxed">
                  Positive-bias cohort (<span className="text-red-400 font-medium">red</span>) shifts UP into hyperglycemic range (&gt;180 mg/dL) — 42% of readings cross the hyper threshold vs ~22% baseline. Negative-bias cohort (<span className="text-blue-400 font-medium">blue</span>) shifts DOWN into hypoglycemic range (&lt;70 mg/dL) — 26% cross hypo vs ~6% baseline. The directional distribution shift drives a 6× MAE spike fleetwide, which the rolling-window monitor (MAE Timeline chart above) catches in real time and surfaces as an alert.
                </p>
                <p className="text-xs text-slate-500 italic mt-2">
                  (The ±40 mg/dL incident itself is a <span className="text-amber-300">simulated</span> calibration bug injected into the demo data for illustration — see the page intro for full provenance.)
                </p>
              </div>
              <div className="my-4">
                <img
                  src={fig4DistributionPng}
                  alt="4-panel glucose distribution comparison: baseline (darkgray), clean period (mediumturquoise), Inc+ cohort (red, over-reads), Inc- cohort (blue, under-reads). Histograms, bar chart, CDF, and box plot show how each incident direction shifts the distribution and how the shift maps to hypo/hyper threshold crossings."
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/50"
                />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Generated by job{' '}
                  <a href="https://fevm-mmt-aws-usw2.cloud.databricks.com/jobs/911600926545" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">
                    glucosphere-full-setup-mmt_aws_usw2
                  </a>
                  {' '}— this snapshot from{' '}
                  <a href="https://fevm-mmt-aws-usw2.cloud.databricks.com/?o=7474658466980277#job/464619060436574/run/672389097750401" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">
                    run 899387466814174
                  </a>
                  {' '}on 2026-05-19.
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Notebook: <span className="text-cyan-400">dual_05_CGM_Incident_Inference_DeviceCalibrationBug_Bidirectional</span> 4-class distribution comparison cell. PNG has transparent background so it inherits the surrounding card color in any theme.
                </p>
              </div>
            </div>
          </div>

          {/* Glucose Timeline Chart */}
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Device Calibration Bias Over Time (±40 mg/dL Bidirectional)</h3>
                <p className="text-xs text-slate-500 font-mono">Bottom chart - Signed bias delta per direction cohort</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">TIME SERIES</span>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Signed device bias <span className="font-mono">(observed − true)</span> averaged per direction cohort over the same 7-day window. With the two-window mirror design (2026-05-18), the positive-bias cohort (Alpha/Gamma devices) spikes to +40 mg/dL during Window 1 on Day 2, while the negative-bias cohort (Beta/Delta devices) drops to −40 mg/dL during Window 2 on Day 5. Outside each cohort's own window, that cohort's line sits at ≈ 0 (devices match ground truth) — diurnal glucose fluctuations cancel in the subtraction. Both directions are clinically relevant calibration failures and both are detected by the same direction-agnostic MAE monitor in the top chart.
                </p>
                <p className="text-xs text-slate-500 italic mt-2">
                  (The ±40 mg/dL two-window incident is a <span className="text-amber-300">simulated</span> adverse device-calibration scenario injected into the demo data — see the page intro for full provenance.)
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`WITH minute_data AS (
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
ORDER BY minute`}
                </pre>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Key Calculations:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-slate-300">signed_bias:</span> <span className="font-mono">glucose_observed − glucose_true</span> at every reading. Positive = device over-reads, negative = device under-reads. Subtraction cancels the diurnal glucose component, leaving pure device error.</li>
                  <li>• <span className="font-mono text-red-400">bias_positive:</span> AVG(signed_bias) WHERE incident_direction = 'positive' — the cohort whose devices over-read by +40 mg/dL during incident. ≈ 0 outside incident, ≈ +40 inside.</li>
                  <li>• <span className="font-mono text-blue-400">bias_negative:</span> AVG(signed_bias) WHERE incident_direction = 'negative' — the cohort whose devices under-read by −40 mg/dL during incident. ≈ 0 outside incident, ≈ −40 inside.</li>
                  <li>• <span className="font-mono text-amber-400">Direction mechanism:</span> two-window mirror design — Window 1 (Day 2) injects +bias on Alpha/Gamma device cohort (~300 patients); Window 2 (Day 5) injects -bias on Beta/Delta device cohort (~300 patients). The `calibration_bias_direction_split` setting is now 1.0 (unidirectional per window) since direction is decided BY WINDOW, not within-cohort split.</li>
                </ul>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Visual Elements:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="text-red-400">Red line:</span> Positive-bias cohort signed bias (≈ 0 outside / spikes to ≈ +40 mg/dL during incident)</li>
                  <li>• <span className="text-blue-400">Blue line:</span> Negative-bias cohort signed bias (≈ 0 outside / drops to ≈ −40 mg/dL during incident)</li>
                  <li>• <span className="text-slate-400">Dashed gray line:</span> Zero baseline — no calibration error (the "no bias" reference)</li>
                  <li>• <span className="text-slate-400">Red shaded region:</span> Incident period (3 hours)</li>
                  <li>• <span className="text-slate-400">Y-axis:</span> Symmetric around 0 (typically ±50 to ±60 mg/dL) — so positive and negative cohorts read at the same visual scale</li>
                </ul>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Why delta view instead of absolute glucose:</p>
                <p className="text-sm text-slate-400">
                  An earlier version plotted absolute device readings (glucose_observed) against ground truth (glucose_true). That was visually noisy because diurnal glucose swings (~80–200 mg/dL) dominated the y-axis, making the ±40 mg/dL incident hard to see — and the positive vs negative cohort lines naturally separated outside the incident due to random patient sampling differences, which was counter-intuitive. The signed-bias subtraction eliminates both problems: diurnal fluctuations cancel, cohort-composition differences cancel, and the only thing visible is the device error itself.
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Clinical Significance:</p>
                <p className="text-sm text-slate-400">
                  A bidirectional calibration drift means SOME devices over-read and OTHERS under-read — both directions are clinically dangerous but in opposite ways. Over-reading can lead to unnecessary corrective insulin (causing hypo); under-reading can lead to missed real highs (delayed correction, prolonged hyper). The fleet monitoring layer detects BOTH directions via the same direction-agnostic MAE metric (top chart) — operators then drill in via the `incident_direction` field on the alerts table to act on the specific failure mode. This delta chart is the operator's "what direction did it drift?" view.
                </p>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">{catalog}.{schema}.pseudo_incident_7d_labeled</span>
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
  FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
  WHERE time IS NOT NULL
)
SELECT 
  MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_15m,
  MAX(CASE WHEN incident_period = 1 THEN mae ELSE 0 END) as peak_mae_30m,
  5.8 as baseline_mae_15m,
  5.8 as baseline_mae_30m,
  MAX(CASE WHEN incident_period = 1 THEN ABS(bias) ELSE 0 END) as max_device_bias,
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
                  <li>• <span className="font-mono text-amber-400">max_device_bias:</span> Maximum bias MAGNITUDE during incident — uses ABS() so it captures the worst calibration drift in either direction (positive or negative)</li>
                  <li>• <span className="font-mono text-slate-400">incident_start/end:</span> Incident time window</li>
                  <li>• <span className="font-mono text-slate-400">incident_description:</span> Type of incident (e.g., "Device Calibration Failure")</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">{catalog}.{schema}.pseudo_incident_7d_labeled</span>
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
FROM ${catalog}.${schema}.silver_patient_registry`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">{catalog}.{schema}.silver_patient_registry</span>
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
FROM ${catalog}.${schema}.gold_patient_device_readings
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
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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
FROM ${catalog}.${schema}.gold_patient_device_readings
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
                    <span>HIGH (&gt;5%), MEDIUM (&gt;4.5%), LOW (≤4.5%)</span>
                  </div>
                </div>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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
    (SELECT MAX(time) FROM ${catalog}.${schema}.gold_patient_device_readings)
  ) as minutes_since_last_reading,
  patient_id,
  device_model as device_type,
  CAST(firmware_version AS STRING) as firmware_version,
  glucose as glucose_value
FROM ${catalog}.${schema}.gold_patient_device_readings
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
                  Table: <span className="text-cyan-400">{catalog}.{schema}.gold_patient_device_readings</span>
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
              <h3 className="text-sm font-semibold text-slate-400 mb-2">Diabetes Coach Dashboard</h3>
              <p className="text-xs text-slate-500">Metrics documentation coming soon...</p>
            </div>
          </div>
        </section>

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
          <p>All metrics are calculated in real-time from Databricks Unity Catalog via DBSQL MCP Server</p>
          <p className="mt-1 font-mono">Schema: {catalog}.{schema}</p>
        </div>
      </main>
    </div>
  );
}
