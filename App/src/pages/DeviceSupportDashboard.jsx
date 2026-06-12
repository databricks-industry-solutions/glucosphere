import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Wrench, AlertTriangle, Search, TrendingUp, ChevronDown, ChevronRight, Brain, Loader } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';
import { getDistinctDeviceCount, getDeviceHeatmapData, getOutOfRangeDevices, getDeviceLatestReading, getDevicePatternAlerts, getFirmwareCohorts, getFirmwareLifecycle, getPatientIncidentSnapshot, getPatientRecent3h } from '../api/databricksSQL';
import { callAssistant } from '../api/databricksAgent';
import { getEngine } from '../api/assistEngine';
import { getConfig } from '../api/config';
import ReactMarkdown from 'react-markdown';

// Markdown styling for the Device Analysis (FM) output. The repo has no
// @tailwindcss/typography plugin, so `prose` classes are no-ops — style each
// element explicitly so the FM's section labels + key terms color-code and the
// text stops reading as one undifferentiated block. (Render-only; does not touch
// the FM call/prompt.)
const mdComponents = {
  p: (p) => <p className="mb-2.5 leading-relaxed" {...p} />,
  strong: (p) => <strong className="text-cyan-300 font-semibold" {...p} />,
  em: (p) => <em className="text-slate-200" {...p} />,
  h1: (p) => <h4 className="text-sm text-cyan-400 font-semibold mt-3 mb-1" {...p} />,
  h2: (p) => <h4 className="text-sm text-cyan-400 font-semibold mt-3 mb-1" {...p} />,
  h3: (p) => <h4 className="text-sm text-cyan-400 font-semibold mt-3 mb-1" {...p} />,
  ul: (p) => <ul className="list-disc ml-5 space-y-1 mb-2.5" {...p} />,
  ol: (p) => <ol className="list-decimal ml-5 space-y-1 mb-2.5" {...p} />,
  li: (p) => <li className="leading-relaxed" {...p} />,
  code: (p) => <code className="font-mono text-amber-300 bg-slate-900/60 px-1 rounded" {...p} />,
};

export default function DeviceSupportDashboard() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const lakebaseConfigured = useLakebaseConfigured();
  const [expandedDevice, setExpandedDevice] = useState(null);
  const [filterModel, setFilterModel] = useState('all');
  // Deep-link from a patient's Device panel (Coach → "Device fleet diagnostics"):
  // ?model=<deviceModel> pre-filters the fleet to that patient's model; ?device=<id>
  // best-effort highlights that exact device if it surfaces in the out-of-range list.
  const [searchParams, setSearchParams] = useSearchParams();
  const focusModel = searchParams.get('model');
  const focusDevice = searchParams.get('device');
  const [focusRow, setFocusRow] = useState(null);       // that device's latest reading (OOR/3h gate overridden)
  // Layered time context for the focused device: fault window ("then") +
  // last-3h danger-band summary ("recent") — so arriving from a triage alert
  // or the live watchlist doesn't contradict a healthy "latest" reading.
  const [focusCtx, setFocusCtx] = useState(null);
  const [focusLoading, setFocusLoading] = useState(false);
  const [deviceCount, setDeviceCount] = useState('...');
  const [deviceCountLoading, setDeviceCountLoading] = useState(true);
  const [heatmapData, setHeatmapData] = useState([]);
  const [heatmapLoading, setHeatmapLoading] = useState(true);
  const [deviceTypes, setDeviceTypes] = useState([]);
  const [firmwareVersions, setFirmwareVersions] = useState([]);
  // Firmware × day device-error (MAE) for the date×firmware heatmap (reuses the same
  // getFirmwareLifecycle data as the Firmware Lifecycle line chart).
  const [fwHeat, setFwHeat] = useState([]);          // [{ day, firmware_version, mae, maeFleet }]
  const [fwDays, setFwDays] = useState([]);          // sorted unique days (columns)
  const [fwRows, setFwRows] = useState([]);          // sorted unique firmware versions (rows)
  const [fwHeatLoading, setFwHeatLoading] = useState(true);
  // Heatmap metric scope: 'in-incident' = peak fault severity (triage — which firmware-day to
  // service); 'fleet-wide' = all-readings average (compliance — avg measurement error across
  // the deployed firmware, where the ~12h fault dilutes). Mirrors the MAE-timeline's
  // affected-vs-fleet-wide framing. Default = in-incident (the fault must be findable first).
  const [fwScope, setFwScope] = useState('in-incident');
  const [devices, setDevices] = useState([]);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [fwCohorts, setFwCohorts] = useState([]);     // [{ firmware_version, direction, device_model, devices }]
  const [fwCohortsLoading, setFwCohortsLoading] = useState(true);
  const [baselineSource, setBaselineSource] = useState('from_source'); // synthetic | from_source | from_table — drives the baseline/dilution note wording
  const [deviceAnalysis, setDeviceAnalysis] = useState({}); // Store analysis for each device
  const [analysisLoading, setAnalysisLoading] = useState({}); // Track loading state per device

  // Scroll to top when component mounts
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  // Deep-link focus: when arriving with ?model=…, pre-set the model filter so the
  // fleet opens narrowed to the patient's device model.
  useEffect(() => {
    if (focusModel) setFilterModel(focusModel);
  }, [focusModel]);

  // Deep-link focus: when arriving with ?device=…, fetch THAT device's latest reading
  // directly (overriding the out-of-range / 3-hour gate) so the table focuses on it for
  // review even when it's within range.
  useEffect(() => {
    if (!focusDevice) { setFocusRow(null); return; }
    let alive = true;
    (async () => {
      try {
        setFocusLoading(true);
        const row = await getDeviceLatestReading(focusDevice);
        if (alive) setFocusRow(row);
      } catch (e) {
        console.error('focus device fetch failed:', e);
        if (alive) setFocusRow(null);
      } finally {
        if (alive) setFocusLoading(false);
      }
    })();
    return () => { alive = false; };
  }, [focusDevice]);

  // Layered time context for the focused device — fetched once per focus:
  // "then" (the patient's worst in-incident moment) + "recent" (last-3h
  // danger-band summary). Whichever frame the visitor arrived from (triage
  // alert / live watchlist / roster), the panel shows it next to "now".
  useEffect(() => {
    const pid = focusRow?.patient_id;
    if (!pid) { setFocusCtx(null); return; }
    let alive = true;
    Promise.all([getPatientIncidentSnapshot(pid), getPatientRecent3h(pid)])
      .then(([snap, recent]) => { if (alive) setFocusCtx({ snap, recent }); })
      .catch(() => { if (alive) setFocusCtx(null); });
    return () => { alive = false; };
  }, [focusRow?.patient_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Clear the patient-focus deep-link (drops the banner + the focused device, resets the
  // filter — back to the full out-of-range fleet view).
  const clearFocus = () => {
    setFilterModel('all');
    setFocusRow(null);
    setSearchParams({}, { replace: true });
  };

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

  // Fetch firmware × day device error (MAE) for the date×firmware heatmap.
  useEffect(() => {
    const fetchFwHeat = async () => {
      try {
        setFwHeatLoading(true);
        const data = await getFirmwareLifecycle();  // [{ day, firmwareVersion, mae, maeFleet, readings }]
        if (data && data.length > 0) {
          const rows = data.map(d => ({ day: d.day, firmware_version: d.firmwareVersion, mae: d.mae, maeFleet: d.maeFleet }));
          setFwHeat(rows);
          setFwDays([...new Set(rows.map(r => r.day))].sort());                 // dates ascending
          setFwRows([...new Set(rows.map(r => r.firmware_version))].sort());    // 3.14 < 4.0 < 4.0.3 < 4.1
        } else {
          setFwHeat([]); setFwDays([]); setFwRows([]);
        }
      } catch (error) {
        console.error('Failed to fetch firmware lifecycle heatmap:', error);
        setFwHeat([]); setFwDays([]); setFwRows([]);
      } finally {
        setFwHeatLoading(false);
      }
    };
    fetchFwHeat();
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
            lastReading: d.reading_time, // actual reading timestamp from data (dynamic; not wall-clock-relative)
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


  // Helper function to calculate anomaly score based on glucose value
  // Normal range: 70-180 mg/dL
  const calculateAnomalyScore = (glucoseValue) => {
    if (glucoseValue < 54) return 0.95; // Critically low
    if (glucoseValue < 70) return 0.85; // Low
    if (glucoseValue > 250) return 0.92; // Critically high
    if (glucoseValue > 180) return 0.78; // High
    return 0.1; // In range (70–180) — low risk (only reachable via the focus deep-link; OOR-snapshot rows are never in range)
  };

  // Directional severity band (Battelino bands). The out-of-range snapshot rows are always
  // OOR (<70 or >180) → one of four danger bands. The deep-link "focus" row can also be a
  // healthy in-range reading (70–180) → the IN RANGE (emerald) case. rose = level-2 danger
  // (Very Low / Very High), amber = level-1 (Low / High), emerald = in range.
  const glucoseBand = (g) =>
    g < 54 ? { label: 'VERY LOW', cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' }
      : g < 70 ? { label: 'LOW', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' }
      : g > 250 ? { label: 'VERY HIGH', cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' }
      : g > 180 ? { label: 'HIGH', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' }
      : { label: 'IN RANGE', cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' };

  // Function to get deeper analysis for a specific device reading
  const handleDeeperAnalysis = async (device) => {
    const deviceKey = device.id;
    
    // Set loading state for this specific device
    setAnalysisLoading(prev => ({ ...prev, [deviceKey]: true }));
    
    try {
      // Construct prompt with device context - focusing on device troubleshooting
      const _oor = device.glucose_value < 70 || device.glucose_value > 180;
      const prompt = `Analyze this glucose reading from a DEVICE TROUBLESHOOTING perspective (1-2 paragraphs maximum):

Device ID: ${device.id}
Device Model: ${device.model}
Firmware Version: ${device.firmware}
Patient ID: ${device.patient}
Glucose Reading: ${Math.round(device.glucose_value)} mg/dL
Reading time: ${device.lastReading}
Status: ${_oor ? 'OUT-OF-RANGE (outside the 70–180 mg/dL target)' : 'IN RANGE (within the 70–180 mg/dL target — reviewing this device proactively, not because it is flagged)'}

As a biomedical equipment specialist, analyze:
1. Is this a device malfunction or calibration issue?
2. Are there known issues with this device model or firmware version?
3. Could this be a sensor failure, connectivity problem, or data transmission error?
4. What device diagnostics or troubleshooting steps should be taken?
5. Does this require device replacement, recalibration, or firmware update?

Focus on DEVICE technical issues, not patient clinical care. Provide actionable troubleshooting steps for biomedical technicians.`;

      console.log('Requesting deeper analysis for:', deviceKey);

      // Engine-switchable: 'direct' (fast FM + fleet enrichment) or 'mas' (supervisor).
      // mode:'analysis' tells the backend to fetch fleet context for this model/firmware.
      const response = await callAssistant(prompt, {
        engine: getEngine(),
        mode: 'analysis',
        context: { model: device.model, firmware: device.firmware },
      });
      
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

  // Fetch the per-firmware fault cohort: which device models were faulted on each firmware
  // and in which DIRECTION (over- vs under-read). Annotates the firmware × day heatmap row
  // labels (direction tag) + the fault-cell ↑/↓ glyphs + the hover model breakdown — folding
  // in what the (now relocated to the Firmware Lifecycle page) Calibration Drift matrix shows.
  useEffect(() => {
    const fetchCohorts = async () => {
      try {
        setFwCohortsLoading(true);
        const data = await getFirmwareCohorts();
        setFwCohorts(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch firmware cohorts:', error);
        setFwCohorts([]);
      } finally {
        setFwCohortsLoading(false);
      }
    };
    fetchCohorts();
  }, []);

  // Fetch the deployment's baseline_source so the baseline/dilution note describes
  // the data honestly (real HUPA-UCM vs synthetic generator vs provided table).
  useEffect(() => {
    getConfig()
      .then(cfg => setBaselineSource(cfg.baseline_source || 'from_source'))
      .catch(() => {});
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
            oorEvents: d.total_oor_events,
            days_tracked: d.days_tracked
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

  // Calculate dynamic min/max values for heatmap scaling (out-of-range RATE %)
  const minOorPct = heatmapData.length > 0
    ? Math.min(...heatmapData.map(d => d.out_of_range_pct))
    : 0;

  const maxOorPct = heatmapData.length > 0
    ? Math.max(...heatmapData.map(d => d.out_of_range_pct))
    : 1;

  const getHeatmapColor = (pct) => {
    if (pct === 0) return 'rgb(51 65 85)'; // slate-700 for empty cell (no data)

    // Normalize based on actual data range (min to max), not 0 to max
    const normalized = (pct - minOorPct) / (maxOorPct - minOorPct); // 0 to 1
    
    // Color spectrum: green → yellow → orange → red
    if (normalized < 0.25) {
      // Green to Yellow-Green (low rate)
      const t = normalized / 0.25; // 0 to 1 within this range
      const r = Math.round(34 + (132 * t));   // 34 (emerald) → 166 (lime)
      const g = Math.round(197 + (23 * t));   // 197 → 220
      const b = Math.round(94 - (44 * t));    // 94 → 50
      return `rgb(${r} ${g} ${b})`;
    } else if (normalized < 0.5) {
      // Yellow-Green to Yellow (medium-low rate)
      const t = (normalized - 0.25) / 0.25;
      const r = Math.round(166 + (88 * t));   // 166 → 254 (yellow)
      const g = Math.round(220 + (4 * t));    // 220 → 224
      const b = Math.round(50 - (36 * t));    // 50 → 14
      return `rgb(${r} ${g} ${b})`;
    } else if (normalized < 0.75) {
      // Yellow to Orange (medium-high rate)
      const t = (normalized - 0.5) / 0.25;
      const r = Math.round(254 - (3 * t));    // 254 → 251 (orange)
      const g = Math.round(224 - (78 * t));   // 224 → 146
      const b = Math.round(14 - (5 * t));     // 14 → 9
      return `rgb(${r} ${g} ${b})`;
    } else {
      // Orange to Red (high rate)
      const t = (normalized - 0.75) / 0.25;
      const r = Math.round(251 - (12 * t));   // 251 → 239 (rose/red)
      const g = Math.round(146 - (78 * t));   // 146 → 68
      const b = Math.round(9 + (59 * t));     // 9 → 68
      return `rgb(${r} ${g} ${b})`;
    }
  };

  // Per-firmware fault cohort → { direction, models[], totalDevices }, keyed by firmware.
  // Drives the heatmap's row-label direction tag (↑ over / ↓ under), the fault-cell glyph,
  // and the hover model breakdown — folding in the (relocated) Calibration Drift matrix.
  const fwCohortByFw = {};
  fwCohorts.forEach(c => {
    const e = fwCohortByFw[c.firmware_version] || { direction: c.direction, models: [], totalDevices: 0 };
    e.direction = c.direction;                 // 'positive' (over-read) | 'negative' (under-read)
    e.models.push({ model: c.device_model, devices: c.devices });
    e.totalDevices += c.devices;
    fwCohortByFw[c.firmware_version] = e;
  });
  const dirGlyph = (dir) => (dir === 'positive' ? '↑' : dir === 'negative' ? '↓' : '');
  const dirWord = (dir) => (dir === 'positive' ? 'over' : dir === 'negative' ? 'under' : '');

  // Device-error (MAE mg/dL) colour for the firmware × day heatmap: ~0 → neutral slate
  // (clean), scaling green → amber → red toward the injected ~40 mg/dL fault. Gradiated,
  // scaled against the larger of 40 or the observed max so a full fault reads saturated.
  // Anchor stays in-incident-based (max(40, in-incident max)) in BOTH scope modes, so the
  // fleet-wide view honestly renders low/green (the diluted ~8-12 mg/dL fault never reaches
  // red) instead of being re-stretched to fake a fault.
  const fwMaeMax = fwHeat.length ? Math.max(40, ...fwHeat.map(d => d.mae)) : 40;
  const FW_MAE_GAMMA = 0.7;   // <1 bends the ramp to give clean-day (low-mae) cells visible
                              // green→yellow-green separation (real firmware baseline-noise
                              // gradient) WITHOUT pushing a clean day into amber/red. γ=1.0
                              // would be the old flat-linear scale; γ≤~0.55 over-warms clean
                              // days into false alarms (see ref_notes color-scale sim).
  const getMaeColor = (mae) => {
    // Clean (≈0) renders EMERALD (matching the legend's "0 clean" end), scaling
    // amber → red toward the ~40 mg/dL fault — so an active firmware-day is always a
    // filled green→red cell. Only firmware-days with NO data (firmware not deployed
    // then) stay dark/N-A, handled by the grid (`has ? getMaeColor(...) : darkNA`).
    const t = Math.pow(Math.min(Math.max(mae || 0, 0) / fwMaeMax, 1), FW_MAE_GAMMA);
    const mix = (a, b, u) => Math.round(a + (b - a) * u);
    if (t < 0.5) {                                          // emerald → amber
      const u = t / 0.5;
      return `rgb(${mix(34, 234, u)} ${mix(197, 179, u)} ${mix(94, 8, u)})`;
    }
    const u = (t - 0.5) / 0.5;                              // amber → red
    return `rgb(${mix(234, 239, u)} ${mix(179, 68, u)} ${mix(8, 68, u)})`;
  };

  // Baseline / dilution note — DYNAMIC so it stays honest regardless of baseline_source.
  // Number comes from the live heatmap OOR range (minOorPct/maxOorPct, same values the
  // colorbar uses), so a synthetic deployment (~idealized, lower baseline) shows its own
  // range, not a hardcoded real-data figure. Provenance wording switches on baseline_source.
  const oorRangeKnown = heatmapData.length > 0;
  const oorBaselineRange = oorRangeKnown ? `~${minOorPct}–${maxOorPct}%` : 'its baseline rate';
  const baselineNote = baselineSource === 'synthetic'
    ? { source: 'a synthetic textbook-phenotype + AR(1) generator (idealized, no external data)', why: 'so even calibrated devices report some readings outside 70–180 mg/dL' }
    : baselineSource === 'from_table'
    ? { source: 'a provided baseline table', why: 'so the out-of-range rate reflects that source population' }
    : { source: 'real HUPA-UCM clinical data', why: 'where people with diabetes sit outside 70–180 mg/dL about a third of the time' };

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
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 flex items-center justify-center">
                <Wrench className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
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

      <main className="max-w-[88rem] mx-auto px-6 py-8">
        {/* Population Overview */}
        <section className="mb-8">
          <div className="flex items-center gap-3 mb-1">
            <BrandMark className="w-5 h-5 text-amber-400" />
            <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
              Population Overview
            </h2>
          </div>
          <p className="text-xs font-mono text-slate-500 mb-6">
            Operational fleet view — for the <span className="text-slate-300">device / biomedical team</span> (which devices &amp; firmware to service). For the clinical blast radius (which patients to contact), see{' '}
            <button onClick={() => navigate('/population-risk')} className="text-cyan-400 hover:text-cyan-300">Population Risk →</button>.
          </p>

          <div className="grid grid-cols-12 gap-6 items-stretch">
            {/* Heatmap */}
            <div data-tour="anomaly-heatmap" className="col-span-7 bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
              <div className="mb-4 min-h-14">
                <div className="flex items-start justify-between gap-3">
                  <h3 className="text-sm font-medium text-slate-300 mb-1">Device Error by Firmware × Day</h3>
                  {/* Metric-scope toggle — In-incident (triage, peak fault) vs Fleet-wide
                      (compliance, all-readings avg). Reuses the MAE-timeline's fleet-wide vocabulary. */}
                  <div className="shrink-0 text-right">
                    <span className="block text-[9px] font-mono text-slate-500 mb-0.5 tracking-wide">Metric scope</span>
                    <div className="inline-flex rounded-md border border-slate-700 overflow-hidden text-[11px] font-mono" role="group" aria-label="Heatmap metric scope">
                      <button
                        onClick={() => setFwScope('in-incident')}
                        title="Peak fault severity during the incident window — which firmware-day to service"
                        className={`px-2.5 py-1 transition-colors ${fwScope === 'in-incident' ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
                      >In-incident <span className="opacity-70">(triage)</span></button>
                      <button
                        onClick={() => setFwScope('fleet-wide')}
                        title="All-readings average for the firmware-day — the ~12h fault dilutes; severity is masked"
                        className={`px-2.5 py-1 transition-colors border-l border-slate-700 ${fwScope === 'fleet-wide' ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}
                      >Fleet-wide <span className="opacity-70">(compliance)</span></button>
                    </div>
                  </div>
                </div>
                <p className="text-xs text-slate-500 font-mono mt-3">
                  {fwScope === 'in-incident'
                    ? <>mean |observed − true| mg/dL per firmware per day · ≈0 clean, ~40 faulted · <span className="text-rose-300">↑ over</span> / <span className="text-sky-300">↓ under</span>-read marks the faulted rollout</>
                    : <>mean |observed − true| mg/dL averaged over <span className="text-slate-400">all</span> readings per firmware-day · the ~12h fault dilutes into the day, masking severity — switch to <span className="text-slate-400">In-incident</span> to triage</>}
                </p>
              </div>

              <div className="flex-1 flex flex-col gap-3">
                {/* Heatmap grid: firmware (rows) × day (cols); cell = device-error MAE. */}
                <div className="flex-1 min-w-0 flex flex-col">
                  {fwHeatLoading ? (
                    <div className="flex items-center justify-center h-48 text-slate-500">
                      Loading device-error data...
                    </div>
                  ) : (
                    <div className="h-full flex flex-col gap-2">
                      {/* X-axis: days (MM-DD). The corner cell labels the two axes:
                          rows = firmware version, columns = date. */}
                      <div className="flex items-end gap-2 h-14 shrink-0">
                        <div className="w-28 shrink-0 flex flex-col justify-end pb-1 leading-tight font-mono text-[10px]">
                          <span className="text-slate-400">↓ Firmware Ver.</span>
                          <span className="text-slate-400">→ Date</span>
                        </div>
                        {fwDays.map(day => (
                          <div key={day} className="flex-1 text-center">
                            <span className="text-[11px] font-mono text-slate-400">{String(day).slice(5)}</span>
                          </div>
                        ))}
                      </div>

                      {/* Rows: firmware versions — flex-fill the panel height so the
                          (few) firmware rows fill the panel instead of leaving white space
                          below. Each row label carries the fault direction (↑ over / ↓ under);
                          acute fault cells are glyphed + the hover gives the model breakdown. */}
                      <div className="flex-1 flex flex-col gap-2">
                      {fwRows.map(fw => {
                        const cohort = fwCohortByFw[fw];   // faulted firmware → direction + models
                        const cohortModels = cohort ? cohort.models.map(m => `${m.model} ${m.devices}`).join(' / ') : '';
                        return (
                        <div key={fw} className="flex items-stretch gap-2 flex-1">
                          <div className="w-28 shrink-0 flex flex-col justify-center pr-1 leading-tight">
                            <span className="text-sm text-slate-300 font-mono">{fw}</span>
                            {cohort && (
                              <span className={`text-[10px] font-mono ${cohort.direction === 'positive' ? 'text-rose-300' : 'text-sky-300'}`}>
                                {dirGlyph(cohort.direction)} {dirWord(cohort.direction)}-read
                              </span>
                            )}
                          </div>
                          {fwDays.map(day => {
                            const cell = fwHeat.find(d => d.firmware_version === fw && d.day === day);
                            const has = !!cell;
                            // Scope toggle: in-incident = peak fault severity (cell.mae hybrid);
                            // fleet-wide = all-readings average (cell.maeFleet, fault diluted).
                            const mae = has ? (fwScope === 'fleet-wide' ? cell.maeFleet : cell.mae) : 0;
                            // Direction glyphs mark ACUTE faults — only meaningful in in-incident
                            // scope (fleet-wide dilutes below the 25 threshold, so they'd vanish anyway).
                            const faultCell = has && fwScope === 'in-incident' && mae >= 25 && !!cohort;

                            return (
                              <div
                                key={day}
                                className="flex-1 min-h-[2.25rem] rounded-lg hover:ring-2 hover:ring-cyan-500 hover:ring-offset-2 hover:ring-offset-slate-900 transition-all relative group cursor-default"
                                style={{ backgroundColor: has ? getMaeColor(mae) : 'rgb(15 23 42)' }}
                              >
                                {faultCell && (
                                  <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                                    <span className="text-white font-bold text-sm" style={{ textShadow: '0 1px 2px rgba(0,0,0,0.6)' }}>{dirGlyph(cohort.direction)}</span>
                                  </div>
                                )}
                                {/* Compact tooltip — sits ABOVE the cell (never covers it), stacked + narrow + subtle. */}
                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-20 pointer-events-none">
                                  <div className="bg-slate-950/95 border border-slate-700 rounded px-2 py-1 text-center leading-tight shadow-lg">
                                    <div className="text-slate-100 font-bold font-mono text-xs whitespace-nowrap">{has ? mae : '—'} mg/dL</div>
                                    <div className="text-slate-500 font-mono text-[10px] whitespace-nowrap">FW {fw} · {String(day).slice(5)}</div>
                                    {faultCell && (
                                      <div className={`font-mono text-[10px] whitespace-nowrap ${cohort.direction === 'positive' ? 'text-rose-300' : 'text-sky-300'}`}>{dirGlyph(cohort.direction)} {dirWord(cohort.direction)}-read</div>
                                    )}
                                    {faultCell && cohortModels && (
                                      <div className="text-slate-400 font-mono text-[10px] whitespace-nowrap">{cohortModels}</div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                        );
                      })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Legend (colorbar) — device error mg/dL, clean→fault left to right. */}
                {!fwHeatLoading && fwHeat.length > 0 && (
                  <div className="flex items-center gap-2 pl-28">
                    <span className="text-[10px] font-mono text-emerald-400 font-bold">0</span>
                    <span className="text-[10px] font-mono text-slate-500">clean</span>
                    <div className="flex-1 flex flex-row rounded overflow-hidden">
                      {Array.from({ length: 21 }, (_, i) => i / 20).map((n, i) => (
                        <div
                          key={i}
                          className="flex-1 h-5"
                          style={{ backgroundColor: getMaeColor(n * fwMaeMax) }}
                        />
                      ))}
                    </div>
                    <span className="text-[10px] font-mono text-slate-500">fault</span>
                    <span className="text-[10px] font-mono text-rose-400 font-bold">~{Math.round(fwMaeMax)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Device Pattern Alerts */}
            <div className="col-span-5 bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
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
                  // of echoing its colored bars. Top out-of-range patterns by reading volume.
                  // Two-line rows so device·firmware (line 1) and region·tracking (line 2)
                  // aren't truncated. The severity dot is sized + coloured by out-of-range
                  // rate (bigger/redder = worse), scaled across the shown alerts so it reads
                  // at a glance — orange→rose ramp (no green: even the lowest shown rate is high).
                  const rates = alerts.map(a => a.rate_pct);
                  const lo = Math.min(...rates), hi = Math.max(...rates);
                  const lerp = (a, b, t) => Math.round(a + (b - a) * t);
                  const dotStyle = (r) => {
                    const t = hi > lo ? (r - lo) / (hi - lo) : 1;       // 0..1 across shown alerts
                    const px = 8 + t * 6;                                // 8..14px
                    return { width: `${px}px`, height: `${px}px`, backgroundColor: `rgb(${lerp(251, 244, t)} ${lerp(146, 63, t)} ${lerp(60, 94, t)})` };
                  };
                  return (
                    <div className="flex-1 flex flex-col">
                      {/* column key */}
                      <div className="flex items-center gap-3 pb-2 mb-1 border-b border-slate-800/70 text-[10px] font-mono uppercase tracking-wide text-slate-500">
                        <span className="w-4 shrink-0" />
                        <span className="w-4 shrink-0" />
                        <span className="flex-1 min-w-0">device · firmware · region</span>
                        <span className="shrink-0 w-16 text-right text-amber-400/80">OOR reads</span>
                        <span className="shrink-0 w-12 text-right">rate</span>
                      </div>
                      <ol className="flex-1 flex flex-col justify-between divide-y divide-slate-800/70">
                        {[...alerts].sort((a, b) => b.oorEvents - a.oorEvents).map((alert, idx) => (
                          <li key={idx} className="flex items-center gap-3 py-2.5">
                            <span className="text-xs font-mono text-slate-600 w-4 text-right shrink-0">{idx + 1}</span>
                            <span className="w-4 flex justify-center shrink-0">
                              <span className="rounded-full" style={dotStyle(alert.rate_pct)} title={`out-of-range rate ${alert.rate_pct}%`} />
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-mono text-slate-200 truncate">{alert.device_type} {alert.firmware_version}</div>
                              <div className="text-[11px] font-mono text-slate-500 truncate">{alert.region} · {alert.days_tracked}d tracked</div>
                            </div>
                            <span className="text-sm font-mono text-amber-400 shrink-0 w-16 text-right tabular-nums">{alert.oorEvents.toLocaleString()}</span>
                            <span className="text-xs font-mono text-slate-500 shrink-0 w-12 text-right tabular-nums">{alert.rate_pct}%</span>
                          </li>
                        ))}
                      </ol>
                      {/* key — one line per item */}
                      <div className="mt-3 pt-2 border-t border-slate-800/70 text-[10px] font-mono text-slate-500 leading-relaxed space-y-0.5">
                        <div><span className="text-amber-400/80">OOR reads</span> = count of out-of-range device readings</div>
                        <div><span className="text-slate-300">rate</span> = share of that group's readings out of range</div>
                        <div>● dot — bigger / redder = higher out-of-range rate</div>
                      </div>
                    </div>
                  );
                })()
              )}
            </div>
          </div>

          {/* Why-device-error note — explains the metric choice (why NOT a whole-window
              out-of-range rate): the real HUPA-UCM baseline (~31–39% OOR even on healthy
              firmware) would dilute a 12h fault. Keeps oorBaselineRange/baselineNote
              (computed from the live OOR data) in use. */}
          <div className="mt-6 bg-slate-900/30 border border-slate-800/70 rounded-lg px-5 py-3 text-[11px] font-mono text-slate-500 leading-relaxed">
            <span className="text-slate-300">Why device error? </span>
            The <span className="text-slate-400">Firmware × Day</span> heatmap reads <span className="text-slate-400">device error</span> directly (mean |observed − true|, ≈0 clean → ~40 faulted): <span className="text-slate-400">which firmware drifts, when, how much, and which way</span> — the <span className="text-rose-300">↑ over</span> / <span className="text-sky-300">↓ under</span>-read glyph + row label name the direction and faulted models (the per-model breakdown is on the <span className="text-slate-400">Firmware Lifecycle</span> page). We measure error directly because a whole-window <span className="text-slate-400">out-of-range rate</span> reads <span className="text-slate-400">{oorBaselineRange}</span> even on healthy firmware — glucose comes from <span className="text-slate-400">{baselineNote.source}</span>, {baselineNote.why} — so that baseline would <span className="text-amber-400/80">dilute</span> a 12h fault. Honest signal, no data inflation.
          </div>
        </section>

        {/* Device troubleshooting moved to the global assistant (FAB, bottom-right):
            ask the "Device support" mode for sensor/firmware/calibration help. */}

        {/* Device Detail Table */}
        <section data-tour="out-of-range-table">
          {(focusModel || focusDevice) && (
            <div className="mb-4 flex items-center justify-between gap-3 px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/5">
              <span className="text-xs font-mono text-cyan-300">
                {focusDevice ? (
                  focusRow ? (
                    <>Focused on <span className="text-slate-200">{focusRow.device_id}</span> · patient <span className="text-slate-200">{focusRow.patient_id}</span> · model <span className="text-slate-200">{focusRow.device_type}</span><span className="text-slate-500"> — showing its latest reading below (out-of-range gate overridden); <button onClick={clearFocus} className="underline hover:text-cyan-200">clear</button> for the full fleet</span></>
                  ) : focusLoading ? (
                    <>Loading <span className="text-slate-200">{focusDevice}</span>…</>
                  ) : (
                    <>Couldn't load <span className="text-slate-200">{focusDevice}</span><span className="text-slate-500"> — showing all {focusModel || 'matching'} devices</span></>
                  )
                ) : (
                  <>Focused from a patient · model <span className="text-slate-200">{focusModel}</span><span className="text-slate-500"> — fleet filtered to this device's model</span></>
                )}
              </span>
              <button onClick={clearFocus} className="text-xs font-mono text-slate-400 hover:text-slate-200 shrink-0">clear ✕</button>
            </div>
          )}
          {/* Layered time context — "then / recent / now" — so the focus view never
              contradicts the alert or watchlist that sent the visitor here. */}
          {focusDevice && focusRow && focusCtx && (
            <div className="mb-4 px-3 py-2.5 rounded-lg border border-slate-700 bg-slate-900/50 text-[11px] font-mono space-y-1">
              {focusCtx.snap && (
                <p className="text-slate-400">
                  <span className="text-slate-300">🕰 Fault window</span> (peak, {focusCtx.snap.time}): device showed{' '}
                  <span className={focusCtx.snap.direction === 'positive' ? 'text-rose-300' : 'text-sky-300'}>{focusCtx.snap.observed}</span> vs true{' '}
                  <span className="text-slate-200">{focusCtx.snap.trueGlucose}</span> mg/dL — {focusCtx.snap.direction === 'positive' ? '↑ over-read by' : '↓ under-read by'} ~{Math.abs(focusCtx.snap.observed - focusCtx.snap.trueGlucose)}
                </p>
              )}
              {focusCtx.recent && (
                <p className="text-slate-400">
                  <span className="text-slate-300">⏱ Last 3h</span>: {(focusCtx.recent.veryLow || focusCtx.recent.veryHigh)
                    ? <><span className="text-sky-300">{focusCtx.recent.veryLow} very-low</span> · <span className="text-rose-300">{focusCtx.recent.veryHigh} very-high</span> readings (range {focusCtx.recent.min}–{focusCtx.recent.max} mg/dL)</>
                    : <>no danger-band readings{focusCtx.recent.min != null ? ` (range ${focusCtx.recent.min}–${focusCtx.recent.max} mg/dL)` : ''}</>}
                </p>
              )}
              <p className="text-slate-500">
                <span className="text-slate-400">📍 Now</span>: the latest reading below{focusCtx.snap ? ' — in-range here means the fix landed for this device' : ''}.
              </p>
              {/* the return edge of the triage loop: investigate here (incl. Deeper
                  Analysis), then circle back to the alert to record the resolution */}
              {lakebaseConfigured && focusRow?.patient_id && (
                <button
                  onClick={() => navigate(`/triage?q=${encodeURIComponent(focusRow.patient_id)}`)}
                  className="mt-1 text-[11px] font-mono px-2 py-1 rounded border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10"
                  title="Back to this patient's alert in the triage queue — pick the resolution your investigation points to"
                >⚑ work this device's alert in Triage →</button>
              )}
            </div>
          )}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                {focusDevice ? 'Focused device · latest reading' : 'Out-of-Range Device Readings'}
              </h2>
              <p className="text-xs text-slate-500 font-mono mt-1">
                {focusDevice
                  ? <>The latest reading for the device you came from — any range · <span className="text-cyan-400/80">click the row</span> for details + AI device analysis</>
                  : <>Flagged readings outside the 70–180 mg/dL target — latest snapshot · <span className="text-cyan-400/80">click any row</span> for reading details + AI device analysis</>}
              </p>
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
            {(focusDevice ? focusLoading : devicesLoading) ? (
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
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Range</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Last Reading</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Glucose</th>
                      <th className="px-4 py-3 text-left text-xs font-mono text-slate-500 uppercase">Risk Score</th>
                      <th className="px-4 py-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {((focusDevice && focusRow)
                      ? [{
                          id: focusRow.device_id,
                          patient: focusRow.patient_id,
                          model: focusRow.device_type,
                          firmware: focusRow.firmware_version,
                          status: 'focus',
                          lastReading: focusRow.reading_time,
                          anomalyScore: calculateAnomalyScore(focusRow.glucose_value),
                          glucose_value: focusRow.glucose_value,
                        }]
                      : devices.filter(device => filterModel === 'all' || device.model === filterModel)
                    ).map((device, idx) => (
                  <React.Fragment key={idx}>
                    <tr
                      className={`border-b border-slate-800 hover:bg-slate-800/50 transition-colors cursor-pointer ${focusDevice && device.id === focusDevice ? 'bg-cyan-500/10 ring-1 ring-inset ring-cyan-500/40' : ''}`}
                      onClick={() => setExpandedDevice(expandedDevice === idx ? null : idx)}
                    >
                      <td className="px-4 py-3 text-sm font-mono text-cyan-400">{device.id}</td>
                      <td className="px-4 py-3 text-sm font-mono">
                        {/* cross-reference → this patient's Coach view (the AI rec's
                            "patient notification / clinical review"). stopPropagation so
                            it doesn't also toggle the row's reading-detail expander. */}
                        <button
                          onClick={(e) => { e.stopPropagation(); navigate(`/diabetes-coach?patient=${encodeURIComponent(device.patient)}`); }}
                          className="text-cyan-400 hover:text-cyan-300 hover:underline decoration-dotted underline-offset-2"
                          title={`Open ${device.patient} in Diabetes Coach`}
                        >
                          {device.patient}
                        </button>
                        {/* → this patient's alert in the triage queue (flag-gated) */}
                        {lakebaseConfigured && (
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/triage?q=${encodeURIComponent(device.patient)}`); }}
                            className="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded border border-cyan-500/30 text-cyan-400/80 hover:bg-cyan-500/10"
                            title={`Find ${device.patient} in the Alert Triage queue`}
                          >⚑ triage</button>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-slate-300">{device.model}</td>
                      <td className="px-4 py-3 text-sm font-mono text-slate-400">{device.firmware}</td>
                      <td className="px-4 py-3">
                        {(() => {
                          const b = glucoseBand(device.glucose_value);
                          return (
                            <span className={`inline-block px-2 py-1 rounded-full text-xs font-mono border whitespace-nowrap ${b.cls}`}>
                              {b.label}
                            </span>
                          );
                        })()}
                      </td>
                      <td className="px-4 py-3 text-sm font-mono text-slate-400">{device.lastReading}</td>
                      <td className="px-4 py-3">
                        <span className={`text-sm font-mono font-bold ${
                          (device.glucose_value < 54 || device.glucose_value > 250) ? 'text-rose-400'
                            : (device.glucose_value < 70 || device.glucose_value > 180) ? 'text-amber-400'
                            : 'text-emerald-400'
                        }`}>
                          {device.glucose_value ? `${Math.round(device.glucose_value)} mg/dL` : 'N/A'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${
                                device.anomalyScore > 0.85 ? 'bg-rose-500' :
                                device.anomalyScore > 0.7 ? 'bg-amber-500' :
                                device.anomalyScore > 0.4 ? 'bg-yellow-500' :
                                'bg-emerald-500'
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
                            {/* Reading Details — ONE band → ONE color, used by the value,
                                the Range Status text, and the action banner below (a mixed
                                amber value + white status + rose banner read as three
                                different severities for the same reading — booth catch). */}
                            {(() => { const v = device.glucose_value;
                              const band = (v < 54 || v > 250) ? 'critical' : (v < 70 || v > 180) ? 'warn' : 'ok';
                              const bandText = band === 'critical' ? 'text-rose-400' : band === 'warn' ? 'text-amber-400' : 'text-emerald-400';
                              return (
                            <div>
                              <h4 className="text-sm font-medium text-slate-300 mb-3">Reading Details</h4>
                              <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Glucose Value:</span>
                                  <span className={`font-mono font-bold ${bandText}`}>
                                    {Math.round(v)} mg/dL
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Range Status:</span>
                                  <span className={bandText}>
                                    {v < 54 ? 'Very Low (<54)' :
                                     v < 70 ? 'Low (54–69)' :
                                     v > 250 ? 'Very High (>250)' :
                                     v > 180 ? 'High (181–250)' :
                                     'In range (70–180)'}
                                  </span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Reading time:</span>
                                  <span className="text-slate-300 font-mono">{device.lastReading}</span>
                                </div>
                                <div className="flex justify-between">
                                  <span className="text-slate-500">Risk Score:</span>
                                  <span className="text-slate-300 font-mono">{(device.anomalyScore * 100).toFixed(0)}%</span>
                                </div>
                              </div>
                              
                              {band === 'critical' ? (
                                <div className="mt-4 p-3 bg-rose-500/5 border border-rose-500/20 rounded text-xs text-rose-300">
                                  ⚠️ <strong>Action Required:</strong> This reading is in a danger band (&lt;54 / &gt;250). Consider patient notification and clinical review.
                                </div>
                              ) : band === 'warn' ? (
                                <div className="mt-4 p-3 bg-amber-500/5 border border-amber-500/20 rounded text-xs text-amber-300">
                                  ⚠️ <strong>Monitor:</strong> This reading is outside the 70–180 target band. Keep watching; escalate if it trends toward the danger bands.
                                </div>
                              ) : (
                                <div className="mt-4 p-3 bg-emerald-500/5 border border-emerald-500/20 rounded text-xs text-emerald-300">
                                  ✓ <strong>Within range:</strong> this reading is inside the 70–180 mg/dL target — no action needed.
                                </div>
                              )}
                            </div>
                              ); })()}
                            
                            {/* Device Analysis — FM (fleet-grounded), device-technical focus (not patient clinical care) */}
                            <div>
                              <h4 className="text-sm font-medium text-slate-300 mb-3">Device Analysis</h4>
                              
                              {!deviceAnalysis[device.id] && !analysisLoading[device.id] && (
                                <div className="text-center py-8">
                                  <Brain className="w-12 h-12 text-cyan-400 mx-auto mb-3 opacity-50" />
                                  <p className="text-sm text-slate-400 mb-4">
                                    Get an AI-powered device analysis and recommendations<br/>
                                    for this unit — calibration, sensor, firmware, connectivity — from its readings and fleet context.
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
                                  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-4 text-sm text-slate-300 max-w-none">
                                    <ReactMarkdown components={mdComponents}>{deviceAnalysis[device.id]}</ReactMarkdown>
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

