import React, { useState, useEffect, useCallback } from 'react';
import { ArrowLeft, BellRing, ChevronDown, ChevronRight, Database } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';
import { Link, useSearchParams } from 'react-router-dom';
import { fetchAlerts, alertAction, seedAlerts, resetAlerts, bulkAlerts, fetchRawRows } from '../api/triage';
import { getAllDeviceModels, getLiveRiskWatchlist, getPatientIncidentSnapshot } from '../api/databricksSQL';
import { getConfig } from '../api/config';

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
                  <span className="text-[10px] font-mono text-slate-600 ml-1">
                    writes land in Postgres instantly — if the trail above doesn't update, hit <span className="text-slate-400">↻ Refresh</span>
                  </span>
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
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState({ alerts: [], counts: {} });
  // THE PAGE REMEMBERS WHERE YOU WERE (per tab): the booth loop detours through
  // Coach / Device-Support and returns — landing on cold defaults every time read
  // as "my filters got reset" (booth 2026-06-12). View state persists to
  // sessionStorage; explicit URL params (deep-links) take precedence, and a
  // queue-targeting deep-link (?q/?fault/?model/?fw) overrides a remembered live
  // view (those links point at queue rows). Fresh tab = fresh defaults.
  const persisted = (() => {
    try { return JSON.parse(sessionStorage.getItem('triageView')) || {}; } catch { return {}; }
  })();
  const hasQueueParams = ['q', 'fault', 'model', 'fw'].some((k) => searchParams.get(k));
  const [filter, setFilter] = useState(persisted.filter || 'open');  // status tab — client-side (we fetch all statuses once)
  // Deep-links carry their context: Population Risk passes ?model=, Firmware
  // passes ?fw=, anything can pass ?fault= / ?q=. (Alerts carry no region, so a
  // region-filtered roster lands unfiltered.)
  const [search, setSearch] = useState(searchParams.get('q') || (hasQueueParams ? '' : persisted.search) || '');
  const [faultFilter, setFaultFilter] = useState(searchParams.get('fault') || (hasQueueParams ? 'all' : persisted.faultFilter) || 'all');
  const [modelFilter, setModelFilter] = useState(searchParams.get('model') || (hasQueueParams ? 'all' : persisted.modelFilter) || 'all');
  const [fwFilter, setFwFilter] = useState(searchParams.get('fw') || (hasQueueParams ? 'all' : persisted.fwFilter) || 'all');
  const [scenario, setScenario] = useState(hasQueueParams && persisted.scenario === 'last3h' ? 'week' : (persisted.scenario || 'week'));
  const [watchlist, setWatchlist] = useState(null);       // last3h scenario rows
  const [sortBy, setSortBy] = useState(persisted.sortBy || 'severity');  // severity | patient | updated
  // Persist on every view-state change (cheap; per-tab).
  useEffect(() => {
    try {
      sessionStorage.setItem('triageView', JSON.stringify({ scenario, filter, faultFilter, modelFilter, fwFilter, search, sortBy }));
    } catch { /* private mode — page just won't remember */ }
  }, [scenario, filter, faultFilter, modelFilter, fwFilter, search, sortBy]);
  const [allModels, setAllModels] = useState([]);         // registry SSOT — incl. clean controls
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // Fetch ALL statuses once (600-alert demo scale; server caps at 1000) so the
  // status tabs AND the header counts can both react client-side to the active
  // search/fault/model/fw filters — server-side status fetches made the header
  // counts static under filters (caught at the booth 2026-06-12).
  const load = useCallback(async () => {
    try {
      setLoading(true); setError('');
      setData(await fetchAlerts('all'));
    } catch (e) { setError(String(e.message || e)); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (configured) load(); }, [configured, load]);
  // Full model roster (incl. Epsilon/Zeta clean controls) — once, from the registry SSOT.
  useEffect(() => { if (configured) getAllDeviceModels().then(setAllModels).catch(() => {}); }, [configured]);
  // Scenario vantage: day presets force the matching fault filter; the last-3h
  // live view lazily fetches the watchlist (readings-only — no incident labels).
  const scenarioMounted = React.useRef(false);
  useEffect(() => {
    // Skip the mount run: scenario presets apply on CHANGE only — running on
    // mount would clobber the restored/deep-linked fault filter (the persisted
    // 'week' view would force fault back to 'all').
    if (!scenarioMounted.current) {
      scenarioMounted.current = true;
      if (scenario === 'last3h' && watchlist === null) {
        getLiveRiskWatchlist().then(setWatchlist).catch(() => setWatchlist([]));
      }
      return;
    }
    const s = SCENARIOS[scenario];
    if (s?.fault) setFaultFilter(s.fault);
    if (scenario === 'week') setFaultFilter('all');
    if (scenario === 'last3h' && watchlist === null) {
      getLiveRiskWatchlist().then(setWatchlist).catch(() => setWatchlist([]));
    }
  }, [scenario]); // eslint-disable-line react-hooks/exhaustive-deps
  // Patient deep-links (?q= from Coach / device-focus / watchlist ⚑) carry no
  // fault/model params — once the queue loads, snap those pills to the matched
  // alert's attributes (one-time; only when the pills are still at 'all'), so the
  // filter row reads coherently with the row it shows (booth catch 2026-06-12).
  const snappedRef = React.useRef(false);
  useEffect(() => {
    if (snappedRef.current || !data.alerts?.length) return;
    const q0 = (searchParams.get('q') || '').trim().toLowerCase();
    if (!q0 || searchParams.get('fault') || searchParams.get('model')) { snappedRef.current = true; return; }
    const hits = data.alerts.filter(a => `${a.patient_id} ${a.device_id}`.toLowerCase().includes(q0));
    const types = new Set(hits.map(a => a.alert_type));
    const models = new Set(hits.map(a => a.device_model));
    if (hits.length && types.size === 1 && faultFilter === 'all') setFaultFilter([...types][0]);
    if (hits.length && models.size === 1 && modelFilter === 'all') setModelFilter([...models][0]);
    snappedRef.current = true;
  }, [data.alerts]); // eslint-disable-line react-hooks/exhaustive-deps

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
    try { setBusy(true); await alertAction(id, action, assignee); await load(); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  const onSeed = async () => {
    try { setBusy(true); setError(''); await seedAlerts(); await load(); }
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
    try { setBusy(true); setError(''); await bulkAlerts(filtered.map(a => a.alert_id), action, resolution); await load(); }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  // Booth demo reset — two-step confirm (arm → confirm) instead of a native dialog.
  const [resetArmed, setResetArmed] = useState(false);

  // "Inspect the backing tables" — one-click verification that the queue is REAL
  // Postgres state: deep-link to the workspace's Lakebase editor + a sample query
  // (copy-paste) joining alerts to their audit trail. Workspace host from /api/config
  // (same mechanism as the About page's deep-link tiles).
  const [workspaceHost, setWorkspaceHost] = useState('');
  const [editorUrl, setEditorUrl] = useState('');
  useEffect(() => {
    getConfig().then((c) => {
      setWorkspaceHost(c.workspace_host || '');
      // Exact SQL-editor deep link (project+branch uids resolved server-side);
      // falls back to the generic /lakebase landing when unresolvable.
      setEditorUrl(c.lakebase_editor_url || (c.workspace_host ? `${c.workspace_host}/lakebase` : ''));
    }).catch(() => {});
  }, []);
  const SAMPLE_SQL = `-- your triage actions, as rows (newest first)
SELECT a.patient_id, a.status, a.assigned_to, u.action, u.actor, u.detail, u.at
FROM triage.alerts a JOIN triage.alert_audit u USING (alert_id)
ORDER BY u.at DESC LIMIT 20;`;
  const [sqlCopied, setSqlCopied] = useState(false);
  const [verifyOpen, setVerifyOpen] = useState(false);
  // In-page raw-rows peek: the same join the SQL-editor path runs, rendered under
  // the queue and refreshed with every queue load — click Ack, watch the row land.
  const [rawOpen, setRawOpen] = useState(false);
  // Breadcrumb for the watchlist→queue jump: the scenario flip (live → week) is
  // necessary (the queue only exists in queue views) but was SILENT — confusing
  // (booth 2026-06-12). The jump now leaves a visible banner with a one-click
  // return that restores the live view + its filters.
  // Persisted in sessionStorage: the booth loop often detours through Coach /
  // Device-Support and returns via their ⚑ buttons — a state-only breadcrumb
  // unmounted with the page and the return landed cold on the week default
  // (booth catch 2026-06-12). sessionStorage = per-tab, survives navigation.
  const [jumpCtx, setJumpCtxState] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('triageJumpCtx')) || null; } catch { return null; }
  }); // { patient, search, modelFilter }
  const setJumpCtx = (ctx) => {
    setJumpCtxState(ctx);
    try {
      if (ctx) sessionStorage.setItem('triageJumpCtx', JSON.stringify(ctx));
      else sessionStorage.removeItem('triageJumpCtx');
    } catch { /* private-mode etc. — banner just won't survive navigation */ }
  };
  const [raw, setRaw] = useState(null);
  useEffect(() => {
    if (rawOpen) fetchRawRows().then(setRaw).catch(() => setRaw({ error: true }));
  }, [rawOpen, data]); // refetch whenever the queue reloads (i.e. after every action)
  const copySampleSql = () => {
    navigator.clipboard?.writeText(SAMPLE_SQL).then(() => {
      setSqlCopied(true); setTimeout(() => setSqlCopied(false), 2000);
    }).catch(() => {});
  };
  const onReset = async () => {
    if (!resetArmed) { setResetArmed(true); setTimeout(() => setResetArmed(false), 4000); return; }
    setResetArmed(false);
    try {
      setBusy(true); setError(''); await resetAlerts();
      // "Reset demo" = fresh booth state: the DATA is truncated+reseeded, so the
      // VIEW resets too — sticky filters would otherwise keep narrowing the fresh
      // 600 to the previous visitor's slice (booth catch 2026-06-12).
      setSearch(''); setFaultFilter('all'); setModelFilter('all'); setFwFilter('all');
      setSortBy('severity'); setFilter('open'); setScenario('week'); setJumpCtx(null);
      setSearchParams({}, { replace: true });  // strip ?q= etc. so a refresh can't resurrect them
      await load();
    }
    catch (e) { setError(String(e.message || e)); }
    finally { setBusy(false); }
  };

  // (data.counts — the server's whole-DB totals — is superseded by the dynamic
  // per-filter counts computed below from the refined set.)
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
  // Watch view rows under the active model/search filters — one definition feeds
  // BOTH the table and the "N patients in the danger bands" label, so the label
  // reacts to filters (it sat frozen at the full fetch count before, 2026-06-12).
  const watchFiltered = (watchlist || []).filter(w =>
    (modelFilter === 'all' || w.deviceModel === modelFilter) &&
    (!q || w.patientId.toLowerCase().includes(q)));
  // Bridge stat between the two views: how many of the live danger-band patients
  // ALSO sit in the alert queue with an open device alert — separates physiological
  // risk from device-fault fallout at a glance (replaces a dead "n/a" label).
  const watchIds = new Set(watchFiltered.map(w => w.patientId));
  const alertPatients = new Set((data.alerts || [])
    .filter(a => a.status === 'open' && watchIds.has(a.patient_id))
    .map(a => a.patient_id));
  const watchAlertOverlap = alertPatients.size;
  // refined = every filter EXCEPT the status tab → the header counts break this
  // set down by status, so they update live as filters narrow the queue.
  const refined = (data.alerts || []).filter(a =>
    (faultFilter === 'all' || a.alert_type === faultFilter) &&
    (modelFilter === 'all' || a.device_model === modelFilter) &&
    (fwFilter === 'all' || a.firmware === fwFilter) &&
    (!q || `${a.patient_id} ${a.device_id}`.toLowerCase().includes(q)));
  const counts = { open: 0, acked: 0, resolved: 0 };
  refined.forEach(a => { counts[a.status] = (counts[a.status] || 0) + 1; });
  const total = refined.length;
  const filtered = filter === 'all' ? refined : refined.filter(a => a.status === filter);
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
              {/* Two-column on wide screens (booth monitors): lead prose left,
                  scenario/honesty callouts right — fills the card instead of
                  leaving a dead right half. Stacks on narrow viewports. */}
              <div className="grid lg:grid-cols-2 gap-x-10 gap-y-4 items-start">
                <div>
                  <p className="text-sm text-slate-400 leading-7">
                    Every affected patient-device from the calibration incident lands here as an alert.
                    <span className="text-slate-200"> Acknowledge</span> it, <span className="text-slate-200">assign</span> a technician, <span className="text-slate-200">resolve</span> it —
                    each action writes an <span className="text-slate-300">audit row</span> (expand a row to see its trail).
                    Backed by <span className="text-cyan-300">Lakebase</span> (managed Postgres): the dashboards read the lakehouse; the queue is the app's <span className="text-slate-200">transactional write path</span>.
                  </p>
                  <Link to="/population-risk" className="inline-block mt-3 text-xs font-mono text-cyan-400 hover:text-cyan-300">
                    ← See the clinical blast radius these alerts came from (Population Risk)
                  </Link>
                </div>
                <div>
                  {/* Scenario framing — so a self-serve visitor knows WHAT they're triaging */}
                  <div className="border-l-2 border-slate-700 pl-3 py-1">
                    <p className="text-xs text-slate-500 leading-6 font-mono">
                      <span className="text-slate-400 font-semibold">Scenario</span> · firmware <span className="text-rose-300">4.0</span> shipped an <span className="text-rose-300">↑ over-read</span> fault
                      (Day 2, Alpha/Gamma · false highs, <span className="text-amber-300">MEDIUM</span>);
                      its hotfix <span className="text-sky-300">4.0.3</span> overcorrected into an <span className="text-sky-300">↓ under-read</span>
                      (Day 5, Beta/Delta · masked real highs, <span className="text-rose-300">HIGH</span>) — ~600 devices total.
                      Severity ranks the queue: masked highs first.
                    </p>
                  </div>
                  {/* honesty note: "Live Alert" is the workflow's name, not a latency claim */}
                  <div className="mt-3 border-l-2 border-amber-500/30 pl-3 py-1">
                    <p className="text-[11px] font-mono text-slate-500 leading-6">
                      <span className="text-amber-300/80 font-semibold">Honest note</span> · alerts here are <span className="text-slate-400">batch-derived</span> from the current dataset — not yet streaming.
                      With live ingestion (see <Link to="/full-loop" className="text-cyan-400 hover:text-cyan-300">what's next</Link>) the same queue raises them in real time.
                    </p>
                  </div>
                </div>
              </div>
            </section>

            <section data-tour="triage-queue" className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-end justify-between gap-4 flex-wrap mb-3">
                <div className="flex items-center gap-2 text-xs font-mono">
                  <BellRing className="w-4 h-4 text-cyan-400" />
                  {isWatch ? (
                    // Queue counts are an ALERTS concept — readings rows have no status, so
                    // per-status counts would contradict the table (booth catch 2026-06-12).
                    // Show the BRIDGE stat instead: danger-band patients ∩ open device alerts —
                    // physiological risk vs device-fault fallout at a glance.
                    <span className="text-slate-400"
                      title="Overlap between the danger-band patients below and open device alerts in the queue — a high overlap says the clinical risk is device-fault fallout, not physiology.">
                      <span className="text-rose-300 font-semibold">{watchAlertOverlap}</span> of these {watchFiltered.length} patients also have open device alerts in the queue
                    </span>
                  ) : (<>
                  <span className="text-rose-300">{counts.open || 0} open</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-amber-300">{counts.acked || 0} acked</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-emerald-300">{counts.resolved || 0} resolved</span>
                  </>)}
                </div>
                <div className="flex items-center gap-2">
                  <button onClick={onReset} disabled={busy || loading || isWatch}
                    title="Clears the Postgres tables too: TRUNCATE triage.alerts + triage.alert_audit, then reseeds 600 open alerts from the gold layer — your acks/notes are gone from the database (verify via 🛢). Lets the next booth visitor triage from scratch."
                    className={`text-[11px] font-mono px-2.5 py-1 rounded-md border transition-colors disabled:opacity-40 ${resetArmed ? 'border-rose-500/60 text-rose-300 bg-rose-500/10' : 'border-slate-700 text-slate-500 hover:text-slate-300'}`}>
                    {resetArmed ? 'Confirm reset?' : '⟲ Reset demo'}
                  </button>
                  {workspaceHost && (
                    <div className="relative">
                      <button onClick={() => setVerifyOpen(v => !v)}
                        title="Prove the queue is real Postgres state — see your own actions as rows"
                        className={`text-[11px] font-mono px-2.5 py-1 rounded-md border ${verifyOpen ? 'border-cyan-500/60 text-cyan-200 bg-cyan-500/10' : 'border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10'}`}>
                        🛢 Verify in Postgres ▾
                      </button>
                      {verifyOpen && (
                        <div className="absolute right-0 mt-1 w-72 z-30 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl p-3 text-left">
                          <p className="text-[11px] text-slate-400 mb-2">Every Ack / Assign / Note you click is a Postgres row. See for yourself:</p>
                          <button onClick={copySampleSql}
                            className="w-full text-left text-[11px] font-mono px-2.5 py-1.5 rounded-md border border-slate-700 text-slate-200 hover:bg-slate-800 mb-1.5">
                            {sqlCopied ? '✓ query copied' : '1 · Copy the query'}
                          </button>
                          <a href={editorUrl} target="_blank" rel="noreferrer"
                            className="block text-[11px] font-mono px-2.5 py-1.5 rounded-md border border-slate-700 text-slate-200 hover:bg-slate-800">
                            2 · Open the Lakebase SQL editor ↗
                          </a>
                          <p className="text-[10px] text-slate-500 mt-2 leading-snug">Lands directly in this project's SQL editor — paste → Run.</p>
                          <button onClick={() => { setRawOpen(v => !v); setVerifyOpen(false); }}
                            className="w-full text-left text-[11px] font-mono px-2.5 py-1.5 rounded-md border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 mt-2">
                            {rawOpen ? 'Hide the in-page peek' : 'or · Peek right here ↓'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                  <button onClick={() => load(filter)} disabled={busy || loading}
                    title="Re-queries Postgres and redraws the queue — changes nothing in the database (use it to pick up actions made elsewhere, e.g. another visitor's tab)."
                    className="text-[11px] font-mono px-2.5 py-1 rounded-md border border-slate-700 text-slate-400 hover:text-slate-200 disabled:opacity-40">↻ Refresh</button>
                  <div className={`inline-flex rounded-md border border-slate-700 overflow-hidden text-[11px] font-mono ${isWatch ? 'opacity-40' : ''}`} role="group" aria-label="Status filter" title={isWatch ? NA_WATCH : undefined}>
                    {FILTERS.map(f => (
                      <button key={f} onClick={() => setFilter(f)} disabled={isWatch}
                        title={f === 'all' ? 'All statuses — the search/fault/model filters below still apply' : undefined}
                        className={`px-2.5 py-1 transition-colors capitalize ${f !== FILTERS[0] ? 'border-l border-slate-700' : ''} ${filter === f ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>{f === 'all' ? 'All statuses' : f}</button>
                    ))}
                  </div>
                </div>
              </div>

              {/* refinement bar — client-side over the loaded queue */}
              <div className="flex items-center gap-2 flex-wrap mb-2 text-[11px] font-mono">
                <select value={scenario} onChange={e => { setScenario(e.target.value); setJumpCtx(null); }}
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
                <span className="text-slate-500 ml-auto">
                  {scenario === 'last3h' ? `${watchFiltered.length} patient${watchFiltered.length === 1 ? '' : 's'} in the danger bands` : `${filtered.length} matching${filtered.length > VISIBLE_CAP ? ` · showing first ${VISIBLE_CAP} — refine to narrow` : ''}`}
                  {(q || faultFilter !== 'all' || modelFilter !== 'all' || fwFilter !== 'all') && (
                    <button onClick={() => { setSearch(''); setFaultFilter('all'); setModelFilter('all'); setFwFilter('all'); setJumpCtx(null); }}
                      title="Clear the search / fault / model / firmware filters (status tab + scenario stay)"
                      className="ml-2 text-cyan-400 hover:text-cyan-300 underline decoration-dotted">✕ clear filters</button>
                  )}
                </span>
              </div>

              {jumpCtx && scenario === 'week' && (
                <div className="flex items-center gap-3 text-xs font-mono mb-4 border border-amber-500/30 bg-amber-500/5 rounded-lg px-3 py-2">
                  <span className="text-amber-300">⚑</span>
                  <span className="text-slate-300">
                    Jumped from the <span className="text-amber-300">live last-3h view</span> to{' '}
                    <span className="text-cyan-300">{jumpCtx.patient}</span>'s device alert — the queue lives in the retrospective views.
                  </span>
                  <button onClick={() => { setScenario('last3h'); setSearch(jumpCtx.search); setModelFilter(jumpCtx.modelFilter); setJumpCtx(null); }}
                    className="ml-auto shrink-0 px-2.5 py-1 rounded-md border border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                    ⏱ Back to live view
                  </button>
                </div>
              )}
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
                        <th className="p-2 text-right">Queue</th>
                      </tr>
                    </thead>
                    <tbody>
                      {watchFiltered
                        .map(w => (
                          <tr key={w.patientId} className="border-t border-slate-800 hover:bg-slate-900/40">
                            <td className="p-2 font-mono text-xs"><Link to={`/diabetes-coach?patient=${encodeURIComponent(w.patientId)}`} className="text-cyan-300 hover:text-cyan-200 hover:underline">{w.patientId}</Link></td>
                            <td className="p-2 font-mono text-xs text-slate-400">{w.deviceModel}</td>
                            <td className="p-2 font-mono text-xs text-slate-400">{w.firmware}</td>
                            <td className="p-2 font-mono text-xs text-right text-sky-300">{w.veryLow || '—'}</td>
                            <td className="p-2 font-mono text-xs text-right text-rose-300">{w.veryHigh || '—'}</td>
                            <td className="p-2 font-mono text-xs text-right text-slate-400">{Math.round(w.minGlucose)} · {Math.round(w.maxGlucose)}</td>
                            <td className="p-2 font-mono text-xs text-right">
                              {alertPatients.has(w.patientId) ? (
                                <button onClick={() => { setJumpCtx({ patient: w.patientId, search, modelFilter }); setScenario('week'); setFilter('open'); setSearch(w.patientId); }}
                                  title="This patient also has an open device alert — open it in the queue (full-week view, searched to this patient)."
                                  className="text-rose-300 hover:text-rose-200 hover:underline">⚑ open alert</button>
                              ) : <span className="text-slate-600" title="No open device alert — the danger-band readings look physiological, not device-fault fallout.">—</span>}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                )
              ) : loading ? (
                <div className="flex items-center justify-center h-40 text-slate-500">Loading alert queue…</div>
              ) : (data.alerts || []).length === 0 ? (
                <div className="text-center py-10">
                  <p className="text-sm text-slate-400 mb-3">The queue is empty.</p>
                  <button disabled={busy} onClick={onSeed}
                    className="text-xs font-mono px-3 py-2 rounded-lg border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 disabled:opacity-40">
                    {busy ? 'Seeding…' : '⚡ Seed from the affected cohort'}
                  </button>
                  <p className="text-[11px] font-mono text-slate-600 mt-2">Inserts one open alert per affected patient-device from the gold layer (idempotent).</p>
                </div>
              ) : filtered.length === 0 ? (
                <div className="text-center py-10">
                  <p className="text-sm text-slate-400 mb-3">No alerts match the current filters.</p>
                  <button onClick={() => { setSearch(''); setFaultFilter('all'); setModelFilter('all'); setFwFilter('all'); setFilter('all'); }}
                    className="text-xs font-mono px-3 py-2 rounded-lg border border-slate-600 text-slate-300 hover:bg-slate-800">
                    Clear filters
                  </button>
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

            {/* In-page Postgres peek — the exact join the SQL editor would run, live.
                Refetches on every queue reload, so an Ack above lands here instantly. */}
            {rawOpen && (
              <section className="bg-slate-900/50 border border-cyan-500/30 rounded-lg p-6 mt-6">
                <div className="flex items-center justify-between mb-2">
                  <h3 className="text-sm font-semibold text-cyan-300 font-mono">🛢 Raw Postgres rows — live</h3>
                  <button onClick={() => setRawOpen(false)} className="text-xs text-slate-500 hover:text-slate-300">✕ hide</button>
                </div>
                <p className="text-[11px] text-slate-500 font-mono mb-3">
                  Straight from Lakebase (<span className="text-slate-400">triage.alerts ⋈ triage.alert_audit</span>, newest first) —
                  act on an alert above and the row appears here on the next refresh. Same query, same result, in the
                  workspace SQL editor via <span className="text-cyan-400">🛢 Verify in Postgres</span>.
                </p>
                {raw?.sql && (
                  <pre className="text-[10px] font-mono text-slate-500 bg-slate-950 border border-slate-800 rounded p-2 mb-3 overflow-x-auto">{raw.sql}</pre>
                )}
                {raw?.error ? (
                  <p className="text-xs text-rose-300 font-mono">couldn't fetch rows — try ↻ Refresh</p>
                ) : !raw ? (
                  <p className="text-xs text-slate-500 font-mono">loading…</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[11px] font-mono">
                      <thead>
                        <tr className="text-[10px] text-slate-500 uppercase tracking-wider">
                          {['patient_id', 'status', 'assigned_to', 'action', 'actor', 'detail', 'at'].map(c => <th key={c} className="p-1.5 pr-4">{c}</th>)}
                        </tr>
                      </thead>
                      <tbody>
                        {(raw.rows || []).map((r, i) => (
                          <tr key={i} className="border-t border-slate-800 text-slate-300">
                            <td className="p-1.5 pr-4 text-cyan-300">{r.patient_id}</td>
                            <td className="p-1.5 pr-4">{r.status}</td>
                            <td className="p-1.5 pr-4">{r.assigned_to || '—'}</td>
                            <td className="p-1.5 pr-4 text-amber-300">{r.action}</td>
                            <td className="p-1.5 pr-4 text-slate-400">{r.actor}</td>
                            <td className="p-1.5 pr-4 text-slate-400 max-w-[16rem] truncate" title={r.detail || ''}>{r.detail || '—'}</td>
                            <td className="p-1.5 text-slate-500">{r.at}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
