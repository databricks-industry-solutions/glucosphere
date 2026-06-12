import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, BellRing, ChevronDown, ChevronRight, Database } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchAlerts, alertAction, seedAlerts, resetAlerts, bulkAlerts } from '../api/triage';
import { getAllDeviceModels, getLiveRiskWatchlist, getPatientIncidentSnapshot } from '../api/databricksSQL';

// → ACT — the fleet-level act surface: a live alert queue with ack / assign /
// resolve + an audit trail, backed by Lakebase (Postgres OLTP) — the app's only
// WRITE path. Reached from Population Risk ("send to triage") and Firmware
// Lifecycle ("flag for rollback"); flag-gated end-to-end (useLakebaseConfigured
// client-side, 503s server-side), so non-Lakebase deploys never see it.

const SEV = {
  HIGH: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
  MEDIUM: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
};
const STATUS = {
  open: 'bg-rose-500/10 text-rose-300 border-rose-500/30',
  acked: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
  resolved: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
};
const FILTERS = ['open', 'acked', 'resolved', 'all'];

// Resolution outcomes — picked at resolve time, recorded in the audit trail.
// Deliberately includes the non-device and emergency paths: triage's job is
// routing, and "it wasn't the device" / "this is a medical emergency" are
// first-class outcomes, not edge cases.
const RESOLUTIONS = [
  '🔧 Firmware rolled back',
  '📦 Device replaced — swap shipped',
  '🩸 Fingerstick-verified — readings OK',
  '↪ Not a device issue — routed to care team',
  '🚑 EMS dispatched (911) — patient escalated',
];

function AlertRow({ alert, onAction, busy }) {
  const [expanded, setExpanded] = useState(false);
  const [assignee, setAssignee] = useState('');
  const [note, setNote] = useState('');
  const [resolveOpen, setResolveOpen] = useState(false);
  const [otherText, setOtherText] = useState('');
  const [showOther, setShowOther] = useState(false);
  // Patient context (the in-incident discovery) — lazily fetched on first expand,
  // so the triager sees device-vs-true BEFORE picking a resolution.
  const [snapshot, setSnapshot] = useState(undefined); // undefined → not fetched · 'loading' · null → none · {…}
  const toggleExpand = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && snapshot === undefined) {
      setSnapshot('loading');
      getPatientIncidentSnapshot(alert.patient_id).then(setSnapshot).catch(() => setSnapshot(null));
    }
  };
  return (
    <>
      <tr className="border-t border-slate-800 hover:bg-slate-900/40">
        <td className="p-2 align-middle">
          <button onClick={toggleExpand} className="text-slate-500 hover:text-slate-300" aria-label="Toggle patient context + audit trail">
            {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </td>
        <td className="p-2"><span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${SEV[alert.severity] || SEV.MEDIUM}`}>{alert.severity}</span></td>
        <td className="p-2 font-mono text-xs">
          {/* deep-link to the patient's Coach view — same pattern as the Population Risk roster */}
          <Link to={`/diabetes-coach?patient=${encodeURIComponent(alert.patient_id)}`} className="text-cyan-300 hover:text-cyan-200 hover:underline">{alert.patient_id}</Link>
          <span className="text-slate-600"> · </span><span className="text-slate-400">{alert.device_model}</span>
        </td>
        <td className="p-2 font-mono text-xs">{alert.alert_type === 'under-read'
          ? <span className="text-sky-300">↓ under-read</span>
          : <span className="text-rose-300">↑ over-read</span>}</td>
        <td className="p-2 font-mono text-xs text-slate-400">{alert.firmware || '—'}</td>
        <td className="p-2"><span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${STATUS[alert.status] || ''}`}>{alert.status}</span></td>
        <td className="p-2 font-mono text-xs text-slate-400">{alert.assigned_to || '—'}</td>
        <td className="p-2 text-right whitespace-nowrap">
          {alert.status === 'open' && (
            <button disabled={busy} onClick={() => onAction(alert.alert_id, 'ack')}
              title={'Acknowledge — "seen, being worked": claims the alert (status → acked) and writes an audit row. Next: assign a technician (expand the row).'}
              className="text-[11px] font-mono px-2.5 py-1 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 disabled:opacity-40 mr-1.5">Ack</button>
          )}
          {alert.status !== 'resolved' && (
            <span className="relative inline-block">
              <button disabled={busy} onClick={() => setResolveOpen(o => !o)}
                title="Resolve — pick the outcome (rollback / device swap / not-a-device-issue / EMS escalation). The choice lands in the audit trail — the recall's compliance record."
                className="text-[11px] font-mono px-2.5 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">Resolve ▾</button>
              {resolveOpen && (
                <div className="absolute right-0 top-full mt-1 z-20 min-w-[260px] bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden text-left">
                  {RESOLUTIONS.map(r => (
                    <button key={r} disabled={busy}
                      onClick={() => { setResolveOpen(false); setShowOther(false); onAction(alert.alert_id, 'resolve', r); }}
                      className="block w-full text-left px-3 py-2 text-[11px] font-mono text-slate-300 hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-40">
                      {r}
                    </button>
                  ))}
                  {/* Other… free-text outcome */}
                  {!showOther ? (
                    <button disabled={busy} onClick={() => setShowOther(true)}
                      className="block w-full text-left px-3 py-2 text-[11px] font-mono text-slate-400 hover:bg-emerald-500/10 hover:text-emerald-300 border-t border-slate-800 disabled:opacity-40">
                      ✏️ Other…
                    </button>
                  ) : (
                    <div className="flex items-center gap-1.5 p-2 border-t border-slate-800">
                      <input autoFocus value={otherText} onChange={e => setOtherText(e.target.value)} placeholder="describe the resolution…"
                        className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-300 placeholder:text-slate-600 flex-1" />
                      <button disabled={busy || !otherText.trim()}
                        onClick={() => { setResolveOpen(false); setShowOther(false); onAction(alert.alert_id, 'resolve', `✏️ ${otherText.trim()}`); setOtherText(''); }}
                        className="text-[11px] font-mono px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">OK</button>
                    </div>
                  )}
                </div>
              )}
            </span>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-t border-slate-800/50 bg-slate-900/30">
          <td colSpan={8} className="p-3 pl-10">
            {/* Patient context — the discovery that informs the resolution choice */}
            <div className="mb-2 text-[11px] font-mono">
              {snapshot === 'loading' && <span className="text-slate-600">loading patient context…</span>}
              {snapshot && snapshot !== 'loading' && (
                <span className="text-slate-400">
                  <span className="text-slate-300">Patient context</span> — at the fault's peak ({snapshot.time}): device showed{' '}
                  <span className={snapshot.direction === 'positive' ? 'text-rose-300' : 'text-sky-300'}>{snapshot.observed}</span> vs true{' '}
                  <span className="text-slate-200">{snapshot.trueGlucose}</span> mg/dL{' '}
                  ({snapshot.direction === 'positive' ? '↑ over-read by' : '↓ under-read by'} ~{Math.abs(snapshot.observed - snapshot.trueGlucose)}) ·{' '}
                  <Link to={`/diabetes-coach?patient=${encodeURIComponent(alert.patient_id)}`} className="text-cyan-400 hover:text-cyan-300">full picture in Coach →</Link>
                </span>
              )}
              {snapshot === null && <span className="text-slate-600">no in-incident readings recorded for this patient</span>}
            </div>
            <div className="flex items-start justify-between gap-4 flex-wrap">
              {/* audit trail — every action lands a row in alert_audit */}
              <ol className="text-[11px] font-mono text-slate-500 space-y-0.5">
                {(alert.audit || []).map((a, i) => (
                  <li key={i}>
                    <span className="text-slate-300">{a.action}</span>
                    {a.detail ? <span className="text-cyan-400"> → {a.detail}</span> : null}
                    <span className="text-slate-600"> · {a.actor} · {a.at}</span>
                  </li>
                ))}
                {!(alert.audit || []).length && <li className="text-slate-600">(no audit rows)</li>}
              </ol>
              <div className="flex flex-col gap-1.5 shrink-0">
                {alert.status !== 'resolved' && (
                  <div className="flex items-center gap-1.5">
                    <input value={assignee} onChange={e => setAssignee(e.target.value)} placeholder="assignee (e.g. tech-1)"
                      className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-300 placeholder:text-slate-600 w-52" />
                    <button disabled={busy || !assignee.trim()} onClick={() => { onAction(alert.alert_id, 'assign', assignee.trim()); setAssignee(''); }}
                      className="text-[11px] font-mono px-2.5 py-1 rounded border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-40">Assign</button>
                  </div>
                )}
                {/* addendum — audit-only note (no status change); allowed even after resolve */}
                <div className="flex items-center gap-1.5">
                  <input value={note} onChange={e => setNote(e.target.value)} placeholder="addendum (e.g. called patient — voicemail)"
                    className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-300 placeholder:text-slate-600 w-52" />
                  <button disabled={busy || !note.trim()} onClick={() => { onAction(alert.alert_id, 'note', note.trim()); setNote(''); }}
                    title="Append a free-text note to the audit trail — no status change"
                    className="text-[11px] font-mono px-2.5 py-1 rounded border border-slate-600 text-slate-300 hover:bg-slate-700/40 disabled:opacity-40">+ Note</button>
                </div>
                {/* follow-up request — engagement, not closure: a required fingerstick
                    verification keeps the alert in the queue (status → acked) until
                    the result comes back, then resolve with the real outcome. */}
                {alert.status !== 'resolved' && (
                  <button disabled={busy}
                    onClick={() => onAction(alert.alert_id, 'followup', '🩸 fingerstick verification requested — awaiting patient reading')}
                    title="Request a fingerstick verification from the patient — keeps the alert open (acked) until the reading comes back; then resolve with the outcome"
                    className="text-[11px] font-mono px-2.5 py-1 rounded border border-rose-400/40 text-rose-300 hover:bg-rose-500/10 disabled:opacity-40 self-start">🩸 Request fingerstick</button>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

// Scenario vantages — re-frame the same queue as a point in the incident story.
// 'last3h' swaps the queue for the live-risk watchlist (no incident labels —
// detection from readings alone, the production-realistic view).
const SCENARIOS = {
  week: { label: '📅 Full week (retrospective)', fault: null,
    prose: null },
  day2: { label: '🚨 Day 2 — during the 4.0 rollout', fault: 'over-read',
    prose: <>It's <span className="text-slate-300">Day 2, 14:00</span> — the fleet monitor just flagged <span className="text-rose-300">FW 4.0</span>: ~300 Alpha/Gamma devices reading <span className="text-rose-300">falsely HIGH</span> (over-read → false alarms). Work the queue.</> },
  day5: { label: '🚨 Day 5 — during the 4.0.3 hotfix fault', fault: 'under-read',
    prose: <>It's <span className="text-slate-300">Day 5, 10:00</span> — the hotfix <span className="text-sky-300">4.0.3</span> overcorrected: ~300 Beta/Delta devices reading <span className="text-sky-300">falsely LOW</span> (under-read → <span className="text-rose-300">masked real highs</span>). These are the dangerous ones.</> },
  last3h: { label: '⏱ Last 3h — live risk view', fault: null,
    prose: <>The <span className="text-slate-300">last 3 hours</span> of data, detected from the readings alone (<span className="font-mono">&lt;54 / &gt;250 mg/dL</span> — the High-Risk tile's bands). <span className="text-slate-300">No incident labels</span> — this is how a real fleet sees it; labels exist only because the demo simulates ground truth.</> },
};

export default function TriagePage() {
  const goBack = useGoBack();
  const configured = useLakebaseConfigured();
  const [searchParams] = useSearchParams();
  const [data, setData] = useState({ alerts: [], counts: {} });
  const [filter, setFilter] = useState('open');          // status — server-side
  // Deep-links carry their context: Population Risk passes ?model=, Firmware
  // passes ?fw=, anything can pass ?fault= / ?q=. (Alerts carry no region, so a
  // region-filtered roster lands unfiltered.)
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const [faultFilter, setFaultFilter] = useState(searchParams.get('fault') || 'all');
  const [modelFilter, setModelFilter] = useState(searchParams.get('model') || 'all');
  const [fwFilter, setFwFilter] = useState(searchParams.get('fw') || 'all');
  const [scenario, setScenario] = useState('week');
  const [watchlist, setWatchlist] = useState(null);       // last3h scenario rows
  const [sortBy, setSortBy] = useState('severity');       // severity | patient | updated
  const [allModels, setAllModels] = useState([]);         // registry SSOT — incl. clean controls
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async (f) => {
    try {
      setLoading(true); setError('');
      setData(await fetchAlerts(f));
    } catch (e) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (configured) load(filter); }, [configured, filter, load]);
  // Full model roster (incl. Epsilon/Zeta clean controls) — once, from the registry SSOT.
  useEffect(() => { if (configured) getAllDeviceModels().then(setAllModels).catch(() => {}); }, [configured]);
  // Scenario vantage: day presets force the matching fault filter; the last-3h
  // live view lazily fetches the watchlist (readings-only — no incident labels).
  useEffect(() => {
    const s = SCENARIOS[scenario];
    if (s?.fault) setFaultFilter(s.fault);
    if (scenario === 'week') setFaultFilter('all');
    if (scenario === 'last3h' && watchlist === null) {
      getLiveRiskWatchlist().then(setWatchlist).catch(() => setWatchlist([]));
    }
  }, [scenario]); // eslint-disable-line react-hooks/exhaustive-deps
  // If the fault filter strands the selected model (e.g. Alpha under under-read),
  // fall back to 'all' — the dropdown also greys those options out dynamically.
  useEffect(() => {
    if (modelFilter === 'all') return;
    const avail = new Set((data.alerts || [])
      .filter(a => faultFilter === 'all' || a.alert_type === faultFilter)
      .map(a => a.device_model));
    if (!avail.has(modelFilter)) setModelFilter('all');
  }, [faultFilter, data.alerts]); // eslint-disable-line react-hooks/exhaustive-deps

  const onAction = async (id, action, assignee = null) => {
    try { setBusy(true); await alertAction(id, action, assignee); await load(filter); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const onSeed = async () => {
    try { setBusy(true); setError(''); await seedAlerts(); await load(filter); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  // Bulk actions over the FILTERED set — the fleet move (e.g. filter FW 4.0 →
  // one "Firmware rolled back" resolves the whole cohort; audit row per alert).
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkOtherText, setBulkOtherText] = useState('');
  const [showBulkOther, setShowBulkOther] = useState(false);
  const onBulk = async (action, resolution = null) => {
    setBulkOpen(false); setShowBulkOther(false);
    try { setBusy(true); setError(''); await bulkAlerts(filtered.map(a => a.alert_id), action, resolution); await load(filter); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  // Booth demo reset — two-step confirm (arm → confirm) instead of a native dialog.
  const [resetArmed, setResetArmed] = useState(false);
  const onReset = async () => {
    if (!resetArmed) { setResetArmed(true); setTimeout(() => setResetArmed(false), 4000); return; }
    setResetArmed(false);
    try { setBusy(true); setError(''); await resetAlerts(); await load(filter); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const counts = data.counts || {};
  const total = Object.values(counts).reduce((s, n) => s + Number(n || 0), 0);
  // Live-readings view: rows are readings, not alerts — no fault direction, no
  // queue status, no severity. Queue-only controls grey out (search+model still apply).
  const isWatch = scenario === 'last3h';
  const NA_WATCH = 'n/a in the live readings view — these rows are readings (no fault/status/severity dimensions)';

  // Client-side refinement over the loaded queue (status is already server-filtered).
  const affectedModels = new Set((data.alerts || []).map(a => a.device_model).filter(Boolean));
  // Models with rows under the ACTIVE view — drives dynamic greying (e.g. Alpha is
  // over-read-only, so it disables while ↓ under-read is selected). In the last-3h
  // scenario availability comes from the watchlist instead: clean models legitimately
  // appear there (physiological hypo/hyper, not device faults).
  const availableForFault = scenario === 'last3h'
    ? new Set((watchlist || []).map(w => w.deviceModel))
    : new Set((data.alerts || [])
        .filter(a => faultFilter === 'all' || a.alert_type === faultFilter)
        .map(a => a.device_model));
  // Dropdown lists the FULL registry roster; clean (alert-free) models render disabled —
  // the control cohort visibly "has nothing to triage". Falls back to affected-only
  // until/unless the registry query resolves.
  const modelOptions = allModels.length ? allModels : [...affectedModels].sort();
  const q = search.trim().toLowerCase();
  const filtered = (data.alerts || []).filter(a =>
    (faultFilter === 'all' || a.alert_type === faultFilter) &&
    (modelFilter === 'all' || a.device_model === modelFilter) &&
    (fwFilter === 'all' || a.firmware === fwFilter) &&
    (!q || `${a.patient_id} ${a.device_id}`.toLowerCase().includes(q)));
  // Sort: severity = the server's triage order (open first, HIGH first). The other two
  // interleave the cohorts (an "all faults" view is otherwise a wall of HIGH/under-read).
  const sorted = sortBy === 'patient'
    ? [...filtered].sort((a, b) => a.patient_id.localeCompare(b.patient_id))
    : sortBy === 'updated'
      ? [...filtered].sort((a, b) => (b.updated_at || '').localeCompare(a.updated_at || ''))
      : filtered;
  const VISIBLE_CAP = 100; // keep the DOM light; filters narrow the rest
  const visible = sorted.slice(0, VISIBLE_CAP);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={goBack} className="text-slate-500 hover:text-slate-300" aria-label="Back">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <BrandMark className="w-7 h-7 text-cyan-400" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Alert Triage</h1>
              <p className="text-xs text-slate-500 font-mono">→ Act — work the live alert queue: acknowledge · assign · resolve</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8 space-y-6">
        {!configured ? (
          <section className="bg-slate-900/50 border border-dashed border-slate-700 rounded-lg p-8 text-center">
            <Database className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-sm text-slate-400">Alert Triage isn't enabled on this deploy target.</p>
            <p className="text-xs text-slate-500 font-mono mt-2">Enable by setting the <span className="text-slate-400">lakebase_project_id</span> bundle variable + re-rendering app.yaml (see DEPLOY.md).</p>
          </section>
        ) : (
          <>
            <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <span className="text-xs font-mono px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">→ ACT</span>
              <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Live alert queue — the recall, operationalized</h2>
              <p className="text-sm text-slate-400 leading-relaxed">
                Every affected patient-device from the calibration incident lands here as an alert.
                <span className="text-slate-200"> Acknowledge</span> it, <span className="text-slate-200">assign</span> a technician, <span className="text-slate-200">resolve</span> it —
                each action writes an <span className="text-slate-300">audit row</span> (expand a row to see its trail).
                Backed by <span className="text-cyan-300">Lakebase</span> (managed Postgres): the dashboards read the lakehouse; the queue is the app's <span className="text-slate-200">transactional write path</span>.
              </p>
              {/* Scenario framing — so a self-serve visitor knows WHAT they're triaging */}
              <p className="text-xs text-slate-500 leading-relaxed mt-2 font-mono">
                Scenario: firmware <span className="text-rose-300">4.0</span> shipped an <span className="text-rose-300">↑ over-read</span> fault (Day 2, Alpha/Gamma · false highs, <span className="text-amber-300">MEDIUM</span>),
                its hotfix <span className="text-sky-300">4.0.3</span> overcorrected into an <span className="text-sky-300">↓ under-read</span> (Day 5, Beta/Delta · masked real highs, <span className="text-rose-300">HIGH</span>) — ~600 devices total.
                Severity ranks the queue: masked highs first.
              </p>
              <Link to="/population-risk" className="inline-block mt-2 text-xs font-mono text-cyan-400 hover:text-cyan-300">
                ← See the clinical blast radius these alerts came from (Population Risk)
              </Link>
            </section>

            <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-end justify-between gap-4 flex-wrap mb-3">
                <div className="flex items-center gap-2 text-xs font-mono">
                  <BellRing className="w-4 h-4 text-cyan-400" />
                  <span className="text-rose-300">{counts.open || 0} open</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-amber-300">{counts.acked || 0} acked</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-emerald-300">{counts.resolved || 0} resolved</span>
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={onReset} disabled={busy || loading || isWatch}
                    title="Wipe statuses + audit and reseed all alerts as open — lets the next booth visitor triage from scratch"
                    className={`text-[11px] font-mono px-2.5 py-1 rounded-md border transition-colors disabled:opacity-40 ${resetArmed ? 'border-rose-500/60 text-rose-300 bg-rose-500/10' : 'border-slate-700 text-slate-500 hover:text-slate-300'}`}>
                    {resetArmed ? 'Confirm reset?' : '⟲ Reset demo'}
                  </button>
                  <button onClick={() => load(filter)} disabled={busy || loading} title="Reload the queue"
                    className="text-[11px] font-mono px-2.5 py-1 rounded-md border border-slate-700 text-slate-400 hover:text-slate-200 disabled:opacity-40">↻ Refresh</button>
                  <div className={`inline-flex rounded-md border border-slate-700 overflow-hidden text-[11px] font-mono ${isWatch ? 'opacity-40' : ''}`} role="group" aria-label="Status filter" title={isWatch ? NA_WATCH : undefined}>
                    {FILTERS.map(f => (
                      <button key={f} onClick={() => setFilter(f)} disabled={isWatch}
                        className={`px-2.5 py-1 transition-colors capitalize ${f !== FILTERS[0] ? 'border-l border-slate-700' : ''} ${filter === f ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>{f}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* refinement bar — client-side over the loaded queue */}
              <div className="flex items-center gap-2 flex-wrap mb-2 text-[11px] font-mono">
                <select value={scenario} onChange={e => setScenario(e.target.value)}
                  title="Re-frame the queue as a point in the incident story; 'last 3h' switches to the live readings-only risk view"
                  className="bg-slate-900 border border-cyan-500/40 rounded px-2 py-1 text-cyan-300">
                  {Object.entries(SCENARIOS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
                </select>
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="search patient / device…"
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300 placeholder:text-slate-600 w-52" />
                <div className={`inline-flex rounded-md border border-slate-700 overflow-hidden ${isWatch ? 'opacity-40' : ''}`} role="group" aria-label="Fault filter" title={isWatch ? NA_WATCH : undefined}>
                  {[['all', 'all faults'], ['over-read', '↑ over-read'], ['under-read', '↓ under-read']].map(([v, l], i) => (
                    <button key={v} onClick={() => setFaultFilter(v)} disabled={isWatch}
                      className={`px-2.5 py-1 transition-colors ${i ? 'border-l border-slate-700' : ''} ${faultFilter === v ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>{l}</button>
                  ))}
                </div>
                <select value={modelFilter} onChange={e => setModelFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300">
                  <option value="all">all models</option>
                  {modelOptions.map(m => availableForFault.has(m)
                    ? <option key={m} value={m}>{m}</option>
                    : <option key={m} value={m} disabled>{m}{affectedModels.has(m) ? ' — none for this fault' : ' — clean, no alerts'}</option>)}
                </select>
                <select value={sortBy} onChange={e => setSortBy(e.target.value)} disabled={isWatch}
                  title={isWatch ? NA_WATCH + ' — the watchlist ranks by danger-band reading count' : 'Severity = triage order (most critical first); the others interleave the cohorts'}
                  className={`bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300 ${isWatch ? 'opacity-40' : ''}`}>
                  <option value="severity">sort: severity</option>
                  <option value="patient">sort: patient id</option>
                  <option value="updated">sort: recently updated</option>
                </select>
                {fwFilter !== 'all' && (
                  <button onClick={() => setFwFilter('all')} title="Clear the firmware filter (set by the Firmware Lifecycle deep-link)"
                    className="px-2 py-0.5 rounded border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10">FW {fwFilter} ×</button>
                )}
                <span className="text-slate-500 ml-auto">{scenario === 'last3h' ? `${(watchlist || []).length} patients in the danger bands` : `${filtered.length} matching${filtered.length > VISIBLE_CAP ? ` · showing first ${VISIBLE_CAP} — refine to narrow` : ''}`}</span>
              </div>

              {SCENARIOS[scenario].prose && (
                <p className="text-xs text-slate-400 leading-relaxed font-mono mb-4 border-l-2 border-cyan-500/40 pl-3">{SCENARIOS[scenario].prose}</p>
              )}
              {/* why "masked highs first" — the severity ranking, honestly framed:
                  both directions are dangerous; the HIGH/MEDIUM split mirrors the
                  documented harm profile of the two real recalls. */}
              {scenario !== 'last3h' && (
                <p className="text-[11px] text-slate-500 leading-relaxed font-mono mb-4">
                  <span className="text-slate-300">Why "masked highs first"?</span> Both fault directions are dangerous in opposite ways: an <span className="text-rose-300">↑ over-read</span> hides real lows and cries wolf on highs (false alarms → over-treatment);
                  an <span className="text-sky-300">↓ under-read</span> hides real highs — hyperglycemia goes untreated (DKA risk). The queue ranks under-read <span className="text-rose-300">HIGH</span> because it mirrors the <span className="text-slate-300">2025 under-read recall</span>, the failure mode tied to documented deaths
                  (the 2024 over-read recall reported injuries, no deaths) — a recall-informed triage heuristic, not a clinical absolute. Switch sort to interleave the cohorts.
                </p>
              )}

              {/* Bulk actions over the FILTERED set — the fleet move */}
              {!isWatch && filtered.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap mb-4 text-[11px] font-mono">
                  <span className="text-slate-500">Bulk on the <span className="text-slate-300">{filtered.length}</span> matching:</span>
                  <button disabled={busy} onClick={() => onBulk('ack')}
                    title="Acknowledge every matching open alert (one audit row per alert)"
                    className="px-2.5 py-1 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 disabled:opacity-40">Ack all</button>
                  <span className="relative inline-block">
                    <button disabled={busy} onClick={() => setBulkOpen(o => !o)}
                      title="Resolve every matching unresolved alert with one outcome — e.g. filter to FW 4.0, pick 'Firmware rolled back', and the whole cohort closes (audit row per alert)"
                      className="px-2.5 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">Resolve all ▾</button>
                    {bulkOpen && (
                      <div className="absolute left-0 top-full mt-1 z-20 min-w-[260px] bg-slate-900 border border-slate-700 rounded-lg shadow-xl overflow-hidden text-left">
                        {RESOLUTIONS.map(r => (
                          <button key={r} disabled={busy} onClick={() => onBulk('resolve', r)}
                            className="block w-full text-left px-3 py-2 text-[11px] font-mono text-slate-300 hover:bg-emerald-500/10 hover:text-emerald-300 disabled:opacity-40">{r}</button>
                        ))}
                        {!showBulkOther ? (
                          <button disabled={busy} onClick={() => setShowBulkOther(true)}
                            className="block w-full text-left px-3 py-2 text-[11px] font-mono text-slate-400 hover:bg-emerald-500/10 hover:text-emerald-300 border-t border-slate-800 disabled:opacity-40">✏️ Other…</button>
                        ) : (
                          <div className="flex items-center gap-1.5 p-2 border-t border-slate-800">
                            <input autoFocus value={bulkOtherText} onChange={e => setBulkOtherText(e.target.value)} placeholder="describe the resolution…"
                              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-300 placeholder:text-slate-600 flex-1" />
                            <button disabled={busy || !bulkOtherText.trim()}
                              onClick={() => { onBulk('resolve', `✏️ ${bulkOtherText.trim()}`); setBulkOtherText(''); }}
                              className="text-[11px] font-mono px-2 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">OK</button>
                          </div>
                        )}
                      </div>
                    )}
                  </span>
                </div>
              )}

              {error && <p className="text-xs font-mono text-rose-300 mb-3">⚠ {error}</p>}

              {scenario === 'last3h' ? (
                /* Live risk watchlist — readings-only detection (no incident labels),
                   read-only: these aren't persisted alerts (creating alerts from live
                   signals is the monitoring layer's job — the queue's phase-2). */
                watchlist === null ? (
                  <div className="flex items-center justify-center h-40 text-slate-500">Scanning the last 3 hours of readings…</div>
                ) : (
                  <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
                    <thead>
                      <tr className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                        <th className="p-2">Patient</th>
                        <th className="p-2">Model</th>
                        <th className="p-2">FW</th>
                        <th className="p-2 text-right">Very-low readings (&lt;54)</th>
                        <th className="p-2 text-right">Very-high readings (&gt;250)</th>
                        <th className="p-2 text-right">Min · Max mg/dL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {watchlist
                        .filter(w => (modelFilter === 'all' || w.deviceModel === modelFilter) && (!q || w.patientId.toLowerCase().includes(q)))
                        .map(w => (
                          <tr key={w.patientId} className="border-t border-slate-800 hover:bg-slate-900/40">
                            <td className="p-2 font-mono text-xs"><Link to={`/diabetes-coach?patient=${encodeURIComponent(w.patientId)}`} className="text-cyan-300 hover:text-cyan-200 hover:underline">{w.patientId}</Link></td>
                            <td className="p-2 font-mono text-xs text-slate-400">{w.deviceModel}</td>
                            <td className="p-2 font-mono text-xs text-slate-400">{w.firmware}</td>
                            <td className="p-2 font-mono text-xs text-right text-sky-300">{w.veryLow || '—'}</td>
                            <td className="p-2 font-mono text-xs text-right text-rose-300">{w.veryHigh || '—'}</td>
                            <td className="p-2 font-mono text-xs text-right text-slate-400">{Math.round(w.minGlucose)} · {Math.round(w.maxGlucose)}</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )
              ) : loading ? (
                <div className="flex items-center justify-center h-40 text-slate-500">Loading alert queue…</div>
              ) : total === 0 ? (
                <div className="text-center py-10">
                  <p className="text-sm text-slate-400 mb-3">The queue is empty.</p>
                  <button disabled={busy} onClick={onSeed}
                    className="text-xs font-mono px-3 py-2 rounded-lg border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-40">
                    {busy ? 'Seeding…' : '⚡ Seed from the affected cohort'}
                  </button>
                  <p className="text-[11px] font-mono text-slate-600 mt-2">Inserts one open alert per affected patient-device from the gold layer (idempotent).</p>
                </div>
              ) : (
                <table className="w-full text-left" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
                      <th className="p-2 w-8"></th>
                      <th className="p-2">Sev</th>
                      <th className="p-2">Patient · Device</th>
                      <th className="p-2">Fault</th>
                      <th className="p-2">FW</th>
                      <th className="p-2">Status</th>
                      <th className="p-2">Assigned</th>
                      <th className="p-2 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map(a => <AlertRow key={a.alert_id} alert={a} onAction={onAction} busy={busy} />)}
                  </tbody>
                </table>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  );
}
