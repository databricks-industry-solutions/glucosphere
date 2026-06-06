import React, { useState } from 'react';
import { Link } from 'react-router-dom';

// Combined "exposure → fault classification" panel for the Population Risk page.
// Two stacked, ALIGNED plots in one shared 3-column grid (Firmware-Lifecycle style — chart on
// top, decomposition beneath, columns lined up):
//   row 1 — each cohort's device-reported %hypo / %hyper bar pair (Negative / Baseline / Positive)
//   row 2 — that cohort's confusion matrix directly below it (Under-read / Baseline / Over-read)
// The bar pair = the matrix's device-column totals (device-Low = %hypo, device-High = %hyper);
// the matrix splits each by TRUTH. All values are % of that cohort's in-incident readings.
// Axes read like a calibration plot: device-shown low→high left→right (columns), true high→low
// top→bottom (rows), so the agreement line runs bottom-left (Low|Low) → top-right (High|High).

const BANDS = ['Low', 'In-range', 'High'];      // columns (device-shown): low → high, left → right
const ROW_BANDS = ['High', 'In-range', 'Low'];  // rows (truth): high → low, top → bottom — so agreement runs bottom-left (Low|Low) → top-right (High|High), like a calibration / parity plot (truth high-up, device high-right)

// One bias cohort's confusion matrix. `cells` = {'truth|device': rawCount}. `mode`: 'row'
// (each row = 100%, per-class recall) | 'total' (whole grid = 100%, share of readings).
// `control` (baseline) → device ≈ truth, so off-diagonal is sensor noise, not a fault: render it
// neutral grey instead of amber/rose so it doesn't read as a false-alarm/missed event.
function ConfusionMatrix({ title, titleColor, cells, mode, control = false }) {
  const cnt = (t, d) => cells[`${t}|${d}`] || 0;
  const rowTotal = (t) => BANDS.reduce((s, d) => s + cnt(t, d), 0);
  const grand = BANDS.reduce((s, t) => s + rowTotal(t), 0);
  const diag = BANDS.reduce((s, b) => s + cnt(b, b), 0);
  const correctPct = grand ? Math.round((diag / grand) * 1000) / 10 : 0;
  const cellClass = (truth, device, c) => {
    if (!c) return 'text-slate-700 border border-transparent';
    if (truth === device) return 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30';
    if (control) return 'bg-slate-500/10 text-slate-400 border border-slate-600/40'; // noise, not fault
    if (device === 'In-range' && truth !== 'In-range') return 'bg-rose-500/15 text-rose-300 border border-rose-500/40'; // missed real event
    if (truth === 'In-range' && device !== 'In-range') return 'bg-amber-500/15 text-amber-300 border border-amber-500/30'; // false alarm
    return 'bg-rose-500/15 text-rose-300 border border-rose-500/40';
  };
  const sublabel = (truth, device, c) => {
    if (control || truth === device || !c) return null;
    if (device === 'In-range' && truth !== 'In-range') return `missed ${truth === 'High' ? 'hyper' : 'hypo'} ⚠`;
    if (truth === 'In-range') return `false ${device === 'High' ? 'hyper' : 'hypo'}`;
    return 'flip ⚠';
  };
  return (
    <div>
      <p className={`text-xs font-mono mb-2 text-center ${titleColor}`}>{title}<br /><span className="text-slate-500">{correctPct}% classified correctly</span></p>
      <table className="w-full text-[11px] font-mono border-collapse" style={{ tableLayout: 'fixed' }}>
        <thead>
          <tr className="text-slate-500">
            <th className="p-1 text-left font-normal text-[9px]" style={{ width: '58px' }}>true↓/dev→</th>
            {BANDS.map((d) => <th key={d} className="p-1 font-normal text-slate-400">{d}</th>)}
          </tr>
        </thead>
        <tbody className="text-center">
          {ROW_BANDS.map((truth) => {
            const rt = rowTotal(truth);
            return (
              <tr key={truth}>
                <td className="p-1 text-left text-slate-400">{truth}</td>
                {BANDS.map((device) => {
                  const c = cnt(truth, device);
                  const denom = mode === 'total' ? grand : rt;
                  const pct = denom ? Math.round((c / denom) * 1000) / 10 : 0;
                  const sl = sublabel(truth, device, c);
                  return (
                    <td key={device} className={`p-1 rounded align-middle ${cellClass(truth, device, c)}`} style={{ height: '42px' }}>
                      {c ? `${pct}${truth === device ? ' ✓' : ''}` : '0'}
                      {sl && <span className="block text-[8px] opacity-90">{sl}</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// One cohort's %hypo / %hyper bar pair, scaled to a shared max so heights compare across cohorts.
function CohortBars({ label, labelColor, hypo, hyper, max }) {
  const h = (v) => `${Math.max(1, (v / max) * 160)}px`;
  return (
    <div>
      <p className={`text-xs font-mono text-center mb-2 ${labelColor}`}>{label}</p>
      <div className="flex items-end justify-center gap-4" style={{ height: '190px' }}>
        <div className="flex flex-col items-center justify-end">
          <span className="text-xs font-mono text-blue-300 mb-1">{hypo}</span>
          <div className="w-9 rounded-t bg-blue-500/80" style={{ height: h(hypo) }} />
        </div>
        <div className="flex flex-col items-center justify-end">
          <span className="text-xs font-mono text-rose-300 mb-1">{hyper}</span>
          <div className="w-9 rounded-t bg-rose-500/80" style={{ height: h(hyper) }} />
        </div>
      </div>
      <p className="text-[10px] font-mono text-slate-500 text-center mt-1 border-t border-slate-800 pt-1">% hypo · % hyper</p>
    </div>
  );
}

export default function CohortFaultPanel({ data = [], confusion = { positive: {}, negative: {}, baseline: {} }, loading = false }) {
  const [mode, setMode] = useState('total'); // default 'total' (share of all — grid sums to 100%) | 'row' (per-true-band recall)
  const find = (prefix) => data.find((r) => (r.cohort || '').toLowerCase().startsWith(prefix)) || { pctHypo: 0, pctHyper: 0 };
  const neg = find('negative'), base = find('baseline'), pos = find('positive');
  const max = Math.max(10, neg.pctHypo, neg.pctHyper, base.pctHypo, base.pctHyper, pos.pctHypo, pos.pctHyper);
  const ready = !loading && (Object.keys(confusion.positive).length > 0 || Object.keys(confusion.negative).length > 0);

  return (
    <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-slate-200 mb-1" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
        Hypo / hyper exposure → fault classification, by cohort <span className="text-sm font-normal text-slate-500">— in-incident (~3h fault window)</span>
      </h2>
      <p className="text-xs font-mono text-slate-500 mb-1">
        Each cohort's <span className="text-slate-300">device-reported</span> %hypo/%hyper (top) sits above its <span className="text-slate-300">confusion matrix</span> (below): the bars are the matrix's device-column totals; the matrix splits each by what was <span className="text-slate-300">truly</span> happening.
      </p>
      <p className="text-[11px] font-mono text-cyan-400/90 mb-4">All values are % of each cohort's in-incident readings.</p>

      {!ready ? (
        <div className="flex items-center justify-center h-64 text-slate-500">Loading cohort exposure…</div>
      ) : (
        <>
          {/* Row 1 — bar pairs, in a shared 3-column grid */}
          <div className="grid grid-cols-3 gap-6">
            <CohortBars label="↓ Negative (under-read)" labelColor="text-slate-300" hypo={neg.pctHypo} hyper={neg.pctHyper} max={max} />
            <CohortBars label="Baseline (unaffected)" labelColor="text-slate-400" hypo={base.pctHypo} hyper={base.pctHyper} max={max} />
            <CohortBars label="↑ Positive (over-read)" labelColor="text-amber-300" hypo={pos.pctHypo} hyper={pos.pctHyper} max={max} />
          </div>

          {/* legend + normalization toggle */}
          <div className="flex flex-wrap items-end justify-between gap-4 my-4">
            <div className="flex flex-wrap gap-3 text-[11px] font-mono text-slate-500">
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-emerald-500/30 border border-emerald-500/50 align-middle" /> device agreed</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-amber-500/30 border border-amber-500/50 align-middle" /> false alarm</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-rose-500/30 border border-rose-500/50 align-middle" /> ⚠ missed real event</span>
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm bg-slate-500/20 border border-slate-600/50 align-middle" /> sensor noise (baseline)</span>
            </div>
            <div className="shrink-0 text-right">
              <span className="block text-[9px] font-mono text-slate-500 mb-0.5 tracking-wide">Normalize</span>
              <div className="inline-flex rounded-md border border-slate-700 overflow-hidden text-[11px] font-mono" role="group" aria-label="Confusion matrix normalization">
                <button onClick={() => setMode('row')} title="Of readings truly in each band, what % the device showed (each row = 100%)"
                  className={`px-2.5 py-1 transition-colors ${mode === 'row' ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>Per true band <span className="opacity-70">(row %)</span></button>
                <button onClick={() => setMode('total')} title="Each cell as a share of all the cohort's in-incident readings (whole grid = 100%)"
                  className={`px-2.5 py-1 transition-colors border-l border-slate-700 ${mode === 'total' ? 'bg-slate-700 text-slate-100 font-semibold' : 'text-slate-400 hover:text-slate-200'}`}>Share of all <span className="opacity-70">(total %)</span></button>
              </div>
            </div>
          </div>

          {/* Row 2 — matrices, SAME 3-column grid → aligned under their bars */}
          <div className="grid grid-cols-3 gap-6">
            <ConfusionMatrix title="↓ Under-read (Beta / Delta)" titleColor="text-slate-300" cells={confusion.negative} mode={mode} />
            <ConfusionMatrix title="Baseline — control" titleColor="text-slate-400" cells={confusion.baseline} mode={mode} control />
            <ConfusionMatrix title="↑ Over-read (Alpha / Gamma)" titleColor="text-amber-300" cells={confusion.positive} mode={mode} />
          </div>

          <p className="text-[11px] font-mono text-slate-600 mt-4">
            The fault doesn't change the patient's <span className="text-slate-300">true</span> glucose — the matrix <span className="text-slate-300">rows</span> (truth) stay ≈ baseline across all three. It corrupts the <span className="text-slate-300">reading</span> — the <span className="text-slate-300">columns</span> (device) are what diverge: an over-read device hides real lows (⚠ missed hypo) &amp; cries wolf on highs; an under-read device hides real highs (⚠ missed hyper) &amp; cries wolf on lows. Baseline is the unaffected control (device ≈ truth, ~95% agree; its scattered cells are sensor noise). Over the full week these errors wash to ~0.5&nbsp;pp.
          </p>
          <Link to="/metrics-explained#me-firmware-fault-impact" className="inline-block mt-3 text-xs font-mono text-cyan-400 hover:text-cyan-300">
            How this is computed →
          </Link>
        </>
      )}
    </section>
  );
}
