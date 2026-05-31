import React from 'react';

// Multi-line chart: out-of-range rate (%) per firmware version over time.
// The faulty firmware spikes during the incident window; clean versions stay
// flat — the "rollout → fault → fix" read. Responsive (viewBox + w-full).
const COLORS = ['#f43f5e', '#f59e0b', '#22c55e', '#22d3ee', '#a78bfa', '#ec4899'];

export default function FirmwareLifecycleChart({ data = [] }) {
  if (!data.length) {
    return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">No firmware data</div>;
  }

  const W = 760, H = 340, pad = { top: 20, right: 132, bottom: 52, left: 52 };
  const innerW = W - pad.left - pad.right, innerH = H - pad.top - pad.bottom;

  const days = [...new Set(data.map(d => d.day))].sort();
  const versions = [...new Set(data.map(d => d.firmwareVersion))].sort();
  const maxY = Math.max(5, ...data.map(d => d.oorRatePct));

  const x = (day) => pad.left + (days.length === 1 ? innerW / 2 : (days.indexOf(day) / (days.length - 1)) * innerW);
  const y = (v) => pad.top + innerH - (v / maxY) * innerH;

  const seriesFor = (ver) => days
    .map(day => { const row = data.find(d => d.day === day && d.firmwareVersion === ver); return row ? { day, v: row.oorRatePct } : null; })
    .filter(Boolean);

  const fmtDay = (d) => (d || '').slice(5); // MM-DD

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
      {/* y grid + labels */}
      {[0, 0.25, 0.5, 0.75, 1].map((t, i) => {
        const yy = pad.top + innerH - t * innerH;
        return (
          <g key={i}>
            <line x1={pad.left} y1={yy} x2={pad.left + innerW} y2={yy} stroke="rgb(51 65 85 / 0.4)" strokeWidth="0.5" />
            <text x={pad.left - 8} y={yy + 3} textAnchor="end" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)">{(t * maxY).toFixed(1)}</text>
          </g>
        );
      })}
      {/* x labels */}
      {days.map((d, i) => (
        <text key={i} x={x(d)} y={pad.top + innerH + 16} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)">{fmtDay(d)}</text>
      ))}
      <text x={pad.left + innerW / 2} y={H - 6} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)">Day</text>
      <text x={14} y={pad.top + innerH / 2} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)" transform={`rotate(-90 14 ${pad.top + innerH / 2})`}>Out-of-range rate (%)</text>

      {/* series */}
      {versions.map((ver, vi) => {
        const pts = seriesFor(ver);
        const color = COLORS[vi % COLORS.length];
        const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(p.day)} ${y(p.v)}`).join(' ');
        return (
          <g key={ver}>
            <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {pts.map((p, i) => <circle key={i} cx={x(p.day)} cy={y(p.v)} r="2.5" fill={color} />)}
            {/* legend */}
            <line x1={pad.left + innerW + 12} y1={pad.top + 6 + vi * 20} x2={pad.left + innerW + 30} y2={pad.top + 6 + vi * 20} stroke={color} strokeWidth="2.5" />
            <text x={pad.left + innerW + 35} y={pad.top + 9 + vi * 20} fontSize="11" fontFamily="monospace" fill="rgb(148 163 184)">FW {ver}</text>
          </g>
        );
      })}
    </svg>
  );
}
