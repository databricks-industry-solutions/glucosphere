import React from 'react';

// Grouped bars: % of device-observed readings in hypo (<70) / hyper (>180)
// range, per cohort (Baseline vs positive-/negative-bias cohorts during their
// incident windows) = the clinical blast radius. Semantic colors match the app:
// blue = hypo / under-read, red = hyper / over-read. Responsive (viewBox).
export default function PopulationRiskChart({ data = [] }) {
  if (!data.length) {
    return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">No population data</div>;
  }

  const order = { 'Baseline': 0, 'Positive cohort': 1, 'Negative cohort': 2 };
  const rows = [...data].sort((a, b) => (order[a.cohort] ?? 9) - (order[b.cohort] ?? 9));

  const W = 760, H = 340, pad = { top: 20, right: 132, bottom: 56, left: 52 };
  const innerW = W - pad.left - pad.right, innerH = H - pad.top - pad.bottom;
  const maxY = Math.max(10, ...rows.flatMap(r => [r.pctHypo, r.pctHyper]));

  const groupW = innerW / rows.length;
  const barW = Math.min(46, groupW / 3);
  const y = (v) => pad.top + innerH - (v / maxY) * innerH;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      {/* y grid + labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
        const yy = pad.top + innerH - t * innerH;
        return (
          <g key={i}>
            <line x1={pad.left} y1={yy} x2={pad.left + innerW} y2={yy} stroke="rgb(51 65 85 / 0.4)" strokeWidth="0.5" />
            <text x={pad.left - 8} y={yy + 3} textAnchor="end" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)">{(t * maxY).toFixed(0)}%</text>
          </g>
        );
      })}
      <text x={14} y={pad.top + innerH / 2} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)" transform={`rotate(-90 14 ${pad.top + innerH / 2})`}>% of readings</text>

      {/* grouped bars */}
      {rows.map((r, i) => {
        const cx = pad.left + i * groupW + groupW / 2;
        const hypoX = cx - barW - 3, hyperX = cx + 3;
        return (
          <g key={r.cohort}>
            <rect x={hypoX} y={y(r.pctHypo)} width={barW} height={pad.top + innerH - y(r.pctHypo)} rx="2" fill="#3b82f6" fillOpacity="0.8" />
            <text x={hypoX + barW / 2} y={y(r.pctHypo) - 4} textAnchor="middle" fontSize="9.5" fontFamily="monospace" fill="rgb(148 163 184)">{r.pctHypo}</text>
            <rect x={hyperX} y={y(r.pctHyper)} width={barW} height={pad.top + innerH - y(r.pctHyper)} rx="2" fill="#f43f5e" fillOpacity="0.8" />
            <text x={hyperX + barW / 2} y={y(r.pctHyper) - 4} textAnchor="middle" fontSize="9.5" fontFamily="monospace" fill="rgb(148 163 184)">{r.pctHyper}</text>
            <text x={cx} y={pad.top + innerH + 16} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(148 163 184)">{r.cohort.replace(' cohort', '')}</text>
          </g>
        );
      })}

      {/* legend */}
      <rect x={pad.left + innerW + 14} y={pad.top + 4} width="12" height="12" rx="2" fill="#3b82f6" fillOpacity="0.8" />
      <text x={pad.left + innerW + 30} y={pad.top + 14} fontSize="11" fontFamily="monospace" fill="rgb(148 163 184)">% hypo (&lt;70)</text>
      <rect x={pad.left + innerW + 14} y={pad.top + 24} width="12" height="12" rx="2" fill="#f43f5e" fillOpacity="0.8" />
      <text x={pad.left + innerW + 30} y={pad.top + 34} fontSize="11" fontFamily="monospace" fill="rgb(148 163 184)">% hyper (&gt;180)</text>
    </svg>
  );
}
