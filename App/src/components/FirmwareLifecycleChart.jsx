import React, { useState } from 'react';
import ChartTooltip from './ChartTooltip';

// Multi-line chart: device calibration error (MAE = |observed − true| glucose)
// per firmware version over time. Faulty firmwares spike during their incident
// window; clean versions stay near 0 — the "rollout → fault → fix" read.
// Responsive (viewBox), width-capped by the page for a compact footprint.
//
// Colour is by FAULT STATUS, not firmware order: faulty rollouts read warm
// (red / orange), clean versions read cool (green / cyan) — so a culprit can never
// show up green. `faultyFws` is the list of culprit versions (ordered by peak desc).
const FAULT_COLORS = ['#f43f5e', '#fb923c'];                       // culprits: red, orange
const CLEAN_COLORS = ['#22c55e', '#22d3ee', '#a78bfa', '#ec4899']; // clean: green/cyan/…

export default function FirmwareLifecycleChart({ data = [], faultyFws = [] }) {
  const [hover, setHover] = useState(null);
  if (!data.length) {
    return <div className="flex items-center justify-center h-64 text-slate-500 text-sm">No firmware data</div>;
  }

  // Wide, short aspect: full page width but compact height (data is sparse — flat
  // lines + a couple of spikes — so a tall plot is mostly empty). Short enough that
  // the chart + the ACT card + the Population-Risk hand-off all fit at 100% zoom.
  // Legend sits BELOW the plot (horizontal, centered) — less cluttered than crowding the
  // y-axis gutter. pad.left is widened to clear the Calibration-Drift matrix's row-label
  // column below, so the day points line up under the matrix's day cells (day0 ≈ first cell
  // centre, day6 ≈ last); the left gutter is otherwise empty by design (its width is driven by
  // that alignment, not the legend). Keep pad.left in sync with the matrix label width
  // (CalibrationDriftPanel: w-[11%]) if either changes.
  const W = 760, H = 184, pad = { top: 16, right: 48, bottom: 72, left: 132 };
  const innerW = W - pad.left - pad.right, innerH = H - pad.top - pad.bottom;

  const days = [...new Set(data.map(d => d.day))].sort();
  const versions = [...new Set(data.map(d => d.firmwareVersion))].sort();
  const maxY = Math.max(5, ...data.map(d => d.mae));

  // Colour by fault status (not firmware order): culprits warm, clean cool.
  const isFaulty = (ver) => faultyFws.includes(ver);
  const cleanVersions = versions.filter(v => !isFaulty(v));
  const colorFor = (ver) => isFaulty(ver)
    ? FAULT_COLORS[faultyFws.indexOf(ver) % FAULT_COLORS.length]
    : CLEAN_COLORS[cleanVersions.indexOf(ver) % CLEAN_COLORS.length];

  const x = (day) => pad.left + (days.length === 1 ? innerW / 2 : (days.indexOf(day) / (days.length - 1)) * innerW);
  const y = (v) => pad.top + innerH - (v / maxY) * innerH;

  const seriesFor = (ver) => days
    .map(day => { const row = data.find(d => d.day === day && d.firmwareVersion === ver); return row ? { day, v: row.mae } : null; })
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
      <text x={14} y={pad.top + innerH / 2} textAnchor="middle" fontSize="10" fontFamily="monospace" fill="rgb(100 116 139)" transform={`rotate(-90 14 ${pad.top + innerH / 2})`}>Device error — MAE (mg/dL)</text>

      {/* series */}
      {versions.map((ver, vi) => {
        const pts = seriesFor(ver);
        const color = colorFor(ver);
        const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(p.day)} ${y(p.v)}`).join(' ');
        return (
          <g key={ver}>
            <path d={path} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            {pts.map((p, i) => (
              <g key={i}>
                <circle cx={x(p.day)} cy={y(p.v)} r="3.5" fill={color} />
                <text x={x(p.day)} y={y(p.v) - 7} textAnchor="middle" fontSize="10" fontFamily="monospace" fill={color}>{p.v}</text>
                {/* invisible hover hit-target (bigger than the dot for easy targeting) */}
                <circle
                  cx={x(p.day)} cy={y(p.v)} r="8" fill="transparent" style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHover({ ax: x(p.day), ay: y(p.v), color, title: `FW ${ver}`, rows: [`${fmtDay(p.day)} · MAE ${p.v} mg/dL`] })}
                  onMouseLeave={() => setHover(null)}
                />
              </g>
            ))}
          </g>
        );
      })}

      {/* legend — horizontal, LEFT-aligned BELOW the plot (mirrors the matrix's footer
          legend so the two read as a set). Dot markers match the series' data-point dots;
          small font keeps it unobtrusive. */}
      {(() => {
        const ly = pad.top + innerH + 58;
        const step = 88;
        const startX = 24;   // panel left edge (clears the rotated y-axis title at x=14), mirroring the matrix footer legend below
        return versions.map((ver, vi) => {
          const lx = startX + vi * step;
          return (
            <g key={`lg-${ver}`}>
              <circle cx={lx} cy={ly - 2.5} r="3" fill={colorFor(ver)} />
              <text x={lx + 8} y={ly} fontSize="8" fontFamily="monospace" fill={isFaulty(ver) ? 'rgb(253 164 175)' : 'rgb(148 163 184)'}>FW {ver}{isFaulty(ver) ? ' ⚠' : ''}</text>
            </g>
          );
        });
      })()}

      {hover && <ChartTooltip {...hover} W={W} H={H} />}
    </svg>
  );
}
