import React from 'react';

// Reusable hover tooltip for the hand-rolled SVG charts that use an UNDISTORTED
// viewBox (preserveAspectRatio="xMidYMid meet") — Firmware Lifecycle + Population
// Risk. Coordinates are in viewBox space, so fontSize/padding match the chart's
// existing axis text. The card flips to the left of the anchor near the right
// edge and clamps vertically so it never spills outside the plot.
//
// Props: ax/ay = anchor point (viewBox units), W/H = viewBox bounds (for clamping),
// color = optional swatch, title = bold first line, rows = [string] detail lines.
export default function ChartTooltip({ ax, ay, W, H, color, title, rows = [] }) {
  const lineH = 13, padX = 8, padY = 7, charW = 6.2; // ~monospace advance @ 10.5px
  const swatchGap = color ? 12 : 0;
  const lines = [title, ...rows];
  const boxW = Math.max(...lines.map((l) => l.length)) * charW + padX * 2 + swatchGap;
  const boxH = lines.length * lineH + padY * 2;

  const flipX = ax + 12 + boxW > W;            // near right edge → draw to the left
  const bx = flipX ? ax - 12 - boxW : ax + 12;
  const by = Math.max(2, Math.min(H - boxH - 2, ay - boxH / 2));
  const textX = bx + padX + swatchGap;

  return (
    <g pointerEvents="none">
      <rect x={bx} y={by} width={boxW} height={boxH} rx="4" fill="rgb(2 6 23 / 0.96)" stroke="rgb(51 65 85)" strokeWidth="0.75" />
      {color && <rect x={bx + padX} y={by + padY + 2} width="8" height="8" rx="1.5" fill={color} />}
      {lines.map((l, i) => (
        <text
          key={i}
          x={textX}
          y={by + padY + 9 + i * lineH}
          fontSize="10.5"
          fontFamily="monospace"
          fill={i === 0 ? 'rgb(226 232 240)' : 'rgb(148 163 184)'}
          fontWeight={i === 0 ? 600 : 400}
        >
          {l}
        </text>
      ))}
    </g>
  );
}
