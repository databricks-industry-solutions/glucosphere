import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import PopulationRiskChart from '../components/PopulationRiskChart';
import { GlucoseAbsoluteChart } from '../components/IncidentCharts';
import { useGoBack } from '../hooks/useGoBack';
import { getPopulationRisk, getCohortAffected, getCohortAffectedBreakdown } from '../api/databricksSQL';

// Stacked split bar: affected patients per label, segmented by DEVICE-bias direction —
// over-read (amber) vs under-read (slate-grey). Deliberately NOT the clinical rose/blue
// (hyper/hypo) palette, so the device fault isn't visually conflated with glucose state.
// `max` normalizes bar width across rows. Clicking a row filters
// the roster below (dim = 'region' | 'model'); the active row is highlighted.
function SplitBars({ title, dim, rows, max, activeLabel, onSelect }) {
  return (
    <div>
      <p className="text-sm font-mono text-slate-300 mb-3">{title}</p>
      <div className="space-y-2.5">
        {rows.map((r) => {
          const active = activeLabel === r.label;
          return (
            <button
              key={r.label}
              onClick={() => onSelect(dim, r.label)}
              className={`w-full flex items-center gap-3 rounded px-1 py-1 transition-colors ${active ? 'bg-cyan-500/10 ring-1 ring-cyan-500/40' : 'hover:bg-slate-800/50'}`}
              title={`Filter roster to ${r.label}`}
            >
              <span className={`w-20 text-sm font-mono shrink-0 text-right ${active ? 'text-cyan-300' : 'text-slate-300'}`}>{r.label}</span>
              <div className="flex-1 flex h-5 rounded overflow-hidden bg-slate-950">
                <div className="bg-amber-500/80 h-full" style={{ width: `${(r.positive / max) * 100}%` }} title={`${r.positive} over-read`} />
                <div className="bg-slate-400/80 h-full" style={{ width: `${(r.negative / max) * 100}%` }} title={`${r.negative} under-read`} />
              </div>
              <span className="w-24 text-xs font-mono text-slate-500 shrink-0 text-left">
                <span className="text-amber-300">{r.positive}</span> · <span className="text-slate-300">{r.negative}</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ③ Assess — which patient cohorts a device fault pushed into hypo/hyper exposure.
export default function PopulationRiskPage() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [roster, setRoster] = useState([]);
  const [rosterLoading, setRosterLoading] = useState(true);
  const [rosterLimit, setRosterLimit] = useState(40); // 40 | 100 | 250 | null(all) — severity-ranked
  const [breakdown, setBreakdown] = useState({ byRegion: [], byModel: [] });

  useEffect(() => {
    (async () => {
      try { setLoading(true); setData(await getPopulationRisk()); }
      catch (e) { console.error('Population risk fetch failed:', e); setData([]); }
      finally { setLoading(false); }
    })();
    (async () => {
      try { setBreakdown(await getCohortAffectedBreakdown()); }
      catch (e) { console.error('Cohort breakdown fetch failed:', e); }
    })();
  }, []);

  // Roster re-fetches whenever the size selector changes (severity-ranked;
  // rosterLimit null = "All" → no LIMIT). The breakdown/summary above stays full-cohort.
  useEffect(() => {
    (async () => {
      try { setRosterLoading(true); setRoster(await getCohortAffected(rosterLimit)); }
      catch (e) { console.error('Cohort roster fetch failed:', e); setRoster([]); }
      finally { setRosterLoading(false); }
    })();
  }, [rosterLimit]);

  // Normalize bar widths within each group by its largest total.
  const regionMax = Math.max(1, ...breakdown.byRegion.map((r) => r.total));
  const modelMax = Math.max(1, ...breakdown.byModel.map((r) => r.total));

  // Roster sort + summary→table cross-filter.
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [filter, setFilter] = useState(null); // {dim:'region'|'model', label}
  const [outreachOpen, setOutreachOpen] = useState(false);
  const [channel, setChannel] = useState('portal');

  const toggleSort = (col) => {
    if (sortCol === col) { setSortDir((d) => (d === 'asc' ? 'desc' : 'asc')); }
    else { setSortCol(col); setSortDir(col === 'pctHypo' || col === 'pctHyper' ? 'desc' : 'asc'); }
  };
  const selectFilter = (dim, label) => setFilter((f) => (f && f.dim === dim && f.label === label ? null : { dim, label }));

  const displayedRoster = (() => {
    let rows = roster;
    if (filter) rows = rows.filter((r) => (filter.dim === 'region' ? r.region === filter.label : r.deviceModel === filter.label));
    if (sortCol) {
      const num = sortCol === 'pctHypo' || sortCol === 'pctHyper';
      rows = [...rows].sort((a, b) => {
        const cmp = num ? (a[sortCol] - b[sortCol]) : String(a[sortCol]).localeCompare(String(b[sortCol]));
        return sortDir === 'asc' ? cmp : -cmp;
      });
    }
    return rows;
  })();
  const sortIcon = (col) => (sortCol === col ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '');

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
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Population Risk</h1>
              <p className="text-xs text-slate-500 font-mono">③ Assess — the clinical blast radius</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30">③ ASSESS</span>
          <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Hypo / hyper exposure by cohort</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The clinical question: <span className="text-slate-200">who got pushed into danger</span>. Share of device-reported readings in the
            <span className="text-blue-300"> hypoglycemic (&lt;70 mg/dL)</span> and <span className="text-rose-300">hyperglycemic (&gt;180 mg/dL)</span> ranges,
            per cohort. The over-reading cohort is driven into apparent <span className="text-rose-300">highs</span>, the under-reading cohort into apparent
            <span className="text-blue-300"> lows</span> — both vs the unaffected <span className="text-slate-200">baseline</span>. That gap is the blast radius.
          </p>
          <p className="text-xs font-mono text-slate-500 mt-3">
            Clinical view — the roster below is for <span className="text-slate-300">care-team outreach</span>. For device-side fleet operations (heatmap, live readings, per-device diagnostics), see{' '}
            <button onClick={() => navigate('/device-support')} className="text-cyan-400 hover:text-cyan-300">Device Support →</button>.
          </p>
        </section>

        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          {loading
            ? <div className="flex items-center justify-center h-64 text-slate-500">Loading population risk…</div>
            : <div className="max-w-4xl mx-auto"><PopulationRiskChart data={data} /></div>}
        </section>

        {/* The full per-cohort actual-vs-device timeline lives on the landing (detect view) —
            link out rather than duplicate it cramped here. */}
        <p className="text-xs font-mono text-slate-500">
          See how the bias unfolds over time on the{' '}
          <button onClick={() => navigate('/')} className="text-cyan-400 hover:text-cyan-300">per-cohort glucose timeline (landing) →</button>
        </p>

        {/* Affected-patient summary — by region + device model, each split by error
            direction (over-read vs under-read) over the full affected population. */}
        {(breakdown.byRegion.length > 0 || breakdown.byModel.length > 0) && (
          <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <h2 className="text-lg font-semibold text-slate-200 mb-1" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Affected-patient summary</h2>
            <p className="text-xs font-mono text-slate-500 mb-4">
              Distinct affected patients across all incident cohorts, by region and device model. Split by{' '}
              <span className="text-amber-300">device over-read</span> · <span className="text-slate-300">device under-read</span> —
              the <span className="text-slate-300">fault direction</span> (not the patient's glucose; an under-read device can still serve a hyper patient).
            </p>
            <div className="grid md:grid-cols-2 gap-8">
              <SplitBars title="By region" dim="region" rows={breakdown.byRegion} max={regionMax} activeLabel={filter?.dim === 'region' ? filter.label : null} onSelect={selectFilter} />
              <SplitBars title="By device model" dim="model" rows={breakdown.byModel} max={modelMax} activeLabel={filter?.dim === 'model' ? filter.label : null} onSelect={selectFilter} />
            </div>
            <p className="text-[11px] font-mono text-slate-600 mt-3">
              Click a bar to filter the roster below. &nbsp;·&nbsp; Regions:{' '}
              <span className="text-slate-400">NA</span> North America &nbsp;·&nbsp;
              <span className="text-slate-400">EMEA</span> Europe, Middle East &amp; Africa &nbsp;·&nbsp;
              <span className="text-slate-400">APAC</span> Asia-Pacific
            </p>
          </section>
        )}

        {/* Affected patients & devices — the act handoff */}
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <div className="flex items-start justify-between mb-4 gap-4 flex-wrap">
            <div>
              <h2 className="text-lg font-semibold text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Affected patients &amp; devices</h2>
              <p className="text-xs text-slate-500 font-mono mt-1">The outreach / recall roster — worst exposure first. <span className="text-cyan-400">Click a row to open the patient →</span> Identifiers simulated (no real PHI).</p>
              <p className="text-[11px] text-slate-600 font-mono mt-1">%hypo/%hyper span each patient's full observed window (~7 days) — same basis as the Coach.</p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button onClick={() => setOutreachOpen(true)} className="text-xs font-mono px-3 py-2 rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 transition-colors">
                ✉ Draft patient outreach
              </button>
              <button onClick={() => navigate('/roadmap')} className="text-xs font-mono px-3 py-2 rounded-lg border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 transition-colors">
                → Send to triage queue <span className="text-slate-500">(Live Alert · wip)</span>
              </button>
            </div>
          </div>
          <div className="mb-3 flex items-center gap-2 text-xs font-mono flex-wrap">
            {filter && (
              <>
                <span className="text-slate-500">Filtered to</span>
                <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300">{filter.dim}: {filter.label}</span>
                <button onClick={() => setFilter(null)} className="text-slate-500 hover:text-slate-300">clear ✕</button>
              </>
            )}
            <div className="ml-auto flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-slate-500">
                Show
                <select
                  value={rosterLimit === null ? 'all' : String(rosterLimit)}
                  onChange={(e) => setRosterLimit(e.target.value === 'all' ? null : Number(e.target.value))}
                  title="Roster size — severity-ranked (worst exposure first)"
                  className="bg-slate-800 border border-slate-700 rounded px-1.5 py-0.5 text-slate-300 font-mono focus:outline-none focus:border-cyan-500/50"
                >
                  <option value="40">Top 40</option>
                  <option value="100">Top 100</option>
                  <option value="250">Top 250</option>
                  <option value="all">All</option>
                </select>
              </label>
              <span className="text-slate-600">{displayedRoster.length} of {roster.length} shown</span>
            </div>
          </div>
          {rosterLoading ? (
            <div className="flex items-center justify-center h-32 text-slate-500">Loading roster…</div>
          ) : roster.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-slate-500">No affected devices</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] font-mono text-slate-500 border-b border-slate-800">
                    {[
                      { k: 'patientId', label: 'Patient', align: '' },
                      { k: 'deviceId', label: 'Device', align: '' },
                      { k: 'deviceModel', label: 'Model', align: '' },
                      { k: 'region', label: 'Region', align: '' },
                      { k: 'pctHypo', label: '% hypo', align: 'text-right' },
                      { k: 'pctHyper', label: '% hyper', align: 'text-right' },
                    ].map((c, ci) => (
                      <th key={c.k} className={`py-2 ${ci < 5 ? 'pr-3' : ''} font-normal ${c.align}`}>
                        <button onClick={() => toggleSort(c.k)} className="hover:text-slate-300 transition-colors">{c.label}{sortIcon(c.k)}</button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="font-mono text-slate-300">
                  {displayedRoster.map((r, i) => (
                    <tr
                      key={i}
                      onClick={() => navigate(`/diabetes-coach?patient=${encodeURIComponent(r.patientId)}`)}
                      className="border-b border-slate-800/50 hover:bg-slate-800/40 cursor-pointer"
                      title="Open this patient in the Diabetes Coach view"
                    >
                      <td className="py-2 pr-3 text-cyan-300 hover:text-cyan-200">{r.patientId}</td>
                      <td className="py-2 pr-3">{r.deviceId}</td>
                      <td className="py-2 pr-3 text-slate-400">{r.deviceModel}</td>
                      <td className="py-2 pr-3 text-slate-400">{r.region}</td>
                      <td className="py-2 pr-3 text-right text-blue-300">{r.pctHypo}</td>
                      <td className="py-2 text-right text-rose-300">{r.pctHyper}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </main>

      {/* Patient-outreach mockup — regulated, auditable comms. Illustrative only:
          nothing is sent; the action is a clinician-approval queue stand-in. */}
      {outreachOpen && (
        <div className="fixed inset-0 z-[120] flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-black/60" onClick={() => setOutreachOpen(false)} />
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-6">
            <div className="flex items-start justify-between mb-1">
              <h3 className="text-base font-semibold text-slate-100" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Patient outreach — calibration advisory</h3>
              <button onClick={() => setOutreachOpen(false)} className="text-slate-500 hover:text-slate-300 text-sm">✕</button>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">MOCKUP · not wired</span>

            <div className="mt-4 space-y-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono text-slate-500">Recipients</span>
                <span className="font-mono text-slate-200">{displayedRoster.length} affected patient{displayedRoster.length === 1 ? '' : 's'}{filter ? ` · ${filter.label}` : ''}</span>
              </div>

              <div>
                <p className="text-xs font-mono text-slate-500 mb-2">Channel (approved, auditable)</p>
                <div className="flex flex-wrap gap-2">
                  {[
                    { k: 'portal', label: 'Secure patient-portal message' },
                    { k: 'email', label: 'Encrypted email' },
                    { k: 'sms', label: 'SMS reminder' },
                  ].map((c) => (
                    <button
                      key={c.k}
                      onClick={() => setChannel(c.k)}
                      className={`text-xs font-mono px-3 py-1.5 rounded-lg border transition-colors ${channel === c.k ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300' : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'}`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs font-mono text-slate-500 mb-2">Message template</p>
                <textarea
                  rows="4"
                  defaultValue={`Your continuous glucose monitor may have reported inaccurate readings during a recent device calibration issue. Please disregard affected readings, follow your usual safety checks, and your care team will follow up regarding recalibration or device replacement. No action is needed right now.`}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg p-3 text-xs text-slate-300 leading-relaxed focus:outline-none focus:border-cyan-500 resize-none"
                />
              </div>

              <p className="text-[11px] font-mono text-slate-500 leading-relaxed border-t border-slate-800 pt-3">
                Routed through approved, auditable channels (HIPAA / GDPR-compliant); requires <span className="text-slate-300">clinician sign-off</span> before send. No PHI leaves the governed Databricks environment — identifiers here are simulated.
              </p>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setOutreachOpen(false)} className="text-xs font-mono px-3 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800">Cancel</button>
              <button onClick={() => setOutreachOpen(false)} className="text-xs font-mono px-3 py-2 rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10">
                Queue for clinician approval <span className="text-slate-500">(mockup)</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
