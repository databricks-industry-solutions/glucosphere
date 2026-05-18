import React, { useState, useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { getIncidentImpactData, getGlucoseTimelineData, getIncidentSummary } from '../pages/GlucoseLanding/incidentQueries';

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
  const chartHeight = 400;
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
  
  const mae15Values = validData.map(d => d.mae_15m || 0);
  const mae30Values = validData.map(d => d.mae_30m || 0);
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
      const y = yScale(d.mae_15m || 0);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  const mae30Path = validData
    .map((d, i) => {
      const x = xScale(d.time);
      const y = yScale(d.mae_30m || 0);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  // Find incident period for highlighting
  const incidentData = validData.filter(d => d.incident_period === 1);
  const incidentStart = incidentData.length > 0 ? xScale(incidentData[0].time) : 0;
  const incidentEnd = incidentData.length > 0 ? xScale(incidentData[incidentData.length - 1].time) : 0;

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
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
      {/* Chart Title */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-slate-200 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Incident Impact: {summary?.incident_description || 'Device Calibration Issue'}
        </h3>
        <p className="text-xs text-slate-500 font-mono">
          Mean Absolute Error (MAE) Timeline - 7 Day Window
        </p>
      </div>

      {/* SVG Chart */}
      <div className="overflow-x-auto">
        <svg width={chartWidth} height={chartHeight} className="mx-auto">
          {/* Incident period highlight */}
          {incidentStart > 0 && incidentEnd > 0 && (
            <rect
              x={incidentStart}
              y={padding.top}
              width={incidentEnd - incidentStart}
              height={innerHeight}
              fill="rgb(248 113 113 / 0.1)"
              stroke="rgb(248 113 113 / 0.3)"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
          )}

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

          {/* MAE 30m line (orange) */}
          <path
            d={mae30Path}
            fill="none"
            stroke="rgb(251 146 60)"
            strokeWidth="2"
            opacity="0.9"
          />

          {/* MAE 15m line (blue) */}
          <path
            d={mae15Path}
            fill="none"
            stroke="rgb(59 130 246)"
            strokeWidth="2.5"
            opacity="0.9"
          />

          {/* Legend */}
          <g transform={`translate(${padding.left + 20}, ${padding.top + 10})`}>
            <line x1="0" y1="0" x2="30" y2="0" stroke="rgb(59 130 246)" strokeWidth="2.5" />
            <text x="35" y="4" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              MAE 15m
            </text>

            <line x1="0" y1="20" x2="30" y2="20" stroke="rgb(251 146 60)" strokeWidth="2" />
            <text x="35" y="24" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              MAE 30m
            </text>

            <rect x="0" y="35" width="30" height="10" fill="rgb(248 113 113 / 0.2)" stroke="rgb(248 113 113 / 0.5)" />
            <text x="35" y="44" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Incident Period (3h)
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
 * Glucose Timeline Chart - Shows actual vs device readings with bias
 * Similar to the bottom chart in the provided image
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
  const chartHeight = 400;
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
  
  // Bidirectional cohort split: device readings split by incident_direction.
  // glucose_device_positive/negative can be null at minutes with no data in
  // that cohort — filter those out for min/max + skip in path generation.
  const glucoseActualValues = validData.map(d => d.glucose_actual || 0);
  const glucoseDevicePositiveValues = validData.map(d => d.glucose_device_positive).filter(v => v != null);
  const glucoseDeviceNegativeValues = validData.map(d => d.glucose_device_negative).filter(v => v != null);
  const timeValues = validData.map(d => new Date(d.time).getTime());

  const allDeviceValues = [...glucoseDevicePositiveValues, ...glucoseDeviceNegativeValues];
  // Extra top headroom (1.20×) leaves room for the in-chart legend at top-left
  // so it doesn't overlap the data lines — particularly the negative-bias blue
  // line which can run near the top of the data range outside the incident window.
  const maxGlucose = Math.max(...glucoseActualValues, ...allDeviceValues) * 1.20;
  const minGlucose = Math.min(...glucoseActualValues, ...allDeviceValues) * 0.95;
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

  // Create path data for glucose lines
  const actualPath = validData
    .map((d, i) => {
      const x = xScale(d.time);
      const y = yScale(d.glucose_actual || 0);
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  // Build two device paths — positive bias (cohort over-reads, line shifts UP
  // during incident) and negative bias (cohort under-reads, line shifts DOWN).
  // Skip null points (no data for that cohort at that minute) by breaking the
  // path with an M command on the next valid point.
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
  const devicePositivePath = buildPath('glucose_device_positive');
  const deviceNegativePath = buildPath('glucose_device_negative');

  // Find incident period for highlighting
  const incidentData = validData.filter(d => d.incident_period === 1);
  const incidentStart = incidentData.length > 0 ? xScale(incidentData[0].time) : 0;
  const incidentEnd = incidentData.length > 0 ? xScale(incidentData[incidentData.length - 1].time) : 0;

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
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
      {/* Chart Title */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-slate-200 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
          Glucose Timeline: Actual vs Device Readings (±40 mg/dL Bidirectional Calibration Bias)
        </h3>
        <p className="text-xs text-slate-500 font-mono">
          Affected patient cohorts split by direction — half over-read (+40 mg/dL), half under-read (−40 mg/dL) during the incident window
        </p>
      </div>

      {/* SVG Chart */}
      <div className="overflow-x-auto">
        <svg width={chartWidth} height={chartHeight} className="mx-auto">
          {/* Incident period highlight */}
          {incidentStart > 0 && incidentEnd > 0 && (
            <rect
              x={incidentStart}
              y={padding.top}
              width={incidentEnd - incidentStart}
              height={innerHeight}
              fill="rgb(248 113 113 / 0.1)"
              stroke="rgb(248 113 113 / 0.3)"
              strokeWidth="1"
              strokeDasharray="4 2"
            />
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
            Glucose (mg/dL)
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

          {/* Device readings — positive-bias cohort (red, shifts UP during incident) */}
          <path
            d={devicePositivePath}
            fill="none"
            stroke="rgb(239 68 68)"
            strokeWidth="2"
            opacity="0.9"
          />

          {/* Device readings — negative-bias cohort (blue, shifts DOWN during incident) */}
          <path
            d={deviceNegativePath}
            fill="none"
            stroke="rgb(59 130 246)"
            strokeWidth="2"
            opacity="0.9"
          />

          {/* Actual glucose line (green/ground truth — same for all cohorts) */}
          <path
            d={actualPath}
            fill="none"
            stroke="rgb(34 197 94)"
            strokeWidth="2.5"
            opacity="0.9"
          />

          {/* Legend */}
          <g transform={`translate(${padding.left + 20}, ${padding.top + 10})`}>
            <line x1="0" y1="0" x2="40" y2="0" stroke="rgb(34 197 94)" strokeWidth="2.5" />
            <text x="45" y="4" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Actual glucose (ground truth)
            </text>

            <line x1="0" y1="20" x2="40" y2="20" stroke="rgb(239 68 68)" strokeWidth="2" />
            <text x="45" y="24" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Device — positive bias cohort (over-reads, +40 mg/dL)
            </text>

            <line x1="0" y1="40" x2="40" y2="40" stroke="rgb(59 130 246)" strokeWidth="2" />
            <text x="45" y="44" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Device — negative bias cohort (under-reads, −40 mg/dL)
            </text>

            <rect x="0" y="55" width="40" height="10" fill="rgb(248 113 113 / 0.2)" stroke="rgb(248 113 113 / 0.5)" />
            <text x="45" y="64" fill="rgb(148 163 184)" fontSize="11" fontFamily="monospace">
              Incident Period (3h)
            </text>
          </g>

        </svg>
      </div>
    </div>
  );
}
