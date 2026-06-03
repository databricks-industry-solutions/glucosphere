import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCalibrationDrift } from '../api/databricksSQL';

// Device Calibration Drift — signed device drift (mean observed − true) per device model,
// laid out by DAY so it aligns with the Firmware Lifecycle chart's day axis above: the fault
// columns line up under the chart's spikes. Over-read (+, red) vs under-read (−, blue), ≈0
// calibrated (slate). The per-model / per-direction triage detail of the incidents.
// Self-contained data fetch; `days` (the chart's day axis) is passed so the columns match.
//
// Canonical fleet model order (mirrors utils/additional_patient_info/_device_model_spec.py's
// DEVICE_MODELS) so clean models (Epsilon/Zeta — no incident) still render as calibrated rows.
const FLEET_MODELS = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta'];

export default function CalibrationDriftPanel({ days = [] }) {
  const navigate = useNavigate();
  const [drift, setDrift] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const data = await getCalibrationDrift();
        setDrift(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error('Failed to fetch calibration drift:', error);
        setDrift([]);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Diverging colour: under-read (negative) → blue, over-read (positive) → red, 0 → slate.
  const getDriftColor = (signed) => {
    const t = Math.min(Math.abs(signed) / 40, 1);
    if (t < 0.02) return 'rgb(30 41 59)';
    const lerp = (a, b) => Math.round(a + (b - a) * t);
    if (signed > 0) return `rgb(${lerp(30, 239)} ${lerp(41, 68)} ${lerp(59, 68)})`;   // → red-500
    return `rgb(${lerp(30, 59)} ${lerp(41, 130)} ${lerp(59, 246)})`;                   // → blue-500
  };

  const dayOf = (ts) => (ts ? String(ts).slice(0, 10) : '');          // window_start → YYYY-MM-DD
  const fmtDay = (d) => String(d).slice(5);                            // YYYY-MM-DD → MM-DD

  // Map drift to (model, incident-day) + per-day metadata (direction, device count).
  const byModelDay = {};
  const dayMeta = {};
  drift.forEach(d => {
    const day = dayOf(d.window_start);
    byModelDay[`${d.device_model}|${day}`] = d;
    const meta = dayMeta[day] || { direction: d.direction, devices: 0 };
    meta.direction = d.direction;
    meta.devices += d.devices;
    dayMeta[day] = meta;
  });

  // Columns = the chart's day axis (so they line up); fall back to the incident days alone.
  const cols = (days && days.length) ? days : [...new Set(drift.map(d => dayOf(d.window_start)))].sort();
  const dirWord = (dir) => (dir === 'positive' ? 'over' : dir === 'negative' ? 'under' : '');

  return (
    <div data-tour="calibration-drift" className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex flex-col">
      <div className="mb-4">
        <h3 className="text-sm font-medium text-slate-300 mb-1">Device Calibration Drift · by model × day</h3>
        <p className="text-xs text-slate-500 font-mono">mean(observed − true) mg/dL · ≈0 calibrated, ±40 faulted — aligned to the day axis above; which models drifted, when, and which way</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-500">Loading calibration drift...</div>
      ) : drift.length === 0 ? (
        <div className="flex items-center justify-center h-48 text-slate-500">No incident drift detected</div>
      ) : (
        <div className="flex-1 flex flex-col">
          <div className="space-y-1.5">
            {/* Day headers — match the chart's day axis; fault days carry the direction + count. */}
            <div className="flex items-end gap-1.5 h-12">
              <div className="w-[11%] shrink-0" />
              {cols.map(day => {
                const meta = dayMeta[day];
                return (
                  <div key={day} className="flex-1 text-center">
                    <div className="text-[13px] font-mono text-slate-400">{fmtDay(day)}</div>
                    {meta && (
                      <div className={`text-[11px] font-mono leading-tight ${meta.direction === 'positive' ? 'text-rose-300' : 'text-sky-300'}`}>
                        {dirWord(meta.direction)}-read<br />{meta.devices} dev
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {FLEET_MODELS.map(m => (
              <div key={m} className="flex items-center gap-1.5">
                <div className="w-[11%] shrink-0 text-sm text-slate-300 font-mono">{m}</div>
                {cols.map(day => {
                  const cell = byModelDay[`${m}|${day}`];
                  const signed = cell ? cell.signed_drift : 0;
                  const active = !!cell && Math.abs(signed) >= 0.5;
                  return (
                    <div
                      key={day}
                      onClick={active ? () => navigate(`/population-risk?model=${encodeURIComponent(m)}`) : undefined}
                      role={active ? 'button' : undefined}
                      title={active ? `See ${m}'s affected patients on Population Risk` : undefined}
                      className={`flex-1 h-9 rounded-md flex items-center justify-center group relative transition-all hover:ring-2 hover:ring-cyan-500 hover:ring-offset-2 hover:ring-offset-slate-900 ${active ? 'cursor-pointer' : 'cursor-default'}`}
                      style={{ backgroundColor: getDriftColor(signed) }}
                    >
                      {active && (
                        <span className="text-xs font-mono font-semibold text-white">
                          {signed > 0 ? '+' : ''}{signed.toFixed(0)}
                        </span>
                      )}
                      {cell && (
                        <div className="absolute inset-x-0 -top-9 flex justify-center opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                          <div className="bg-slate-950 border border-cyan-500 rounded px-2 py-1 text-[10px] font-mono whitespace-nowrap shadow-xl">
                            <span className="text-white font-bold">{signed > 0 ? '+' : ''}{signed.toFixed(1)} mg/dL</span>
                            <span className="text-slate-400"> · {cell.devices} dev · {fmtDay(day)}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-800/70 text-[12px] font-mono text-slate-500">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="inline-block w-4 h-3 rounded-sm" style={{ backgroundColor: getDriftColor(-40) }} />
              <span>−40 under-read</span>
              <span className="inline-block w-4 h-3 rounded-sm ml-2" style={{ backgroundColor: getDriftColor(0) }} />
              <span>0 calibrated</span>
              <span className="inline-block w-4 h-3 rounded-sm ml-2" style={{ backgroundColor: getDriftColor(40) }} />
              <span>+40 over-read</span>
            </div>
            <div className="mt-1.5 text-slate-600">Window 1 (over-read) on FW 4.0 · Window 2 (under-read) on FW 4.0.3 · Epsilon / Zeta clean — no incident</div>
          </div>
        </div>
      )}
    </div>
  );
}
