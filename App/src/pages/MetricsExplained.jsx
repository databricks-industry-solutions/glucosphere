import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BookOpen, ArrowLeft } from 'lucide-react';
import { getConfig } from '../api/config';
import { useGoBack } from '../hooks/useGoBack';
// fig4 PNG is served at runtime from UC Volume via Flask /uc-assets/ route
// (App/databricks/app.py:serve_uc_asset). No vite-bundled static copy needed —
// the pipeline writes to /Volumes/{CATALOG}/{SCHEMA}/pipeline_data/incident_inference_assets/
// and the App fetches it live. Refresh PNG = rerun the pipeline; no rebuild needed.
const FIG4_UC_PATH = '/uc-assets/incident_inference_assets/distribution_comparison_4panel.png';

export default function MetricsExplained() {
  const navigate = useNavigate();
  const location = useLocation();
  const goBack = useGoBack();

  // Deep-link support: the landing-page chart panels link here with a #anchor
  // (e.g. /metrics-explained#me-mae-timeline). react-router v6 does NOT auto-scroll
  // to a hash, so scroll the matching card into view (below the sticky header via
  // scroll-mt on the targets). Defer a frame so layout is settled first.
  useEffect(() => {
    if (!location.hash) return;
    const el = document.querySelector(location.hash);
    if (el) requestAnimationFrame(() => el.scrollIntoView({ behavior: 'smooth', block: 'start' }));
  }, [location.hash]);

  // Fetch catalog/schema from Flask /api/config so the SQL examples + display
  // text shown to users reflect the workspace this app is deployed to.
  // NEVER hardcode catalog/schema inline.
  const [catalog, setCatalog] = useState('');
  const [schema, setSchema] = useState('');
  const [baselineSource, setBaselineSource] = useState('from_source');
  const [baselineSourceDetail, setBaselineSourceDetail] = useState('');
  const [workspaceHost, setWorkspaceHost] = useState('');
  const [setupJobUrl, setSetupJobUrl] = useState('');
  useEffect(() => {
    getConfig().then(cfg => {
      setCatalog(cfg.catalog || '');
      setSchema(cfg.schema || '');
      setBaselineSource(cfg.baseline_source || 'from_source');
      setBaselineSourceDetail(cfg.baseline_source_detail || '');
      setWorkspaceHost(cfg.workspace_host || '');
      setSetupJobUrl(cfg.setup_job_url || '');
    }).catch(err => console.error('Failed to load config:', err));
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={goBack}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                <BookOpen className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                  Metrics Explained
                </h1>
                <p className="text-xs text-slate-500 font-mono">How metrics are calculated across dashboards</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8">
        {/* Introduction */}
        <section className="mb-12">
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-3 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
              About This Page
            </h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              This page documents how each metric is calculated across the Glucosphere Dashboard.
              All metrics are derived from real-time data in the Databricks Unity Catalog using SQL queries
              via the DBSQL MCP (Model Context Protocol) server.
            </p>
            <p className="text-sm text-slate-400 leading-relaxed mt-3">
              <span className="text-amber-300 font-medium">Note on demo data:</span> patient identifiers,
              device metadata, and the ±40 mg/dL device-calibration-bug incidents shown across these charts
              are <span className="text-amber-300 font-medium">simulated</span> for demo purposes — there is
              no real adverse-event PHI.{' '}
              {baselineSource === 'synthetic' ? (
                <>
                  This deployment is running in <span className="font-mono text-cyan-400">baseline_source=synthetic</span>{' '}
                  mode — the underlying CGM glucose signal is generated by a textbook-phenotype + AR(1) synthetic
                  generator (no external data dependency). The synthetic baseline reflects an idealized
                  "well-managed diabetes" distribution (std ≈ 34 mg/dL, ~0.1% hypo), which exercises the model
                  + monitoring stack against a clean baseline. A <span className="font-mono text-cyan-400">from_source</span>{' '}
                  mode (HUPA-UCM seed) is also available for runs against clinical extremes — see{' '}
                  <span className="font-mono text-cyan-400">baseline_source</span> in the deploy docs.
                </>
              ) : baselineSource === 'from_table' ? (
                <>
                  This deployment is running in <span className="font-mono text-cyan-400">baseline_source=from_table</span>{' '}
                  mode — the underlying CGM glucose signal is read from a pre-existing UC table you specified
                  {baselineSourceDetail && (
                    <>
                      {' '}(<span className="font-mono text-cyan-400">{baselineSourceDetail}</span>)
                    </>
                  )}.
                  This is the bring-your-own-data variant: useful when you already have curated CGM data in UC
                  and want to wire it through the forecast + monitoring pipeline without re-ingesting.{' '}
                  <span className="font-mono text-cyan-400">synthetic</span> and{' '}
                  <span className="font-mono text-cyan-400">from_source</span> modes are also available —
                  see <span className="font-mono text-cyan-400">baseline_source</span> in the deploy docs.
                </>
              ) : (
                <>
                  This deployment is running in the default <span className="font-mono text-cyan-400">baseline_source=from_source</span>{' '}
                  mode — the underlying CGM glucose signal is seeded from a real T1D dataset
                  (HUPA-UCM), so the forecasting model + monitoring stack are exercised against realistic clinical
                  extremes (≈6.6% hypo, max 444 mg/dL). A fully-synthetic baseline mode is also available for
                  clean demos without external data dependency — see <span className="font-mono text-cyan-400">baseline_source</span>{' '}
                  in the deploy docs.
                </>
              )}
            </p>
          </div>
        </section>

        {/* Counts vs rates — data-agnostic principle (true on real OR synthetic baseline) */}
        <section className="mb-12">
          <div className="bg-slate-900/50 border border-amber-500/20 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-amber-300 mb-2" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
              Why fleet comparisons use rates, not counts
            </h2>
            <p className="text-sm text-slate-400">
              The gold table holds <span className="font-mono text-cyan-400">one row per reading</span> (~288/patient/day),
              so a raw <span className="font-mono text-amber-400">COUNT</span> of out-of-range readings scales with how much
              data a group has — not how unhealthy it is. Comparing device models, diagnoses, regions, or firmware by raw
              count therefore ranks them by population/volume and can invert the real picture (the smallest cohort often has
              the highest rate). So cross-group views — the firmware × model heatmap, the High-Risk tile, and the CGM Genie
              assistant — report <span className="text-cyan-300">rates</span>{' '}
              (<span className="font-mono text-cyan-400">AVG(glucose_out_of_range)*100</span>), and reserve the Battelino
              level-2 danger bands (<span className="font-mono">&lt;54</span> / <span className="font-mono">&gt;250</span> mg/dL)
              for "high risk". Device-health questions use data completeness (readings vs the expected ~288/day), not glucose excursions.
            </p>
          </div>
        </section>

        {/* Landing Page Hero Metrics */}
        <section className="mb-12">
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
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
                  Number of unique patients with at least one reading in a <span className="text-slate-200">clinically-critical
                  glucose range</span> — Very Low <span className="font-mono text-cyan-400">&lt;54 mg/dL</span> or Very High
                  <span className="font-mono text-cyan-400"> &gt;250 mg/dL</span> — in the last
                  <span className="font-mono text-cyan-400"> 3 hours</span> of available data. These are the level-2 danger
                  bands, deliberately narrower than "any out-of-range (&lt;70 or &gt;180)," which is routine for a diabetic fleet.
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Why 3 hours (not 24)?</p>
                <p className="text-sm text-slate-400">
                  The 3-hour window matches a typical device-calibration incident window so a live incident
                  shifts the count clearly. For scale, on this deployment's <span className="text-slate-300">real (HUPA-UCM) baseline</span>:
                  ~822 patients have a reading in a 3h window; <span className="font-mono text-cyan-400">~517</span> have
                  <em>any</em> out-of-range reading (&lt;70 or &gt;180) — routine for type-1 diabetes — while only
                  <span className="font-mono text-cyan-400"> ~176</span> hit a critical band (&lt;54 or &gt;250).
                  Counting the critical bands is what makes this a believable "high-risk" signal rather than half the fleet.
                  <span className="text-slate-500">(A synthetic-baseline deployment is idealized and skews far healthier — fewer in either band; the &lt;54 / &gt;250 thresholds are fixed clinical bands regardless of data source.)</span>
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`SELECT COUNT(DISTINCT patient_id) as high_risk_patients
FROM ${catalog}.${schema}.gold_patient_device_readings
WHERE (glucose < 54 OR glucose > 250)
  AND time >= (
    SELECT MAX(time) - INTERVAL 3 HOUR
    FROM ${catalog}.${schema}.gold_patient_device_readings
  )`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Why &lt;54 and &gt;250?</p>
                <p className="text-sm text-slate-400">
                  These are the level-2 (clinically-significant) danger bands from the international Time-in-Ranges
                  consensus (Battelino et al., 2019): <span className="font-mono text-cyan-400">Very Low &lt;54</span>,
                  Low 54–69, Target 70–180, High 181–250, <span className="font-mono text-cyan-400">Very High &gt;250</span> mg/dL.
                  Counted from the raw <span className="font-mono text-amber-400">glucose</span> column — not the broader
                  <span className="font-mono text-amber-400"> glucose_out_of_range</span> flag, which fires on the routine &lt;70 / &gt;180 bands.
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
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
            Landing Page: Recent Incident Analysis
          </h2>

          {/* Why this monitoring stack matters — frames the 3 incident charts that follow */}
          <div className="bg-cyan-500/5 border border-cyan-500/20 rounded-lg p-6 mb-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-lg font-semibold text-cyan-300 mb-1">Why this monitoring stack matters</h3>
                <p className="text-xs text-slate-500 font-mono">Platform value — what the three detection-chain charts catch</p>
              </div>
              <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 rounded text-xs font-mono text-cyan-300">FRAMING</span>
            </div>
            <p className="text-sm text-slate-300 leading-relaxed">
              Real-world CGM device calibration failures span <span className="font-medium">both directions</span> — Abbott FreeStyle Libre 3 sensors have <span className="font-medium">FDA Class I (most serious)</span> recalls on record for BOTH <span className="text-red-300 font-medium">over-reading</span><sup><a href="https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/continuous-glucose-monitoring-cgm-sensor-recall-abbott-diabetes-care-inc-issues-recall-certain" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline ml-0.5">1</a></sup> and <span className="text-blue-300 font-medium">under-reading</span><sup><a href="https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/glucose-monitor-sensor-recall-abbott-diabetes-care-removes-certain-freestyle-libre-3-and-freestyle" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline ml-0.5">2</a></sup> sensor failures (≈3M sensors recalled Feb 2026; ≥860 serious injuries and 7 deaths linked to the under-read failure mode alone). Each direction is clinically dangerous in opposite ways (over-read → unwarranted corrective insulin → hypo risk; under-read → missed real highs → delayed correction). A fleet-monitoring layer that catches either failure mode with a single <span className="font-medium">direction-agnostic</span> metric (MAE rolling-window) and then lets operators drill in to <span className="font-medium">which</span> direction each device drifted (<span className="font-mono text-cyan-400">incident_direction</span> field on the alerts table) is what closes the loop from fleet-wide alert → per-device action.
            </p>
            <p className="text-xs text-slate-500 mt-3 leading-relaxed">
              <span className="font-medium text-slate-400">Sources:</span>{' '}
              <sup className="text-cyan-400">1</sup>{' '}
              <a href="https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/continuous-glucose-monitoring-cgm-sensor-recall-abbott-diabetes-care-inc-issues-recall-certain" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">
                FDA — CGM Sensor Recall: Abbott Diabetes Care, Inc. Issues Recall for Certain FreeStyle Libre 3 Sensors due to Risk for Inaccurate <em>High</em> Glucose Readings
              </a>
              {' · '}
              <sup className="text-cyan-400">2</sup>{' '}
              <a href="https://www.fda.gov/medical-devices/medical-device-recalls-and-early-alerts/glucose-monitor-sensor-recall-abbott-diabetes-care-removes-certain-freestyle-libre-3-and-freestyle" target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">
                FDA — Glucose Monitor Sensor Recall: Abbott Diabetes Care Removes Certain FreeStyle Libre 3 and FreeStyle Libre 3 Plus Sensors (inaccurate <em>low</em> readings; Class I, ≈3M sensors, ≥860 serious injuries / 7 deaths linked)
              </a>
            </p>
            <p className="text-sm text-slate-300 leading-relaxed mt-3">
              The detection chain spans three views, each documented in detail below:
              <span className="block ml-4 mt-1">(1) <span className="text-cyan-300 font-medium">MAE Timeline</span> — catches the magnitude (fleet-vs-affected dilution view). <span className="text-xs text-slate-500">Lives on the Glucosphere landing page.</span></span>
              <span className="block ml-4">(2) <span className="text-cyan-300 font-medium">How MAE alerts are triggered</span> — distribution shift explains <em>why</em> MAE spiked. <span className="text-xs text-slate-500">Snapshot PNG from the most recent incident-simulation pipeline run (05_incident_inference_bidirectional notebook), embedded only in this Metrics Explained tab.</span></span>
              <span className="block ml-4">(3) <span className="text-cyan-300 font-medium">Device Calibration Bias Over Time</span> — signed-bias delta reveals <em>which</em> direction each cohort drifted. <span className="text-xs text-slate-500">Lives on the Glucosphere landing page.</span></span>
            </p>
          </div>

          {/* Incident Impact Chart */}
          <div id="me-mae-timeline" className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6 scroll-mt-24">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Incident Impact: MAE Timeline</h3>
                <p className="text-xs text-slate-500 font-mono">Top chart on the Glucosphere landing page — Mean Absolute Error over time</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">TIME SERIES</span>
            </div>
            
            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Displays Mean Absolute Error (MAE) over a 7-day window, showing device accuracy degradation
                  during incident periods. Two lines carry distinct information: <span className="text-blue-400 font-medium">fleet-wide</span> MAE
                  (AVG across all patients — diluted because only the affected cohorts are drifting) vs{' '}
                  <span className="text-orange-400 font-medium">affected-only</span> MAE (AVG over just the patients
                  whose devices are currently in an incident window — shows the TRUE bias magnitude).
                  With the two-window mirror simulation (2026-05-18), TWO separate red-tinted dashed-border
                  rectangles mark the two incident windows: Day 2 (+40 mg/dL bias on Alpha/Gamma cohort) and
                  Day 5 (-40 mg/dL bias on Beta/Delta cohort). Baseline sensor noise of 5.0 mg/dL is added
                  to every reading to simulate realistic CGM accuracy (~5.8 mg/dL MARD).
                </p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">SQL Query:</p>
                <pre className="bg-slate-950 border border-slate-800 rounded p-3 text-xs font-mono text-slate-300 overflow-x-auto">
{`WITH minute_data AS (
  SELECT
    DATE_TRUNC('minute', time) as minute,
    has_incident,
    CASE WHEN time >= incident_start_time AND time < incident_end_time THEN 1 ELSE 0 END as incident_period,
    incident_type as incident_label,
    ABS(glucose_observed - glucose_true) + 5.0 as error_value
  FROM ${catalog}.${schema}.pseudo_incident_7d_labeled
  WHERE time IS NOT NULL
)
SELECT
  minute as time,
  AVG(error_value) as mae_fleet,
  -- Two-window mirror gotcha: mae_affected uses incident_period (per-time-window)
  -- NOT has_incident (per-patient). has_incident=1 includes both cohorts at all
  -- times — averaging over them dilutes the spike. incident_period=1 only fires
  -- during each cohort's OWN window → clean ~+/-45 mg/dL peaks at the two windows.
  AVG(CASE WHEN incident_period = 1 THEN error_value END) as mae_affected,
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
                  <li>• <span className="font-mono text-cyan-400">MAE (Mean Absolute Error):</span> <code className="font-mono text-cyan-300 bg-slate-800/60 px-1.5 py-0.5 rounded">ABS(glucose_observed − glucose_true) + 5.0</code> (baseline sensor noise) — direction-agnostic, catches both positive and negative bias</li>
                  <li>• <span className="font-mono text-blue-400">MAE Fleet-wide:</span> AVG across ALL patients — diluted to ~17 mg/dL during incident because only the active-window cohort drifts at any moment</li>
                  <li>• <span className="font-mono text-orange-400">MAE Affected-only:</span> AVG filtered to <em>incident_period = 1</em> (the per-time-window predicate, NOT the per-patient has_incident flag) — shows the TRUE device-error magnitude ~45 mg/dL during incident. Using incident_period avoids the two-window-mirror dilution trap where has_incident=1 includes both cohorts at all times.</li>
                  <li>• <span className="font-mono text-amber-400">Dilution gap (45 → 17):</span> Why patient-level monitoring matters — fleet-wide averages mask serious per-device errors</li>
                  <li>• <span className="font-mono text-rose-400">Incident Period:</span> time &gt;= incident_start_time AND time &lt; incident_end_time (3-hour window per cohort; two such windows total in the mirror simulation)</li>
                  <li>• <span className="font-mono text-amber-400">Baseline MAE:</span> ~5.8 mg/dL (typical CGM sensor accuracy — dashed slate-400 reference line)</li>
                  <li>• <span className="font-mono text-amber-300">Two MAEs — don't conflate:</span> the <em>model-monitoring</em> MAE is <span className="font-medium">forecast error</span> = |XGBoost prediction − actual future glucose| (computed in the inference notebook: clean ~3.8 mg/dL @15-min / ~5.9 @30-min → ~38 mg/dL during an incident — the headline degradation). <span className="font-medium">This landing chart</span> instead computes a fast <span className="font-medium">device-error proxy</span> = <span className="font-mono text-cyan-400">ABS(glucose_observed − glucose_true) + 5.0</span> directly in SQL (the dashboard doesn't re-run the model in the browser). The proxy is engineered to mirror the forecast-MAE spike — the +5.0 floor → ~5.8 baseline, the ±40 device bias → ~45 affected — and the dashed "Baseline (5.8)" line is the real forecast 30-min baseline.</li>
                  <li>• <span className="font-mono text-slate-300">Derived, not stored:</span> neither MAE is a raw column — both are computed (the forecast MAE during model inference; this chart's proxy at query time from <span className="font-mono text-cyan-400">glucose_observed</span> / <span className="font-mono text-cyan-400">glucose_true</span>).</li>
                  <li>• <span className="font-mono text-slate-300">Time granularity:</span> one point per reading timestamp — readings are 5-min spaced, so <span className="font-mono text-cyan-400">DATE_TRUNC('minute', time)</span> yields a per-5-min point, averaged across the patient population at that moment.</li>
                </ul>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Visual Elements:</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="text-blue-400">Blue line:</span> MAE Fleet-wide (diluted across all patients — ~17 mg/dL peak)</li>
                  <li>• <span className="text-orange-400">Orange line:</span> MAE Affected-only (true bias magnitude — ~45 mg/dL peak)</li>
                  <li>• <span style={{color: 'rgb(248 113 113)'}}>Light-red shaded rectangles (dashed border):</span> Incident windows — TWO separate rectangles (3h each) for the two-window mirror simulation (Day 2 +40 cohort, Day 5 −40 cohort)</li>
                  <li>• <span className="text-slate-400">Dashed slate line:</span> Baseline MAE reference (~5.8 mg/dL)</li>
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

          {/* How MAE alerts are triggered — distribution shift view (4-panel snapshot from 05_incident_inference_bidirectional notebook) */}
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
                  Positive-bias cohort (<span className="text-red-400 font-medium">red</span>) shifts UP into hyperglycemic range (&gt;180 mg/dL) — 42% of readings cross the hyper threshold vs ~22% baseline. Negative-bias cohort (<span className="text-blue-400 font-medium">blue</span>) shifts DOWN into hypoglycemic range (&lt;70 mg/dL) — 26% cross hypo vs ~6% baseline. The directional distribution shift drives a 6× MAE spike fleetwide, which the rolling-window monitor (MAE Timeline chart on the Glucosphere landing page) catches in real time and surfaces as an alert.
                </p>
                <p className="text-xs text-slate-500 italic mt-2">
                  (The ±40 mg/dL incident itself is a <span className="text-amber-300">simulated</span> calibration bug injected into the demo data for illustration — see _About This Page_ above for full provenance.)
                </p>
              </div>
              <div className="my-4">
                <img
                  src={FIG4_UC_PATH}
                  alt="4-panel glucose distribution comparison: baseline (darkgray), clean period (mediumturquoise), Inc+ cohort (red, over-reads), Inc- cohort (blue, under-reads). Histograms, bar chart, CDF, and box plot show how each incident direction shifts the distribution and how the shift maps to hypo/hyper threshold crossings."
                  className="w-full rounded-lg border border-slate-800 bg-slate-950/50"
                />
              </div>
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Data Source:</p>
                <p className="text-sm text-slate-400 font-mono">
                  Generated by the{' '}
                  {(setupJobUrl || workspaceHost) ? (
                    <a href={setupJobUrl || `${workspaceHost}/jobs`} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:underline">
                      glucosphere-full-setup-*
                    </a>
                  ) : (
                    <span className="text-cyan-400">glucosphere-full-setup-*</span>
                  )}
                  {' '}job (the bundle-target-suffixed full setup workflow). PNG is read live from UC Volume
                  via the App's <span className="text-cyan-400">/uc-assets/</span> Flask route, so it
                  refreshes automatically whenever the pipeline regenerates it (no app redeploy needed).
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Notebook: <span className="text-cyan-400">05_incident_inference_bidirectional</span> 4-class distribution comparison cell. PNG has transparent background so it inherits the surrounding card color in any theme.
                </p>
              </div>
            </div>
          </div>

          {/* Glucose Timeline Chart */}
          <div id="me-bias-timeline" className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 mb-6 scroll-mt-24">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-cyan-400 mb-1">Device Calibration Bias Over Time (±40 mg/dL Bidirectional)</h3>
                <p className="text-xs text-slate-500 font-mono">Bottom chart on the Glucosphere landing page — Signed bias delta per direction cohort</p>
              </div>
              <span className="px-3 py-1 bg-slate-800 rounded text-xs font-mono text-slate-400">TIME SERIES</span>
            </div>

            <div className="space-y-3">
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">What it shows:</p>
                <p className="text-sm text-slate-400">
                  Signed device bias <span className="font-mono">(observed − true)</span> averaged per direction cohort over the same 7-day window. With the two-window mirror design (2026-05-18), the positive-bias cohort (Alpha/Gamma devices) spikes to +40 mg/dL during Window 1 on Day 2, while the negative-bias cohort (Beta/Delta devices) drops to −40 mg/dL during Window 2 on Day 5. Outside each cohort's own window, that cohort's line sits at ≈ 0 (devices match ground truth) — diurnal glucose fluctuations cancel in the subtraction. Both directions are clinically relevant calibration failures and both are detected by the same direction-agnostic MAE monitor (MAE Timeline chart on the Glucosphere landing page).
                </p>
                <p className="text-xs text-slate-500 italic mt-2">
                  (The ±40 mg/dL two-window incident is a <span className="text-amber-300">simulated</span> adverse device-calibration scenario injected into the demo data — see _About This Page_ above for full provenance.)
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
                  A bidirectional calibration drift means SOME devices over-read and OTHERS under-read — both directions are clinically dangerous but in opposite ways. Over-reading can lead to unnecessary corrective insulin (causing hypo); under-reading can lead to missed real highs (delayed correction, prolonged hyper). The fleet monitoring layer detects BOTH directions via the same direction-agnostic MAE metric (MAE Timeline chart on the Glucosphere landing page) — operators then drill in via the `incident_direction` field on the alerts table to act on the specific failure mode. This delta chart is the operator's "what direction did it drift?" view.
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
          <h2 className="text-2xl font-bold mb-6 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
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
  ROUND(AVG(glucose_out_of_range) * 100, 1) as out_of_range_pct
FROM ${catalog}.${schema}.gold_patient_device_readings
GROUP BY device_model, firmware_version
ORDER BY device_model, firmware_version`}
                </pre>
              </div>
              
              <div>
                <p className="text-sm font-medium text-slate-300 mb-2">Axes (Dynamic):</p>
                <ul className="text-sm text-slate-400 space-y-1 ml-4">
                  <li>• <span className="font-mono text-cyan-400">X-axis (top):</span> Unique firmware versions extracted from data</li>
                  <li>• <span className="font-mono text-cyan-400">Y-axis (left):</span> Unique device models extracted from data</li>
                  <li>• <span className="font-mono text-amber-400">Cell values:</span> % of readings out-of-range (AVG(glucose_out_of_range)*100) for that combination — a rate, so models with more patients aren't ranked worse just for having more readings</li>
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
                  Most recent 50 glucose readings flagged as out-of-range within the
                  last <span className="font-mono text-cyan-400">3 hours</span> of available data,
                  with device and patient details. Same 3-hour window as the High Risk Alerts hero
                  metric — matches incident-window length so a live calibration event surfaces here
                  clearly above natural baseline OOR noise.
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
  AND time >= (
    SELECT MAX(time) - INTERVAL 3 HOUR
    FROM ${catalog}.${schema}.gold_patient_device_readings
  )
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

        {/* Footer */}
        <div className="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
          <p>All metrics are calculated in real-time from Databricks Unity Catalog via DBSQL MCP Server</p>
          <p className="mt-1 font-mono">Schema: {catalog}.{schema}</p>
        </div>
      </main>
    </div>
  );
}
