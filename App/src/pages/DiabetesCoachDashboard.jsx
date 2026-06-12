import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { HeartHandshake, Search, TrendingUp, TrendingDown, AlertCircle, Users, Loader2, ChevronRight, Wrench, User } from 'lucide-react';
import { getPopulationMetrics, getInsulinMetrics, getPatientList, getPatientDetail } from './DiabetesCoachDashboard/queries';
import { getFirmwareLifecycle } from '../api/databricksSQL';

export default function DiabetesCoachDashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  // Back button: return to wherever we arrived from (e.g. Population Risk row-click,
  // the rail, or Home). location.key === 'default' means a direct/deep-link load with
  // no in-app history to pop, so fall back to Home rather than leaving the app.
  const goBack = () => (location.key === 'default' ? navigate('/') : navigate(-1));

  // Clinical metrics state (population-level — already live)
  const [populationMetrics, setPopulationMetrics] = useState(null);
  const [insulinMetrics, setInsulinMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  // Per-patient state (GitHub #5 — replaces the hardcoded Sarah-K. demo panel)
  const [selectedPatientId, setSelectedPatientId] = useState(null);
  const [patientDetail, setPatientDetail] = useState(null);
  const [patientLoading, setPatientLoading] = useState(true);
  const [searchText, setSearchText] = useState('');
  const [patientOptions, setPatientOptions] = useState([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const searchTimer = useRef(null);
  const [searchParams] = useSearchParams();
  // {firmwareVersion: peakMAE} for firmwares whose calibration error spiked (the
  // faulty rollout) — used to flag a patient whose device runs that firmware.
  const [firmwareFlags, setFirmwareFlags] = useState({});
  // Hovered reading index on the glucose-history profile (null = not hovering).
  const [hoverIdx, setHoverIdx] = useState(null);

  // Fetch population-level clinical metrics + which firmwares are faulty
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setMetricsLoading(true);
        const [popMetrics, insulinData, firmware] = await Promise.all([
          getPopulationMetrics(),
          getInsulinMetrics(),
          getFirmwareLifecycle()
        ]);
        setPopulationMetrics(popMetrics);
        setInsulinMetrics(insulinData);
        // Peak MAE per firmware; flag versions clearing the same >=5 mg/dL bar the
        // Firmware Lifecycle page uses to call a rollout "faulty".
        const peak = {};
        firmware.forEach((d) => { peak[d.firmwareVersion] = Math.max(peak[d.firmwareVersion] || 0, d.mae); });
        setFirmwareFlags(Object.fromEntries(Object.entries(peak).filter(([, v]) => v >= 5)));
      } catch (error) {
        console.error('Failed to fetch clinical metrics:', error);
      } finally {
        setMetricsLoading(false);
      }
    };
    fetchMetrics();
  }, []);

  // Load the initial patient list and auto-select the first patient
  useEffect(() => {
    (async () => {
      const list = await getPatientList('');
      setPatientOptions(list);
      // Deep-link wins (drill-down from Population Risk: /diabetes-coach?patient=PSEUDO_xxxx);
      // otherwise a random default so each visit surfaces a different patient.
      const requested = searchParams.get('patient');
      if (requested) {
        selectPatient(requested);
      } else if (list.length > 0) {
        selectPatient(list[Math.floor(Math.random() * list.length)].patientId);
      } else {
        setPatientLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectPatient = async (pid) => {
    setSelectedPatientId(pid);
    setSearchOpen(false);
    setSearchText('');
    setPatientLoading(true);
    try {
      setPatientDetail(await getPatientDetail(pid));
    } catch (e) {
      console.error('Failed to load patient detail:', e);
      setPatientDetail(null);
    } finally {
      setPatientLoading(false);
    }
  };

  // Debounced server-side typeahead (patient_id LIKE) — never loads all ~1000.
  const handleSearch = (text) => {
    setSearchText(text);
    setSearchOpen(true);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(async () => {
      setPatientOptions(await getPatientList(text));
    }, 250);
  };

  // ── Derived per-patient values (all from real fetched data) ──
  const demo = patientDetail?.demographics;
  const kpis = patientDetail?.kpis;
  const fc = patientDetail?.forecast;
  const incident = patientDetail?.incident;
  const series = patientDetail?.series || [];
  // Peak MAE if this patient's device runs a flagged (faulty) firmware, else undefined.
  const fwFlagPeak = kpis?.firmware ? firmwareFlags[kpis.firmware] : undefined;

  const windowDays = kpis?.firstTime && kpis?.lastTime
    ? Math.max(1, Math.round((new Date(kpis.lastTime) - new Date(kpis.firstTime)) / 86400000))
    : null;

  // ── glucose-history chart scale (dynamic y w/ headroom so spikes/lows aren't clipped) ──
  const gVals = series.flatMap((d) => [d.observed, d.glucoseTrue].filter((v) => v != null));
  const dataMin = gVals.length ? Math.min(...gVals) : 50;
  const dataMax = gVals.length ? Math.max(...gVals) : 250;
  // pad ~10 mg/dL each side, round to 10s; never below 0; keep at least a 50–250 frame.
  const gMin = Math.max(0, Math.min(50, Math.floor((dataMin - 10) / 10) * 10));
  const gMax = Math.max(250, Math.ceil((dataMax + 10) / 10) * 10);
  // value → vertical % (0 = top). Clamped for safety.
  const yOf = (v) => Math.max(0, Math.min(100, 100 - ((v - gMin) / (gMax - gMin)) * 100));
  const xOf = (i) => (series.length > 1 ? (i / (series.length - 1)) * 100 : 0);
  const gridVals = [0, 25, 50, 75, 100].map((t) => Math.round(gMax - (t / 100) * (gMax - gMin)));
  // Incident window → x% span for shading (series is time-ordered ~uniform 5-min readings).
  const iw = patientDetail?.incidentWindow;
  const incX = (() => {
    if (!iw || series.length < 2) return null;
    const s = new Date(iw.start).getTime(), e = new Date(iw.end).getTime();
    const idxs = series.map((d, i) => ({ t: new Date(d.time).getTime(), i })).filter((o) => o.t >= s && o.t <= e).map((o) => o.i);
    return idxs.length ? { x1: xOf(idxs[0]), x2: xOf(idxs[idxs.length - 1]) } : null;
  })();
  // "Now" window — the trailing 3 hours (the same lookback the High-Risk tile and
  // the Triage live watchlist scan, <54/>250). Shaded only when it actually contains
  // danger-band readings, so the chart shows WHY this patient is flagged as current.
  const nowX = (() => {
    if (series.length < 2) return null;
    const lastT = new Date(series[series.length - 1].time).getTime();
    const cutoff = lastT - 3 * 3600 * 1000;
    const idxs = series.map((d, i) => ({ t: new Date(d.time).getTime(), i })).filter((o) => o.t >= cutoff).map((o) => o.i);
    if (!idxs.length) return null;
    const danger = idxs.some((i) => { const v = series[i].observed; return v != null && (v < 54 || v > 250); });
    return danger ? { x1: xOf(idxs[0]), x2: xOf(idxs[idxs.length - 1]) } : null;
  })();
  const fmtTick = (t) => new Date(t).toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit' });
  // "Now" chip → forecast handoff: scroll the forecast card into view + flash it
  // (what just happened → where it's heading).
  const [forecastFlash, setForecastFlash] = useState(false);
  const jumpToForecast = () => {
    document.getElementById('forecast-panel')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setForecastFlash(true);
    setTimeout(() => setForecastFlash(false), 1800);
  };

  // Rule-based risk band (not a trained classifier), built on the SYMMETRIC Battelino
  // 2019 Time-in-Ranges bands: Very Low <54 / Low <70 / Target 70–180 / High >180 /
  // Very High >250 (targets: <54 <1%, <70 <4%, >180 <25%, >250 <5%, CV <=36%, TIR >70%).
  //   HIGH     — a level-2 DANGER band elevated to >=2x its target: Very Low (<54) >=2%
  //              OR Very High (>250) >=10% OR poor overall control (TIR <50%).
  //   LOW      — every consensus target met.
  //   MODERATE — in between.
  // Symmetric on both ends; the <54 band is what escalates dangerous hypo (e.g. a
  // 78%-TIR / 13%-hypo patient with 4% very-low → HIGH). Data-agnostic: works on
  // synthetic (idealized → mostly LOW) and real baselines alike — only the distribution
  // shifts. Full static Tailwind classes so the JIT compiler doesn't purge them.
  const risk = kpis
    ? ((kpis.pctVeryLow >= 2 || kpis.pctVeryHigh >= 10 || kpis.timeInRange < 50) ? { label: 'HIGH', box: 'bg-rose-500/10 border-rose-500/30', text: 'text-rose-400' }
      : (kpis.timeInRange >= 70 && kpis.pctHypo < 4 && kpis.pctHyper < 25 && kpis.cv <= 36) ? { label: 'LOW', box: 'bg-emerald-500/10 border-emerald-500/30', text: 'text-emerald-400' }
      : { label: 'MODERATE', box: 'bg-amber-500/10 border-amber-500/30', text: 'text-amber-400' })
    : { label: '—', box: 'bg-slate-500/10 border-slate-500/30', text: 'text-slate-400' };

  // Cautionary flags: an ELEVATED (level-1) band over its target but not yet HIGH —
  // surfaced on MODERATE/LOW cards so neither end is silently under-read (over-cautious;
  // HIGH cards already convey danger). Symmetric: hypo <70 >=4%, hyper >180 >=25%.
  const hypoFlag = !!kpis && risk.label !== 'HIGH' && kpis.pctHypo >= 4;
  const hyperFlag = !!kpis && risk.label !== 'HIGH' && kpis.pctHyper >= 25;

  // Honest, data-derived observations (replaces the old hardcoded pattern list).
  const observations = kpis ? [
    { type: 'Hypoglycemia exposure', detail: `${kpis.pctHypo}% of readings < 70 mg/dL`, severity: kpis.pctHypo >= 4 ? 'high' : kpis.pctHypo > 0 ? 'medium' : 'low' },
    { type: 'Hyperglycemia exposure', detail: `${kpis.pctHyper}% of readings > 180 mg/dL`, severity: kpis.pctHyper >= 25 ? 'high' : kpis.pctHyper > 0 ? 'medium' : 'low' },
    { type: 'Glycemic variability', detail: `CV ${kpis.cv}% (target < 36%)`, severity: kpis.cv >= 36 ? 'high' : 'low' },
  ] : [];

  const classify = (g) => g == null ? null
    : g < 70 ? { label: 'Hypo', cls: 'text-rose-400 bg-rose-500/10 border-rose-500/30' }
    : g > 180 ? { label: 'Hyper', cls: 'text-amber-400 bg-amber-500/10 border-amber-500/30' }
    : { label: 'In range', cls: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30' };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={goBack}
              aria-label="Back"
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                <HeartHandshake className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                  Diabetes Coach Dashboard
                </h1>
                <p className="text-xs text-slate-500 font-mono">Provider Encounter Preparation</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-xs font-mono text-emerald-400">UC · gold</span>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8">
        {/* Population-Level Clinical Metrics */}
        <section className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Users className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
              Population Clinical Metrics
            </h2>
            <span className="text-xs text-slate-500 font-mono">(Last 24 Hours)</span>
          </div>

          <div className="grid grid-cols-6 gap-4 mb-6">
            {/* Time in Range - Most Important */}
            <div className="bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/30 rounded-lg p-5 hover:border-emerald-500/50 transition-colors">
              <p className="text-xs text-emerald-400 font-mono mb-2">TIME IN RANGE</p>
              <p className="text-3xl font-mono font-bold text-emerald-400">
                {metricsLoading ? '...' : (populationMetrics?.timeInRange != null ? `${populationMetrics.timeInRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">70-180 mg/dL</p>
              <div className="mt-3 h-1.5 bg-slate-900 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                  style={{ width: `${populationMetrics?.timeInRange || 0}%` }}
                />
              </div>
            </div>

            {/* Average Glucose */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">AVG GLUCOSE</p>
              <p className="text-3xl font-mono font-bold text-slate-200">
                {metricsLoading ? '...' : (populationMetrics?.avgGlucose != null ? populationMetrics.avgGlucose : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">mg/dL</p>
              {populationMetrics?.stddevGlucose && (
                <p className="text-xs text-slate-600 mt-1">±{populationMetrics.stddevGlucose} SD</p>
              )}
            </div>

            {/* Hypoglycemia */}
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-5 hover:border-rose-500/50 transition-colors">
              <p className="text-xs text-rose-400 font-mono mb-2">HYPOGLYCEMIA</p>
              <p className="text-3xl font-mono font-bold text-rose-400">
                {metricsLoading ? '...' : (populationMetrics?.pctTimeBelowRange != null ? `${populationMetrics.pctTimeBelowRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">&lt;70 mg/dL</p>
              {populationMetrics?.patientsWithHypo && (
                <p className="text-xs text-rose-400/60 mt-1">{populationMetrics.patientsWithHypo} patients</p>
              )}
            </div>

            {/* Hyperglycemia */}
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-5 hover:border-amber-500/50 transition-colors">
              <p className="text-xs text-amber-400 font-mono mb-2">HYPERGLYCEMIA</p>
              <p className="text-3xl font-mono font-bold text-amber-400">
                {metricsLoading ? '...' : (populationMetrics?.pctTimeAboveRange != null ? `${populationMetrics.pctTimeAboveRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">&gt;180 mg/dL</p>
              {populationMetrics?.patientsWithHyper && (
                <p className="text-xs text-amber-400/60 mt-1">{populationMetrics.patientsWithHyper} patients</p>
              )}
            </div>

            {/* Patients Monitored */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">PATIENTS</p>
              <p className="text-3xl font-mono font-bold text-cyan-400">
                {metricsLoading ? '...' : (populationMetrics?.totalPatientsMonitored != null ? populationMetrics.totalPatientsMonitored : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">Monitored</p>
              <div className="mt-3 flex items-center gap-1">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-xs text-emerald-400 font-mono">Active</span>
              </div>
            </div>

            {/* Glucose Range */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">GLUCOSE RANGE</p>
              <div className="flex items-baseline gap-2">
                <p className="text-2xl font-mono font-bold text-slate-200">
                  {metricsLoading ? '...' : (populationMetrics?.minGlucose != null ? Math.round(populationMetrics.minGlucose) : 'N/A')}
                </p>
                <span className="text-slate-500 px-0.5">–</span>
                <p className="text-2xl font-mono font-bold text-slate-200">
                  {metricsLoading ? '...' : (populationMetrics?.maxGlucose != null ? Math.round(populationMetrics.maxGlucose) : 'N/A')}
                </p>
              </div>
              <p className="text-xs text-slate-500 mt-2">mg/dL</p>
            </div>
          </div>

          {/* Insulin Delivery Metrics */}
          {insulinMetrics && (
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">BASAL EVENTS</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.basalEvents?.toLocaleString() || 'N/A'}
                </p>
                {insulinMetrics.avgBasalRate && (
                  <p className="text-xs text-slate-600 mt-1">Avg: {insulinMetrics.avgBasalRate}u/hr</p>
                )}
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">BOLUS EVENTS</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.bolusEvents?.toLocaleString() || 'N/A'}
                </p>
                {insulinMetrics.avgBolusVolume && (
                  <p className="text-xs text-slate-600 mt-1">Avg: {insulinMetrics.avgBolusVolume}u</p>
                )}
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">CARB ENTRIES</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.carbEvents?.toLocaleString() || 'N/A'}
                </p>
                <p className="text-xs text-slate-600 mt-1">Patient logged</p>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">HYPO EVENTS</p>
                <p className="text-xl font-mono font-bold text-rose-400">
                  {populationMetrics?.hypoEvents?.toLocaleString() || 'N/A'}
                </p>
                <p className="text-xs text-slate-600 mt-1">Readings &lt;70</p>
              </div>
            </div>
          )}
        </section>

        {/* Patient Selector — live typeahead over the simulated patient cohort */}
        <section className="mb-8">
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500 z-10" />
              <input
                type="text"
                value={searchText}
                onChange={(e) => handleSearch(e.target.value)}
                onFocus={() => setSearchOpen(true)}
                placeholder="Search patient ID (e.g. PSEUDO_0000355) — simulated cohort, no real PHI"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-12 pr-4 py-3 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
              />
              {searchOpen && patientOptions.length > 0 && (
                <div className="absolute z-20 mt-1 w-full max-h-72 overflow-y-auto bg-slate-950 border border-slate-700 rounded-lg shadow-xl">
                  {patientOptions.map((p) => (
                    <button
                      key={p.patientId}
                      onClick={() => selectPatient(p.patientId)}
                      className={`w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-slate-800/70 transition-colors border-b border-slate-800/50 last:border-0 ${p.patientId === selectedPatientId ? 'bg-slate-800/40' : ''}`}
                    >
                      <span className="text-sm font-mono text-slate-200">{p.patientId}</span>
                      <span className="text-xs font-mono text-slate-500">{p.deviceModel} · {p.region}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            {searchOpen && (
              <button onClick={() => setSearchOpen(false)} className="fixed inset-0 z-0 cursor-default" aria-hidden tabIndex={-1} />
            )}
          </div>
        </section>

        {/* Pre-Visit Summary Panel */}
        {patientLoading ? (
          <div className="flex items-center justify-center h-64 text-slate-500 mb-8">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading patient…
          </div>
        ) : !patientDetail ? (
          <div className="flex items-center justify-center h-32 text-slate-500 mb-8">No data for this patient.</div>
        ) : (
        <div className="grid grid-cols-12 gap-6 mb-8">
          {/* ⚠ Masked-severity alert — device under-read while the patient's TRUE glucose
              was hyper, so the displayed value under-reported danger. The unsafe failure mode. */}
          {incident?.maskedSeverity && (
            <div className="col-span-12 flex items-start gap-3 bg-rose-500/10 border border-rose-500/40 rounded-lg p-4">
              <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-semibold text-rose-300">⚠ Masked severity — device under-read during a calibration incident</p>
                <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                  This device <span className="text-rose-300">under-reported</span> by ~{Math.round(incident.biasGap)} mg/dL during the incident:
                  true glucose reached <span className="font-mono text-rose-300">~{Math.round(incident.trueMax)} mg/dL</span> but the device displayed
                  <span className="font-mono"> ~{Math.round(incident.obsAtPeak ?? incident.trueMax - incident.biasGap)} mg/dL</span> — hyperglycemia severity was <span className="text-rose-300">under-stated</span>.
                  Verify true status before acting on this device's readings.
                </p>
              </div>
            </div>
          )}
          {/* Left Column - Main Summary */}
          <div className="col-span-8 space-y-6">
            {/* Patient Header */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <User className="w-6 h-6 text-cyan-400 shrink-0" strokeWidth={2.25} />
                    <h2 className="text-2xl font-semibold font-mono" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                      {selectedPatientId}
                    </h2>
                    <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/30 rounded text-xs text-emerald-400 font-mono">Live</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-slate-400 font-mono">
                    <span>Age: {demo?.age ?? '—'}</span>
                    <span>•</span>
                    <span>{demo?.diagnosis === 'T1D' ? 'Type 1 Diabetes' : demo?.diagnosis === 'T2D' ? 'Type 2 Diabetes' : (demo?.diagnosis ?? '—')}</span>
                    <span>•</span>
                    <span>Device: {demo?.deviceModel ?? '—'}</span>
                  </div>
                </div>
                <div className={`px-4 py-2 border rounded-lg ${risk.box}`}>
                  <p className={`text-xs font-mono mb-1 ${risk.text}`}>RISK LEVEL</p>
                  <p className={`text-xl font-mono font-bold ${risk.text}`}>{risk.label}</p>
                  {(hypoFlag || hyperFlag) && (
                    <span className="mt-1 flex flex-wrap gap-1">
                      {hypoFlag && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/30"
                          title="Time-below-70 above the <4% consensus target — watch for hypoglycemia">
                          ⚠ hypo {kpis.pctHypo}%
                        </span>
                      )}
                      {hyperFlag && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30"
                          title="Time-above-180 above the <25% consensus target — watch for hyperglycemia">
                          ⚠ hyper {kpis.pctHyper}%
                        </span>
                      )}
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">AVG GLUCOSE</p>
                  <p className="text-2xl font-mono font-bold text-slate-200">{kpis?.avgGlucose ?? '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">mg/dL{windowDays ? ` (${windowDays}d)` : ''}</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">TIME IN RANGE</p>
                  <p className={`text-2xl font-mono font-bold ${kpis?.timeInRange >= 70 ? 'text-emerald-400' : 'text-amber-400'}`}>{kpis?.timeInRange != null ? `${kpis.timeInRange}%` : '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">Target: 70-180</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">HYPOGLYCEMIA</p>
                  <p className="text-2xl font-mono font-bold text-rose-400">{kpis?.pctHypo != null ? `${kpis.pctHypo}%` : '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">&lt;70 mg/dL</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">CV</p>
                  <p className="text-2xl font-mono font-bold text-slate-200">{kpis?.cv != null ? `${kpis.cv}%` : '—'}</p>
                  <p className="text-xs text-slate-500 mt-1">Variability</p>
                </div>
              </div>
            </div>

            {/* Glucose history — real full-window series, observed vs true with incident shading */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-sm font-medium text-slate-300 mb-1">Glucose History{windowDays ? ` (~${windowDays} days)` : ''}</h3>
                  <p className="text-xs text-slate-500 font-mono">{series.length} readings · device-observed vs true glucose</p>
                </div>
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 rounded border border-slate-800">
                    <div className="w-3 h-0.5 bg-cyan-400" />
                    <span className="text-[11px] text-slate-400 font-mono">Observed</span>
                  </div>
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 rounded border border-slate-800">
                    <div className="w-3 border-t border-dashed border-rose-400" />
                    <span className="text-[11px] text-slate-400 font-mono">True</span>
                  </div>
                  {incX && (
                    <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 rounded border border-slate-800">
                      <div className="w-3 h-2.5 bg-rose-500/20 border-x border-rose-500/40" />
                      <span className="text-[11px] text-slate-400 font-mono">Incident</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 rounded border border-slate-800">
                    <div className="w-3 h-0.5 bg-emerald-500" />
                    <span className="text-[11px] text-slate-400 font-mono">Target 70–180</span>
                  </div>
                  {nowX && (
                    <button onClick={jumpToForecast}
                      className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-950 rounded border border-amber-500/40 hover:bg-amber-500/10 cursor-pointer"
                      title="The trailing 3-hour window with very-low (<54) or very-high (>250) readings — the live-risk lookback that flags this patient as CURRENTLY at risk (same window as the High-Risk tile and the Triage live view). Click: jump to where it's heading (the near-term forecast).">
                      <div className="w-3 h-2.5 bg-amber-500/20 border-x border-amber-500/50" />
                      <span className="text-[11px] text-amber-300 font-mono">⚠ Now (last 3h) → forecast</span>
                    </button>
                  )}
                </div>
              </div>

              {/* ml-12 gutter so the -left-12 y-axis labels (250…50) sit inside the card */}
              <div className="relative h-64 ml-12">
                {/* Incident window shading (device-fault period) — drawn first so lines sit on top */}
                {incX && (
                  <div className="absolute top-0 bottom-0 bg-rose-500/10 border-x border-rose-500/30" style={{ left: `${incX.x1}%`, width: `${Math.max(0.5, incX.x2 - incX.x1)}%` }} />
                )}

                {/* "Now" live-risk window (trailing 3h with <54/>250 readings) — why this
                    patient is CURRENTLY flagged; amber to distinguish from the rose incident. */}
                {nowX && (
                  <div className="absolute top-0 bottom-0 bg-amber-500/10 border-x border-amber-500/40" style={{ left: `${nowX.x1}%`, width: `${Math.max(0.8, nowX.x2 - nowX.x1)}%` }} />
                )}

                {/* Target Range Band (70–180) — positioned on the dynamic scale */}
                <div className="absolute inset-x-0 bg-emerald-500/5 border-y border-emerald-500/20" style={{ top: `${yOf(180)}%`, height: `${yOf(70) - yOf(180)}%` }} />

                {/* Grid Lines + dynamic y labels */}
                {[0, 25, 50, 75, 100].map((val, idx) => (
                  <div key={val} className="absolute inset-x-0 border-t border-slate-800" style={{ top: `${val}%` }}>
                    <span className="absolute -left-12 -top-2 text-xs font-mono text-slate-600">{gridVals[idx]}</span>
                  </div>
                ))}

                {/* Glucose lines: true (dashed rose) + observed (solid cyan). Outside the
                    incident they overlap; during it the gap = the device under/over-read.
                    viewBox + unitless coords (SVG `points` rejects % units); non-scaling-stroke
                    keeps strokes ~constant despite preserveAspectRatio="none". */}
                {series.length > 1 && (
                  <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
                    <polyline
                      points={series.map((d, i) => `${xOf(i)},${yOf(d.glucoseTrue ?? d.observed)}`).join(' ')}
                      fill="none" stroke="rgb(251 113 133)" strokeWidth="1.5" strokeDasharray="3 2"
                      vectorEffect="non-scaling-stroke"
                    />
                    <polyline
                      points={series.map((d, i) => `${xOf(i)},${yOf(d.observed)}`).join(' ')}
                      fill="none" stroke="rgb(34 211 238)" strokeWidth="2"
                      vectorEffect="non-scaling-stroke"
                      className="drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]"
                    />
                  </svg>
                )}

                {/* Time Labels (first / mid / last) — date-aware for the multi-day window */}
                {series.length > 1 && (
                  <div className="absolute -bottom-6 inset-x-0 flex justify-between text-[11px] font-mono text-slate-600">
                    <span>{fmtTick(series[0].time)}</span>
                    <span>{fmtTick(series[Math.floor(series.length / 2)].time)}</span>
                    <span>{fmtTick(series[series.length - 1].time)}</span>
                  </div>
                )}

                {/* Hover overlay — maps cursor x to the nearest reading. The plot SVG is
                    stretched (preserveAspectRatio="none"), so we read pixels from this div
                    and map to the same unitless x/y the polylines use. */}
                {series.length > 1 && (() => {
                  const onMove = (e) => {
                    const r = e.currentTarget.getBoundingClientRect();
                    const frac = (e.clientX - r.left) / r.width;
                    setHoverIdx(Math.max(0, Math.min(series.length - 1, Math.round(frac * (series.length - 1)))));
                  };
                  const pt = hoverIdx != null ? series[hoverIdx] : null;
                  const xPct = pt != null ? xOf(hoverIdx) : 0;
                  const yPct = pt != null ? yOf(pt.observed) : 0;
                  const gap = pt != null && pt.glucoseTrue != null ? Math.round(pt.glucoseTrue - pt.observed) : null;
                  const flip = xPct > 62; // anchor tooltip left of the point near the right edge
                  return (
                    <div className="absolute inset-0 z-10" style={{ cursor: 'crosshair' }} onMouseMove={onMove} onMouseLeave={() => setHoverIdx(null)}>
                      {pt && (
                        <>
                          <div className="absolute top-0 bottom-0 w-px bg-cyan-400/40" style={{ left: `${xPct}%` }} />
                          {/* observed marker */}
                          <div className="absolute w-2.5 h-2.5 rounded-full bg-cyan-300 ring-2 ring-slate-950 -translate-x-1/2 -translate-y-1/2" style={{ left: `${xPct}%`, top: `${yPct}%` }} />
                          {/* true marker (only show distinctly when it diverges) */}
                          {pt.glucoseTrue != null && Math.abs(gap) >= 5 && (
                            <div className="absolute w-2 h-2 rounded-full bg-rose-400 ring-2 ring-slate-950 -translate-x-1/2 -translate-y-1/2" style={{ left: `${xPct}%`, top: `${yOf(pt.glucoseTrue)}%` }} />
                          )}
                          <div
                            className="absolute -translate-y-1/2 bg-slate-950/95 border border-slate-700 rounded px-2 py-1 whitespace-nowrap pointer-events-none shadow-lg"
                            style={{ left: `${xPct}%`, top: `${yPct}%`, transform: `translate(${flip ? 'calc(-100% - 12px)' : '12px'}, -50%)` }}
                          >
                            <div className="text-sm font-semibold text-cyan-300 font-mono">{Math.round(pt.observed)} <span className="text-[10px] text-slate-500">mg/dL observed</span></div>
                            {pt.glucoseTrue != null && (
                              <div className="text-xs font-mono text-rose-300">{Math.round(pt.glucoseTrue)} <span className="text-[10px] text-slate-500">true{gap ? ` (${gap > 0 ? '+' : ''}${gap})` : ''}</span></div>
                            )}
                            <div className="text-[10px] text-slate-500 font-mono">{new Date(pt.time).toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })()}
              </div>
            </div>

            {/* Observations — derived from this patient's real readings */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-1">Observations</h3>
              <p className="text-xs text-slate-500 font-mono mb-4">Derived from this patient's observed window{windowDays ? ` (${windowDays}d)` : ''}</p>
              {/* horizontal 3-up (was a vertical list) — fills the left column width
                  so the section sits compactly alongside the right-hand panels */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {observations.map((o, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-4 bg-slate-950 rounded border border-slate-800 hover:border-slate-700 transition-colors">
                    <div className={`w-9 h-9 shrink-0 rounded-lg flex items-center justify-center ${
                      o.severity === 'high' ? 'bg-rose-500/10 border border-rose-500/30' :
                      o.severity === 'medium' ? 'bg-amber-500/10 border border-amber-500/30' :
                      'bg-emerald-500/10 border border-emerald-500/30'
                    }`}>
                      <AlertCircle className={`w-5 h-5 ${
                        o.severity === 'high' ? 'text-rose-400' :
                        o.severity === 'medium' ? 'text-amber-400' :
                        'text-emerald-400'
                      }`} />
                    </div>
                    <div className="min-w-0">
                      <h4 className="text-sm font-medium text-slate-200 leading-tight">{o.type}</h4>
                      <p className="text-xs text-slate-500 font-mono mt-0.5">{o.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column - Forecast & Device */}
          <div className="col-span-4 space-y-6">
            {/* Near-term glucose forecast — real XGBoost 15/30-min model output */}
            <div id="forecast-panel" data-tour="coach-risk"
              className={`bg-slate-900/50 border border-slate-800 rounded-lg p-6 transition-shadow duration-500 ${forecastFlash ? 'ring-2 ring-amber-400/70 shadow-lg shadow-amber-500/20' : ''}`}>
              <h3 className="text-sm font-medium text-slate-300 mb-1">Near-term glucose forecast</h3>
              <p className="text-xs text-slate-500 font-mono mb-4">XGBoost · 15 / 30-min horizons · from last batch run</p>

              {fc ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-slate-950 rounded border border-slate-800">
                    <span className="text-xs text-slate-500 font-mono">Forecast baseline</span>
                    <span className="text-lg font-mono font-bold text-slate-200">{fc.glucoseObserved != null ? Math.round(fc.glucoseObserved) : '—'} <span className="text-xs text-slate-500">mg/dL</span></span>
                  </div>

                  {[{ label: '+15 min', val: fc.pred15m, delta: fc.delta15m }, { label: '+30 min', val: fc.pred30m, delta: fc.delta30m }].map((h, i) => {
                    const c = classify(h.val);
                    return (
                      <div key={i} className="p-3 bg-slate-950 rounded border border-slate-800">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-slate-500 font-mono">{h.label}</span>
                          {c && <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${c.cls}`}>{c.label}</span>}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xl font-mono font-bold text-slate-200">{h.val != null ? Math.round(h.val) : '—'}</span>
                          <span className="text-xs text-slate-500">mg/dL</span>
                          {h.delta != null && (
                            <span className={`flex items-center gap-0.5 text-xs font-mono ml-auto ${h.delta >= 0 ? 'text-amber-400' : 'text-cyan-400'}`}>
                              {h.delta >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                              {h.delta >= 0 ? '+' : ''}{Math.round(h.delta)}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Predicted CGM value vs the forecast baseline — the reading the model scored from in the
                    latest <span className="text-slate-500">batch</span> run (one row per patient, not a live tick).
                    Near-real-time scoring and a 60-min horizon are on the roadmap.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-slate-500">No forecast available for this patient.</p>
              )}
            </div>

            {/* Device — real registry + latest firmware */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Device</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Model</span>
                  <span className="text-sm font-mono text-slate-300">{demo?.deviceModel ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Device ID</span>
                  <span className="text-sm font-mono text-slate-300">{demo?.deviceId ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Firmware</span>
                  {fwFlagPeak != null ? (
                    <span className="text-sm font-mono text-rose-400 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {kpis.firmware}
                    </span>
                  ) : (
                    <span className="text-sm font-mono text-slate-300">{kpis?.firmware ?? '—'}</span>
                  )}
                </div>
                {fwFlagPeak != null && (
                  <button
                    onClick={() => navigate('/firmware-lifecycle')}
                    className="w-full text-left text-[11px] font-mono text-rose-300 bg-rose-500/5 border border-rose-500/30 rounded px-2 py-1.5 hover:bg-rose-500/10 transition-colors"
                  >
                    ⚠ Flagged firmware — calibration error spiked to {fwFlagPeak} mg/dL on this rollout. See Firmware Lifecycle →
                  </button>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Region</span>
                  <span className="text-sm font-mono text-slate-300">{demo?.region ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Readings</span>
                  <span className="text-sm font-mono text-slate-300">{kpis?.readings?.toLocaleString() ?? '—'}{windowDays ? ` · ${windowDays}d` : ''}</span>
                </div>
              </div>
              <button
                onClick={() => {
                  // Carry this patient's device into the fleet view so it opens
                  // pre-filtered to their model (+ best-effort highlight of the
                  // exact device if it surfaces in the out-of-range list).
                  const qs = new URLSearchParams();
                  if (demo?.deviceModel) qs.set('model', demo.deviceModel);
                  if (demo?.deviceId) qs.set('device', demo.deviceId);
                  const q = qs.toString();
                  navigate(q ? `/device-support?${q}` : '/device-support');
                }}
                className="mt-6 w-full flex items-center justify-center gap-1.5 text-sm font-mono px-3 py-2.5 rounded-lg border border-cyan-500/40 bg-cyan-500/10 text-cyan-300 hover:bg-cyan-500/20 hover:text-cyan-200 hover:border-cyan-500/60 transition-colors"
              >
<Wrench className="w-4 h-4 shrink-0" /> <span className="text-center leading-tight">Review this device<br />in fleet diagnostics</span> <ChevronRight className="w-4 h-4 shrink-0" />
              </button>
              {/* secondary: jump to the full (unfocused) fleet view */}
              <button
                onClick={() => navigate('/device-support')}
                className="mt-3.5 w-full flex items-center justify-center gap-1 text-xs font-mono text-slate-500 hover:text-slate-300 transition-colors"
              >
                or open the full fleet diagnostics <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
        )}

      </main>
    </div>
  );
}
