import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import {
  getIncidentImpactData,
  getGlucoseTimelineData,
  getAbsoluteGlucoseTimelineData,
  getIncidentSummary,
} from '../pages/GlucoseLanding/incidentQueries';

/**
 * Incident Impact Chart - Shows MAE over time with incident period highlighted
 * Similar to the top chart in the provided image
 */
export function IncidentImpactChart() {
  const [data, setData] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [impactData, summaryData] = await Promise.all([
          getIncidentImpactData(),
          getIncidentSummary()
        ]);
        setData(impactData);
        setSummary(summaryData);
      } catch (err) {
        console.error('Error loading incident impact data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">Loading incident data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-rose-400">Error: {error}</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No incident data available</div>
      </div>
    );
  }

  // Calculate chart dimensions and scales
  const chartWidth = 1400;
  const chartHeight = 320;
  const padding = { top: 60, right: 160, bottom: 80, left: 80 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Extract values for scaling and filter valid data only
  const validData = data.filter(d => d.time && !isNaN(new Date(d.time).getTime()));
  
  if (validData.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No valid incident data available</div>
      </div>
    );
  }
  
  // Bidirectional-aware: two distinct MAE lines
  //   mae_fleet:    Fleet-wide MAE across all patients (diluted by 70% unaffected)
  //   mae_affected: MAE filtered to affected patients only (true bias magnitude)
  // Old code used d.mae_15m and d.mae_30m (which was just mae_15m × 1.2 —
  // redundant). Now the two lines carry distinct information: fleet vs affected.
  const mae15Values = validData.map(d => d.mae_fleet || 0);
  const mae30Values = validData.map(d => d.mae_affected || 0);
  const timeValues = validData.map(d => new Date(d.time).getTime());

  const maxMAE = Math.max(...mae15Values, ...mae30Values, summary?.baseline_mae_30m || 10) * 1.1;
  const minTime = Math.min(...timeValues);
  const maxTime = Math.max(...timeValues);
  const timeRange = maxTime - minTime;

  // Scale functions
  const xScale = (time) => {
    const t = new Date(time);
    return padding.left + ((t - minTime) / timeRange) * innerWidth;
  };

  const yScale = (value) => {
    return chartHeight - padding.bottom - (value / maxMAE) * innerHeight;
  };

  // Create path data for MAE lines
  const mae15Path = validData
    .map((d, i) => {
      const x = xScale(d.time);
      const y = yScale(d.mae_fleet || 0);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  const mae30Path = validData
    .map((d, i) => {
      const x = xScale(d.time);
      const y = yScale(d.mae_affected || 0);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  // Find incident periods — there can be more than one contiguous block (two
  // separate incidents at Day 2 and Day 5 in the mirror design). Group
  // consecutive incident_period=1 rows so each one shades separately.
  const incidentBlocks = (() => {
    const blocks = [];
    let inBlock = false;
    let blockStart = null;
    validData.forEach((d, idx) => {
      if (d.incident_period === 1 && !inBlock) {
        inBlock = true;
        blockStart = d.time;
      } else if (d.incident_period !== 1 && inBlock) {
        inBlock = false;
        blocks.push({ start: blockStart, end: validData[idx - 1].time });
      }
    });
    if (inBlock) blocks.push({ start: blockStart, end: validData[validData.length - 1].time });
    return blocks;
  })();

  // Format date for x-axis labels
  const formatDate = (date) => {
    const d = new Date(date);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  };

  // Generate x-axis ticks (show 6 dates across the timeline)
  const xAxisTicks = [];
  for (let i = 0; i <= 5; i++) {
    const tickTime = new Date(minTime + (timeRange / 5) * i);
    xAxisTicks.push({
      x: xScale(tickTime),
      label: formatDate(tickTime)
    });
  }

  // Generate y-axis ticks
  const yAxisTicks = [];
  const yStep = Math.ceil(maxMAE / 5);
  for (let i = 0; i <= 5; i++) {
    const value = i * yStep;
    if (value <= maxMAE) {
      yAxisTicks.push({
        y: yScale(value),
        label: value.toFixed(1)
      });
    }
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col lg:flex-row gap-5">
      {/* Chart Title (left column) */}
      <div className="lg:w-48 lg:shrink-0">
        <h3 className="text-sm font-semibold text-slate-200 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Incident Impact: {summary?.incident_description || 'Device Calibration Issue'}
        </h3>
        <p className="text-xs text-slate-500 font-mono">
          Mean Absolute Error (MAE) Timeline - 7 Day Window
        </p>
      </div>

      {/* SVG Chart (right, responsive) */}
      <div className="flex-1 min-w-0">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          {/* Incident period highlights — one rectangle per contiguous incident block.
              With the two-window mirror design there are two separate incidents (Day 2
              and Day 5); rendering each one separately avoids one big rect spanning
              the gap between them. */}
          {incidentBlocks.map((blk, i) => (
            <rect
              key={`mae-incident-${i}`}
              x={xScale(blk.start)}
              y={padding.top}
              width={Math.max(2, xScale(blk.end) - xScale(blk.start))}
              height={innerHeight}
              fill="rgb(248 113 113 / 0.1)"
              stroke="rgb(248 113 113 / 0.3)"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
          ))}

          {/* Baseline MAE reference line */}
          {summary?.baseline_mae_30m && (
            <>
              <line
                x1={padding.left}
                y1={yScale(summary.baseline_mae_30m)}
                x2={chartWidth - padding.right}
                y2={yScale(summary.baseline_mae_30m)}
                stroke="rgb(148 163 184)"
                strokeWidth="1"
                strokeDasharray="4 4"
                opacity="0.5"
              />
              <text
                x={chartWidth - padding.right + 5}
                y={yScale(summary.baseline_mae_30m) + 4}
                fill="rgb(148 163 184)"
                fontSize="10"
                fontFamily="monospace"
              >
                Baseline ({summary.baseline_mae_30m.toFixed(1)})
              </text>
            </>
          )}

          {/* Y-axis */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={chartHeight - padding.bottom}
            stroke="rgb(71 85 105)"
            strokeWidth="1"
          />

          {/* Y-axis ticks and labels */}
          {yAxisTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padding.left - 5}
                y1={tick.y}
                x2={padding.left}
                y2={tick.y}
                stroke="rgb(71 85 105)"
                strokeWidth="1"
              />
              <text
                x={padding.left - 10}
                y={tick.y + 4}
                fill="rgb(148 163 184)"
                fontSize="11"
                textAnchor="end"
                fontFamily="monospace"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* Y-axis label */}
          <text
            x={20}
            y={chartHeight / 2}
            fill="rgb(148 163 184)"
            fontSize="12"
            textAnchor="middle"
            transform={`rotate(-90 20 ${chartHeight / 2})`}
            fontFamily="monospace"
          >
            MAE (mg/dL)
          </text>

          {/* X-axis */}
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="rgb(71 85 105)"
            strokeWidth="1"
          />

          {/* X-axis ticks and labels */}
          {xAxisTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={tick.x}
                y1={chartHeight - padding.bottom}
                x2={tick.x}
                y2={chartHeight - padding.bottom + 5}
                stroke="rgb(71 85 105)"
                strokeWidth="1"
              />
              <text
                x={tick.x}
                y={chartHeight - padding.bottom + 20}
                fill="rgb(148 163 184)"
                fontSize="11"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* X-axis label */}
          <text
            x={chartWidth / 2}
            y={chartHeight - 10}
            fill="rgb(148 163 184)"
            fontSize="12"
            textAnchor="middle"
            fontFamily="monospace"
          >
            Time
          </text>

          {/* MAE Affected-only line (orange) — shows true device-error magnitude during incident (~45 mg/dL peak) */}
          <path
            d={mae30Path}
            fill="none"
            stroke="rgb(251 146 60)"
            strokeWidth="1.5"
            opacity="0.9"
          />

          {/* MAE Fleet-wide line (blue) — diluted by 70% unaffected patients (~17 mg/dL peak) */}
          <path
            d={mae15Path}
            fill="none"
            stroke="rgb(59 130 246)"
            strokeWidth="1.5"
            opacity="0.9"
          />


          {/* Legend */}
          <g transform={`translate(${padding.left + 20}, ${padding.top + 10})`}>
            <line x1="0" y1="0" x2="30" y2="0" stroke="rgb(59 130 246)" strokeWidth="2.5" />
            <text x="35" y="4" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              MAE — fleet-wide
            </text>

            <line x1="0" y1="20" x2="30" y2="20" stroke="rgb(251 146 60)" strokeWidth="2" />
            <text x="35" y="24" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              MAE — affected patients
            </text>

            <rect x="0" y="35" width="30" height="10" fill="rgb(248 113 113 / 0.2)" stroke="rgb(248 113 113 / 0.5)" />
            <text x="35" y="44" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Incident (3h)
            </text>

            <line x1="0" y1="60" x2="30" y2="60" stroke="rgb(148 163 184)" strokeWidth="1" strokeDasharray="4 4" opacity="0.5" />
            <text x="35" y="64" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Baseline MAE ({summary?.baseline_mae_30m?.toFixed(1) || '5.8'})
            </text>
          </g>

        </svg>
      </div>
    </div>
  );
}

/**
 * Glucose Timeline Chart — signed device bias (observed − true) per direction
 * cohort over time. Outside incident: both lines ≈ 0 (devices match true).
 * Inside incident: positive cohort spikes to +bias_magnitude, negative drops
 * to -bias_magnitude. Subtraction cancels diurnal glucose fluctuation, so the
 * incident is the only visually prominent feature.
 */
export function GlucoseTimelineChart() {
  const [data, setData] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const [timelineData, summaryData] = await Promise.all([
          getGlucoseTimelineData(),
          getIncidentSummary()
        ]);
        setData(timelineData);
        setSummary(summaryData);
      } catch (err) {
        console.error('Error loading glucose timeline data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">Loading glucose timeline...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-rose-400">Error: {error}</div>
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No glucose timeline data available</div>
      </div>
    );
  }

  // Calculate chart dimensions and scales
  const chartWidth = 1400;
  const chartHeight = 320;
  const padding = { top: 60, right: 160, bottom: 80, left: 80 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  // Extract values for scaling and filter valid data only
  const validData = data.filter(d => d.time && !isNaN(new Date(d.time).getTime()));
  
  if (validData.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No valid glucose timeline data available</div>
      </div>
    );
  }
  
  // Delta view: render the signed device bias (observed − true) per cohort.
  // Outside incident: both ≈ 0 (no bias). Inside: positive ≈ +bias_magnitude,
  // negative ≈ -bias_magnitude. Diurnal glucose fluctuations cancel in the
  // subtraction, so the incident is the only visually prominent feature.
  const biasPositiveValues = validData.map(d => d.bias_positive).filter(v => v != null);
  const biasNegativeValues = validData.map(d => d.bias_negative).filter(v => v != null);
  const timeValues = validData.map(d => new Date(d.time).getTime());

  const allBiasValues = [...biasPositiveValues, ...biasNegativeValues];
  // Symmetric y-axis around 0 so positive and negative cohorts are visually
  // balanced. Pad to nearest 10 with at least ±55 minimum so the legend at
  // top-left has headroom and the incident-window peaks aren't clipped.
  const absMax = Math.max(...allBiasValues.map(v => Math.abs(v)), 50);
  const maxGlucose = Math.ceil((absMax * 1.20) / 10) * 10;  // round up to nearest 10
  const minGlucose = -maxGlucose;
  const minTime = Math.min(...timeValues);
  const maxTime = Math.max(...timeValues);
  const timeRange = maxTime - minTime;

  // Scale functions
  const xScale = (time) => {
    const t = new Date(time);
    return padding.left + ((t - minTime) / timeRange) * innerWidth;
  };

  const yScale = (value) => {
    return chartHeight - padding.bottom - ((value - minGlucose) / (maxGlucose - minGlucose)) * innerHeight;
  };

  // Build two bias paths — bias_positive (red, ≈ 0 outside / ≈ +bias inside)
  // and bias_negative (blue, ≈ 0 outside / ≈ -bias inside). Skip null points
  // (no data for that cohort at that minute) by breaking the path with an M
  // command on the next valid point.
  const buildPath = (yKey) => {
    let started = false;
    const segments = [];
    validData.forEach((d) => {
      const v = d[yKey];
      if (v == null) {
        // Break the line on null — next valid point starts a fresh segment.
        started = false;
        return;
      }
      const x = xScale(d.time);
      const y = yScale(v);
      segments.push(`${started ? 'L' : 'M'} ${x} ${y}`);
      started = true;
    });
    return segments.join(' ');
  };
  const biasPositivePath = buildPath('bias_positive');
  const biasNegativePath = buildPath('bias_negative');
  // Horizontal zero baseline for visual reference (no bias)
  const zeroY = yScale(0);

  // Find incident periods — same as the MAE chart: group consecutive incident_period=1
  // rows so two-window incidents render as two separate shaded blocks (not one big
  // box spanning the gap).
  const incidentBlocks = (() => {
    const blocks = [];
    let inBlock = false;
    let blockStart = null;
    validData.forEach((d, idx) => {
      if (d.incident_period === 1 && !inBlock) {
        inBlock = true;
        blockStart = d.time;
      } else if (d.incident_period !== 1 && inBlock) {
        inBlock = false;
        blocks.push({ start: blockStart, end: validData[idx - 1].time });
      }
    });
    if (inBlock) blocks.push({ start: blockStart, end: validData[validData.length - 1].time });
    return blocks;
  })();

  // Format date for x-axis labels
  const formatDate = (date) => {
    const d = new Date(date);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };

  // Generate x-axis ticks
  const xAxisTicks = [];
  for (let i = 0; i <= 5; i++) {
    const tickTime = new Date(minTime + (timeRange / 5) * i);
    xAxisTicks.push({
      x: xScale(tickTime),
      label: formatDate(tickTime)
    });
  }

  // Generate y-axis ticks
  const yAxisTicks = [];
  const yStep = Math.ceil((maxGlucose - minGlucose) / 5 / 20) * 20; // Round to nearest 20
  for (let i = 0; i <= 5; i++) {
    const value = minGlucose + (i * yStep);
    if (value <= maxGlucose) {
      yAxisTicks.push({
        y: yScale(value),
        label: Math.round(value)
      });
    }
  }

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col lg:flex-row gap-5">
      {/* Chart Title (left column) */}
      <div className="lg:w-48 lg:shrink-0">
        <h3 className="text-sm font-semibold text-slate-200 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Device Calibration Bias Over Time (±40 mg/dL Bidirectional)
        </h3>
        <p className="text-xs text-slate-500 font-mono">
          Signed device bias (observed − true glucose) per direction cohort. Outside incident: both lines ≈ 0 (devices match true). Inside incident: positive cohort spikes to +40, negative drops to −40.
        </p>
      </div>

      {/* SVG Chart (right, responsive) */}
      <div className="flex-1 min-w-0">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          {/* Incident period highlights — one rectangle per contiguous incident block.
              Two-window mirror design renders each incident (Day 2 + Day 5) separately. */}
          {incidentBlocks.map((blk, i) => (
            <rect
              key={`bias-incident-${i}`}
              x={xScale(blk.start)}
              y={padding.top}
              width={Math.max(2, xScale(blk.end) - xScale(blk.start))}
              height={innerHeight}
              fill="rgb(248 113 113 / 0.1)"
              stroke="rgb(248 113 113 / 0.3)"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
          ))}

          {/* Y-axis */}
          <line
            x1={padding.left}
            y1={padding.top}
            x2={padding.left}
            y2={chartHeight - padding.bottom}
            stroke="rgb(71 85 105)"
            strokeWidth="1"
          />

          {/* Y-axis ticks and labels */}
          {yAxisTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={padding.left - 5}
                y1={tick.y}
                x2={padding.left}
                y2={tick.y}
                stroke="rgb(71 85 105)"
                strokeWidth="1"
              />
              <text
                x={padding.left - 10}
                y={tick.y + 4}
                fill="rgb(148 163 184)"
                fontSize="11"
                textAnchor="end"
                fontFamily="monospace"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* Y-axis label */}
          <text
            x={20}
            y={chartHeight / 2}
            fill="rgb(148 163 184)"
            fontSize="12"
            textAnchor="middle"
            transform={`rotate(-90 20 ${chartHeight / 2})`}
            fontFamily="monospace"
          >
            Device Bias (mg/dL)
          </text>

          {/* X-axis */}
          <line
            x1={padding.left}
            y1={chartHeight - padding.bottom}
            x2={chartWidth - padding.right}
            y2={chartHeight - padding.bottom}
            stroke="rgb(71 85 105)"
            strokeWidth="1"
          />

          {/* X-axis ticks and labels */}
          {xAxisTicks.map((tick, i) => (
            <g key={i}>
              <line
                x1={tick.x}
                y1={chartHeight - padding.bottom}
                x2={tick.x}
                y2={chartHeight - padding.bottom + 5}
                stroke="rgb(71 85 105)"
                strokeWidth="1"
              />
              <text
                x={tick.x}
                y={chartHeight - padding.bottom + 20}
                fill="rgb(148 163 184)"
                fontSize="11"
                textAnchor="middle"
                fontFamily="monospace"
              >
                {tick.label}
              </text>
            </g>
          ))}

          {/* X-axis label */}
          <text
            x={chartWidth / 2}
            y={chartHeight - 10}
            fill="rgb(148 163 184)"
            fontSize="12"
            textAnchor="middle"
            fontFamily="monospace"
          >
            Time
          </text>

          {/* Zero baseline (no bias reference) */}
          <line
            x1={padding.left}
            y1={zeroY}
            x2={chartWidth - padding.right}
            y2={zeroY}
            stroke="rgb(148 163 184)"
            strokeWidth="1"
            strokeDasharray="4 4"
            opacity="0.6"
          />
          <text
            x={chartWidth - padding.right + 5}
            y={zeroY + 4}
            fill="rgb(148 163 184)"
            fontSize="10"
            fontFamily="monospace"
          >
            no bias
          </text>

          {/* Positive-bias cohort bias (red, ≈ 0 outside / spikes to +40 inside incident) */}
          <path
            d={biasPositivePath}
            fill="none"
            stroke="rgb(239 68 68)"
            strokeWidth="1.5"
            opacity="0.9"
          />

          {/* Negative-bias cohort bias (blue, ≈ 0 outside / drops to -40 inside incident) */}
          <path
            d={biasNegativePath}
            fill="none"
            stroke="rgb(59 130 246)"
            strokeWidth="1.5"
            opacity="0.9"
          />


          {/* Legend */}
          <g transform={`translate(${padding.left + 20}, ${padding.top + 10})`}>
            <line x1="0" y1="0" x2="40" y2="0" stroke="rgb(239 68 68)" strokeWidth="2" />
            <text x="45" y="4" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Positive bias (+40)
            </text>

            <line x1="0" y1="20" x2="40" y2="20" stroke="rgb(59 130 246)" strokeWidth="2" />
            <text x="45" y="24" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Negative bias (−40)
            </text>

            <line x1="0" y1="40" x2="40" y2="40" stroke="rgb(148 163 184)" strokeWidth="1" strokeDasharray="4 4" opacity="0.6" />
            <text x="45" y="44" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Zero bias
            </text>

            <rect x="0" y="55" width="40" height="10" fill="rgb(248 113 113 / 0.2)" stroke="rgb(248 113 113 / 0.5)" />
            <text x="45" y="64" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Incident (3h)
            </text>
          </g>

        </svg>
      </div>
    </div>
  );
}

/**
 * Glucose Absolute Chart — absolute glucose timeline per direction cohort.
 * Three lines: darkgray True (ground truth — matches unified palette across
 * notebook + app), red Positive cohort device readings (spikes UP
 * +bias_magnitude during window 1), blue Negative cohort device readings
 * (drops DOWN -bias_magnitude during window 2). Mirrors the notebook
 * 3-panel chart's middle "Affected Patients Only" panel.
 */
export function GlucoseAbsoluteChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const rows = await getAbsoluteGlucoseTimelineData();
        setData(rows);
      } catch (err) {
        console.error('Error loading absolute glucose timeline data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">Loading absolute glucose timeline...</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-rose-400">Error: {error}</div>
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No absolute glucose timeline data available</div>
      </div>
    );
  }

  // Layout (same scale as the other charts)
  const chartWidth = 1400;
  const chartHeight = 320;
  const padding = { top: 60, right: 160, bottom: 80, left: 80 };
  const innerWidth = chartWidth - padding.left - padding.right;
  const innerHeight = chartHeight - padding.top - padding.bottom;

  const validData = data.filter(d => d.time && !isNaN(new Date(d.time).getTime()));
  if (validData.length === 0) {
    return (
      <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 h-96 flex items-center justify-center">
        <div className="text-slate-400">No valid absolute glucose timeline data available</div>
      </div>
    );
  }

  // Extract values; allow nulls (some minutes may have no reading per cohort)
  const allGlucoseValues = validData.flatMap(d => [d.glucose_true, d.glucose_positive, d.glucose_negative]).filter(v => v != null);
  const timeValues = validData.map(d => new Date(d.time).getTime());

  // Y-axis fit to actual glucose range — use observed min/max with a small pad.
  const dataMin = Math.min(...allGlucoseValues);
  const dataMax = Math.max(...allGlucoseValues);
  // Pad and snap to nice round numbers
  const minGlucose = Math.max(0, Math.floor((dataMin - 10) / 10) * 10);
  const maxGlucose = Math.ceil((dataMax + 15) / 10) * 10;
  const minTime = Math.min(...timeValues);
  const maxTime = Math.max(...timeValues);
  const timeRange = maxTime - minTime;

  const xScale = (t) => padding.left + ((new Date(t).getTime() - minTime) / timeRange) * innerWidth;
  const yScale = (v) => chartHeight - padding.bottom - ((v - minGlucose) / (maxGlucose - minGlucose)) * innerHeight;

  // Build paths for each series — break on null so missing minutes don't connect
  const buildPath = (yKey) => {
    let started = false;
    const segments = [];
    validData.forEach(d => {
      const v = d[yKey];
      if (v == null) { started = false; return; }
      const x = xScale(d.time);
      const y = yScale(v);
      segments.push(`${started ? 'L' : 'M'} ${x} ${y}`);
      started = true;
    });
    return segments.join(' ');
  };
  const truePath = buildPath('glucose_true');
  const positivePath = buildPath('glucose_positive');
  const negativePath = buildPath('glucose_negative');

  // Marker downsampling — show one marker every Nth point so the markers are
  // visible (per-minute would be ~10000 dots; we want ~1 per ~6h block).
  const markerEveryN = Math.max(1, Math.floor(validData.length / 30));
  const markerPoints = validData.filter((_, i) => i % markerEveryN === 0);

  // Find incident periods — there can be more than one contiguous block (two
  // windows on different cohorts). Group consecutive incident_period=1 rows.
  const incidentBlocks = [];
  let inBlock = false;
  let blockStart = null;
  validData.forEach((d, idx) => {
    if (d.incident_period === 1 && !inBlock) {
      inBlock = true;
      blockStart = d.time;
    } else if (d.incident_period !== 1 && inBlock) {
      inBlock = false;
      incidentBlocks.push({ start: blockStart, end: validData[idx - 1].time });
    }
  });
  if (inBlock) incidentBlocks.push({ start: blockStart, end: validData[validData.length - 1].time });

  // Date tick formatting
  const formatDate = (t) => {
    const d = new Date(t);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  };
  const xAxisTicks = [];
  for (let i = 0; i <= 5; i++) {
    const tickTime = new Date(minTime + (timeRange / 5) * i);
    xAxisTicks.push({ x: xScale(tickTime), label: formatDate(tickTime) });
  }
  const yAxisTicks = [];
  const yStep = Math.max(10, Math.ceil((maxGlucose - minGlucose) / 5 / 10) * 10);
  for (let v = minGlucose; v <= maxGlucose; v += yStep) {
    yAxisTicks.push({ y: yScale(v), label: Math.round(v) });
  }

  // Hypo / hyper threshold lines (clinical reference)
  const hypoY = (minGlucose <= 70 && maxGlucose >= 70) ? yScale(70) : null;
  const hyperY = (minGlucose <= 180 && maxGlucose >= 180) ? yScale(180) : null;

  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col lg:flex-row gap-5">
      <div className="lg:w-48 lg:shrink-0">
        <h3 className="text-sm font-semibold text-slate-200 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Glucose Timeline: Actual vs Device Readings (per-cohort)
        </h3>
        <p className="text-xs text-slate-500 font-mono">
          Affected patients only. Green = true glucose, Red = positive-bias cohort device readings (+40 mg/dL at Day 2 incident), Blue = negative-bias cohort device readings (-40 mg/dL at Day 5 incident).
        </p>
      </div>
      <div className="flex-1 min-w-0">
        <svg viewBox={`0 0 ${chartWidth} ${chartHeight}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          {/* Incident period shadings — one rectangle per contiguous incident block */}
          {incidentBlocks.map((blk, i) => {
            const x1 = xScale(blk.start);
            const x2 = xScale(blk.end);
            return (
              <rect
                key={`incident-${i}`}
                x={x1}
                y={padding.top}
                width={Math.max(2, x2 - x1)}
                height={innerHeight}
                fill="rgb(248 113 113 / 0.1)"
                stroke="rgb(248 113 113 / 0.3)"
                strokeWidth="1"
                strokeDasharray="4 2"
              />
            );
          })}

          {/* Clinical threshold lines */}
          {hypoY != null && (
            <line x1={padding.left} y1={hypoY} x2={chartWidth - padding.right} y2={hypoY}
                  stroke="rgb(239 68 68)" strokeWidth="1" strokeDasharray="2 3" opacity="0.4" />
          )}
          {hyperY != null && (
            <line x1={padding.left} y1={hyperY} x2={chartWidth - padding.right} y2={hyperY}
                  stroke="rgb(251 146 60)" strokeWidth="1" strokeDasharray="2 3" opacity="0.4" />
          )}

          {/* Y axis */}
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={chartHeight - padding.bottom}
                stroke="rgb(71 85 105)" strokeWidth="1" />
          {yAxisTicks.map((tick, i) => (
            <g key={i}>
              <line x1={padding.left - 5} y1={tick.y} x2={padding.left} y2={tick.y}
                    stroke="rgb(71 85 105)" strokeWidth="1" />
              <text x={padding.left - 10} y={tick.y + 4} fill="rgb(148 163 184)"
                    fontSize="11" textAnchor="end" fontFamily="monospace">
                {tick.label}
              </text>
            </g>
          ))}
          <text x={20} y={chartHeight / 2} fill="rgb(148 163 184)" fontSize="12"
                textAnchor="middle" transform={`rotate(-90 20 ${chartHeight / 2})`} fontFamily="monospace">
            Glucose (mg/dL)
          </text>

          {/* X axis */}
          <line x1={padding.left} y1={chartHeight - padding.bottom}
                x2={chartWidth - padding.right} y2={chartHeight - padding.bottom}
                stroke="rgb(71 85 105)" strokeWidth="1" />
          {xAxisTicks.map((tick, i) => (
            <g key={i}>
              <line x1={tick.x} y1={chartHeight - padding.bottom}
                    x2={tick.x} y2={chartHeight - padding.bottom + 5}
                    stroke="rgb(71 85 105)" strokeWidth="1" />
              <text x={tick.x} y={chartHeight - padding.bottom + 20} fill="rgb(148 163 184)"
                    fontSize="11" textAnchor="middle" fontFamily="monospace">
                {tick.label}
              </text>
            </g>
          ))}
          <text x={chartWidth / 2} y={chartHeight - 10} fill="rgb(148 163 184)"
                fontSize="12" textAnchor="middle" fontFamily="monospace">
            Time
          </text>

          {/* Lines — thinner strokes than before for less bar-like appearance */}
          <path d={truePath} fill="none" stroke="rgb(169 169 169)" strokeWidth="1.5" opacity="0.95" />
          <path d={positivePath} fill="none" stroke="rgb(239 68 68)" strokeWidth="1.5" opacity="0.9" />
          <path d={negativePath} fill="none" stroke="rgb(59 130 246)" strokeWidth="1.5" opacity="0.9" />

          {/* Downsampled markers per series — circle (true), square (positive), triangle (negative) */}
          {markerPoints.map((d, i) => (
            <g key={`mk-${i}`}>
              {d.glucose_true != null && (
                <circle cx={xScale(d.time)} cy={yScale(d.glucose_true)} r="2.5"
                        fill="rgb(169 169 169)" stroke="rgb(169 169 169)" />
              )}
              {d.glucose_positive != null && (
                <rect x={xScale(d.time) - 2.5} y={yScale(d.glucose_positive) - 2.5} width="5" height="5"
                      fill="rgb(239 68 68)" stroke="rgb(239 68 68)" />
              )}
              {d.glucose_negative != null && (
                <polygon
                  points={`${xScale(d.time)},${yScale(d.glucose_negative) - 3} ${xScale(d.time) - 3},${yScale(d.glucose_negative) + 2.5} ${xScale(d.time) + 3},${yScale(d.glucose_negative) + 2.5}`}
                  fill="rgb(59 130 246)" stroke="rgb(59 130 246)"
                />
              )}
            </g>
          ))}

          {/* Legend */}
          <g transform={`translate(${padding.left + 20}, ${padding.top + 10})`}>
            <line x1="0" y1="0" x2="30" y2="0" stroke="rgb(169 169 169)" strokeWidth="2" />
            <circle cx="15" cy="0" r="2.5" fill="rgb(169 169 169)" />
            <text x="38" y="4" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              True glucose
            </text>

            <line x1="0" y1="18" x2="30" y2="18" stroke="rgb(239 68 68)" strokeWidth="2" />
            <rect x="12.5" y="15.5" width="5" height="5" fill="rgb(239 68 68)" />
            <text x="38" y="22" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Device — positive cohort (+40)
            </text>

            <line x1="0" y1="36" x2="30" y2="36" stroke="rgb(59 130 246)" strokeWidth="2" />
            <polygon points="15,33 12,38 18,38" fill="rgb(59 130 246)" />
            <text x="38" y="40" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Device — negative cohort (−40)
            </text>

            <rect x="0" y="50" width="30" height="10" fill="rgb(248 113 113 / 0.2)" stroke="rgb(248 113 113 / 0.5)" />
            <text x="38" y="59" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Incident windows
            </text>
          </g>
        </svg>
      </div>
    </div>
  );
}
