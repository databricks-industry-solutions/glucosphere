import React from 'react';

// PARKED IDEA (user 2026-05-31): add a toggle to break regional distribution down
// BY DEVICE TYPE (region × device_type) — needs a GROUP BY region, device_model query
// + a small toggle control. Feature scope; revisit alongside Phase-3 geo work.
//
// Stylized regional distribution ("schematic geo", no map dependency). Each region
// is a bubble placed in a rough West→East geographic layout on a faint map-coordinate
// field; bubble size ∝ monitored footprint (patients), color ∝ out-of-range volume
// (green→red). Honest to the coarse NA/EMEA/APAC region granularity in the data.

// Expansions for the coarse region acronyms (business macro-regions, not codes).
const REGION_NAMES = {
  NA: 'North America', 'NORTH AMERICA': 'North America', AMERICAS: 'Americas',
  LATAM: 'Latin America', 'SOUTH AMERICA': 'South America',
  EMEA: 'Europe · Middle East · Africa', EUROPE: 'Europe', AFRICA: 'Africa', 'MIDDLE EAST': 'Middle East',
  APAC: 'Asia-Pacific', ASIA: 'Asia', ANZ: 'Australia · New Zealand', OCEANIA: 'Oceania',
};

// Approximate positions in the 0..100 × 0..60 viewBox (relative geography, not precise).
const POS = {
  NA: { x: 20, y: 24 }, 'NORTH AMERICA': { x: 20, y: 24 }, AMERICAS: { x: 22, y: 28 },
  LATAM: { x: 29, y: 45 }, 'SOUTH AMERICA': { x: 29, y: 45 },
  EMEA: { x: 50, y: 24 }, EUROPE: { x: 48, y: 18 }, AFRICA: { x: 52, y: 38 }, 'MIDDLE EAST': { x: 58, y: 30 },
  APAC: { x: 78, y: 30 }, ASIA: { x: 74, y: 22 }, ANZ: { x: 84, y: 47 }, OCEANIA: { x: 84, y: 47 },
};

// green (34,197,94) → amber (250,204,21) → red (244,63,94)
function rampColor(t) {
  const lerp = (a, b, u) => Math.round(a + (b - a) * u);
  const clamp = Math.max(0, Math.min(1, t));
  const [c1, c2, u] = clamp < 0.5
    ? [[34, 197, 94], [250, 204, 21], clamp / 0.5]
    : [[250, 204, 21], [244, 63, 94], (clamp - 0.5) / 0.5];
  return `rgb(${lerp(c1[0], c2[0], u)}, ${lerp(c1[1], c2[1], u)}, ${lerp(c1[2], c2[2], u)})`;
}

export default function RegionMap({ regions = [] }) {
  if (!regions.length) {
    return <div className="flex items-center justify-center h-48 text-slate-500 text-sm">No regional data</div>;
  }
  const maxPatients = Math.max(...regions.map(r => r.patientCount), 1);
  const maxOor = Math.max(...regions.map(r => r.oorEvents), 1);

  // Resolve a position per region; unknown regions spread along the bottom band.
  let fallbackI = 0;
  const placed = regions.map(r => {
    const key = (r.region || '').toUpperCase();
    const pos = POS[key] || { x: 18 + (fallbackI++ * 24) % 70, y: 50 };
    return { ...r, ...pos };
  });

  return (
    <div>
      <svg viewBox="0 0 100 60" className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
        {/* faint map-coordinate field (latitudes + meridians) */}
        <rect x="1" y="1" width="98" height="58" rx="3" fill="none" stroke="rgb(51 65 85 / 0.4)" strokeWidth="0.4" />
        {[18, 30, 42].map(y => (
          <line key={y} x1="2" y1={y} x2="98" y2={y} stroke="rgb(51 65 85 / 0.35)" strokeWidth="0.3" strokeDasharray="1.5 2" />
        ))}
        {[33, 66].map(x => (
          <line key={x} x1={x} y1="2" x2={x} y2="58" stroke="rgb(51 65 85 / 0.35)" strokeWidth="0.3" strokeDasharray="1.5 2" />
        ))}
        {/* region bubbles */}
        {placed.map((r, i) => {
          const radius = 3 + 7 * Math.sqrt(r.patientCount / maxPatients);
          const fill = rampColor(r.oorEvents / maxOor);
          return (
            <g key={i}>
              <circle cx={r.x} cy={r.y} r={radius} fill={fill} fillOpacity="0.8" stroke="rgb(226 232 240 / 0.5)" strokeWidth="0.4" />
              <text x={r.x} y={r.y + radius + 4} textAnchor="middle" fontSize="4" fontFamily="monospace" fill="rgb(203 213 225)">{r.region}</text>
            </g>
          );
        })}
      </svg>
      {/* region key — expand the coarse NA/EMEA/APAC acronyms (only those present) */}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[10px] font-mono text-slate-400">
        {placed.map((r, i) => {
          const name = REGION_NAMES[(r.region || '').toUpperCase()];
          return name ? (
            <span key={i}><span className="text-slate-200">{r.region}</span> — {name}</span>
          ) : null;
        })}
      </div>
      {/* encoding caption */}
      <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-slate-500">
        <span>● size = patients monitored</span>
        <span className="flex items-center gap-1">
          out-of-range
          <span className="inline-block w-12 h-2 rounded" style={{ background: 'linear-gradient(90deg, rgb(34,197,94), rgb(250,204,21), rgb(244,63,94))' }} />
        </span>
      </div>
    </div>
  );
}
