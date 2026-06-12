import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, BellRing, ChevronDown, ChevronRight, Database } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';
import { Link } from 'react-router-dom';
import { fetchAlerts, alertAction, seedAlerts, resetAlerts } from '../api/triage';
import { getAllDeviceModels } from '../api/databricksSQL';

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

function AlertRow({ alert, onAction, busy }) {
  const [expanded, setExpanded] = useState(false);
  const [assignee, setAssignee] = useState('');
  return (
    <>
      <tr className="border-t border-slate-800 hover:bg-slate-900/40">
        <td className="p-2 align-middle">
          <button onClick={() => setExpanded(e => !e)} className="text-slate-500 hover:text-slate-300" aria-label="Toggle audit trail">
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
              className="text-[11px] font-mono px-2.5 py-1 rounded border border-amber-500/40 text-amber-300 hover:bg-amber-500/10 disabled:opacity-40 mr-1.5">Ack</button>
          )}
          {alert.status !== 'resolved' && (
            <button disabled={busy} onClick={() => onAction(alert.alert_id, 'resolve')}
              className="text-[11px] font-mono px-2.5 py-1 rounded border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 disabled:opacity-40">Resolve</button>
          )}
        </td>
      </tr>
      {expanded && (
        <tr className="border-t border-slate-800/50 bg-slate-900/30">
          <td colSpan={8} className="p-3 pl-10">
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
              {alert.status !== 'resolved' && (
                <div className="flex items-center gap-1.5 shrink-0">
                  <input value={assignee} onChange={e => setAssignee(e.target.value)} placeholder="assignee (e.g. tech-1)"
                    className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-[11px] font-mono text-slate-300 placeholder:text-slate-600 w-40" />
                  <button disabled={busy || !assignee.trim()} onClick={() => { onAction(alert.alert_id, 'assign', assignee.trim()); setAssignee(''); }}
                    className="text-[11px] font-mono px-2.5 py-1 rounded border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-40">Assign</button>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function TriagePage() {
  const goBack = useGoBack();
  const configured = useLakebaseConfigured();
  const [data, setData] = useState({ alerts: [], counts: {} });
  const [filter, setFilter] = useState('open');          // status — server-side
  const [search, setSearch] = useState('');               // patient/device — client-side
  const [faultFilter, setFaultFilter] = useState('all');  // over/under — client-side
  const [modelFilter, setModelFilter] = useState('all');  // device model — client-side
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

  // Client-side refinement over the loaded queue (status is already server-filtered).
  const affectedModels = new Set((data.alerts || []).map(a => a.device_model).filter(Boolean));
  // Dropdown lists the FULL registry roster; clean (alert-free) models render disabled —
  // the control cohort visibly "has nothing to triage". Falls back to affected-only
  // until/unless the registry query resolves.
  const modelOptions = allModels.length ? allModels : [...affectedModels].sort();
  const q = search.trim().toLowerCase();
  const filtered = (data.alerts || []).filter(a =>
    (faultFilter === 'all' || a.alert_type === faultFilter) &&
    (modelFilter === 'all' || a.device_model === modelFilter) &&
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
                  <button onClick={onReset} disabled={busy || loading}
                    title="Wipe statuses + audit and reseed all alerts as open — lets the next booth visitor triage from scratch"
                    className={`text-[11px] font-mono px-2.5 py-1 rounded-md border transition-colors disabled:opacity-40 ${resetArmed ? 'border-rose-500/60 text-rose-300 bg-rose-500/10' : 'border-slate-700 text-slate-500 hover:text-slate-300'}`}>
                    {resetArmed ? 'Confirm reset?' : '⟲ Reset demo'}
                  </button>
                  <button onClick={() => load(filter)} disabled={busy || loading} title="Reload the queue"
                    className="text-[11px] font-mono px-2.5 py-1 rounded-md border border-slate-700 text-slate-400 hover:text-slate-200 disabled:opacity-40">↻ Refresh</button>
                  <div className="inline-flex rounded-md border border-slate-700 overflow-hidden text-[11px] font-mono" role="group" aria-label="Status filter">
                    {FILTERS.map(f => (
                      <button key={f} onClick={() => setFilter(f)}
                        className={`px-2.5 py-1 transition-colors capitalize ${f !== FILTERS[0] ? 'border-l border-slate-700' : ''} ${filter === f ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>{f}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* refinement bar — client-side over the loaded queue */}
              <div className="flex items-center gap-2 flex-wrap mb-4 text-[11px] font-mono">
                <input value={search} onChange={e => setSearch(e.target.value)} placeholder="search patient / device…"
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300 placeholder:text-slate-600 w-52" />
                <div className="inline-flex rounded-md border border-slate-700 overflow-hidden" role="group" aria-label="Fault filter">
                  {[['all', 'all faults'], ['over-read', '↑ over-read'], ['under-read', '↓ under-read']].map(([v, l], i) => (
                    <button key={v} onClick={() => setFaultFilter(v)}
                      className={`px-2.5 py-1 transition-colors ${i ? 'border-l border-slate-700' : ''} ${faultFilter === v ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>{l}</button>
                  ))}
                </div>
                <select value={modelFilter} onChange={e => setModelFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300">
                  <option value="all">all models</option>
                  {modelOptions.map(m => affectedModels.has(m)
                    ? <option key={m} value={m}>{m}</option>
                    : <option key={m} value={m} disabled>{m} — clean, no alerts</option>)}
                </select>
                <select value={sortBy} onChange={e => setSortBy(e.target.value)} title="Severity = triage order (most critical first); the others interleave the cohorts"
                  className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-slate-300">
                  <option value="severity">sort: severity</option>
                  <option value="patient">sort: patient id</option>
                  <option value="updated">sort: recently updated</option>
                </select>
                <span className="text-slate-500 ml-auto">{filtered.length} matching{filtered.length > VISIBLE_CAP ? ` · showing first ${VISIBLE_CAP} — refine to narrow` : ''}</span>
              </div>

              {error && <p className="text-xs font-mono text-rose-300 mb-3">⚠ {error}</p>}

              {loading ? (
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
