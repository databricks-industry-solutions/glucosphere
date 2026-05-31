import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, ChevronRight } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import FirmwareLifecycleChart from '../components/FirmwareLifecycleChart';
import { getFirmwareLifecycle, getFirmwareImpact } from '../api/databricksSQL';

// ② Diagnose — trace a fleet-wide accuracy spike to the device firmware at fault,
// then hand off to ACT: who was faulted on that firmware + flag it for rollback.
export default function FirmwareLifecyclePage() {
  const navigate = useNavigate();
  const [data, setData] = useState([]);
  const [impact, setImpact] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        const [lifecycle, impactData] = await Promise.all([getFirmwareLifecycle(), getFirmwareImpact()]);
        setData(lifecycle);
        setImpact(impactData);
      } catch (e) { console.error('Firmware lifecycle fetch failed:', e); setData([]); setImpact([]); }
      finally { setLoading(false); }
    })();
  }, []);

  // Faulty firmware = the version with the highest peak device error (MAE), derived
  // from the lifecycle data. Only treated as a fault when the peak clears baseline.
  const peakByFw = {};
  data.forEach((d) => {
    if (!peakByFw[d.firmwareVersion] || d.mae > peakByFw[d.firmwareVersion].peak) {
      peakByFw[d.firmwareVersion] = { peak: d.mae, day: d.day };
    }
  });
  const ranked = Object.entries(peakByFw).sort((a, b) => b[1].peak - a[1].peak);
  const faulty = ranked.length && ranked[0][1].peak >= 5
    ? { fw: ranked[0][0], peak: ranked[0][1].peak, day: ranked[0][1].day }
    : null;
  // The recall/outreach number = patients actually faulted ON this firmware (in-incident),
  // NOT everyone who ran it (verified: 600 ran FW 4.0 but only 300 were faulted on it).
  const faultyImpact = faulty ? impact.find((f) => f.firmwareVersion === faulty.fw) : null;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={() => navigate('/roadmap')} className="text-slate-500 hover:text-slate-300" aria-label="Back to roadmap">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <BrandMark className="w-7 h-7 text-cyan-400" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>Firmware Lifecycle</h1>
              <p className="text-xs text-slate-500 font-mono">② Diagnose — trace the spike to the firmware at fault</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">② DIAGNOSE</span>
          <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>Calibration error (MAE) by firmware version</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Once the fleet-wide monitor flags an accuracy spike, the next question is <span className="text-slate-200">which firmware</span>.
            Each line is the mean device error — <span className="font-mono">|observed − true| glucose</span> — per firmware version per day.
            Clean firmwares sit near <span className="text-emerald-300">0 mg/dL</span>; the <span className="text-rose-300">faulty version</span> spikes
            during the incident, pointing at the exact rollout to roll back or patch.
          </p>
        </section>

        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          {loading
            ? <div className="flex items-center justify-center h-64 text-slate-500">Loading firmware lifecycle…</div>
            : <FirmwareLifecycleChart data={data} />}
        </section>

        {/* → ACT — name the culprit firmware + its recall fleet + the rollback handoff */}
        {!loading && faulty && (
          <section className="bg-rose-500/5 border border-rose-500/30 rounded-lg p-6">
            <div className="flex items-start justify-between gap-4 flex-wrap">
              <div className="flex items-start gap-3">
                <div className="w-9 h-9 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0">
                  <AlertTriangle className="w-5 h-5 text-rose-400" />
                </div>
                <div>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">→ ACT</span>
                  <h2 className="text-lg font-semibold mt-2 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>
                    FW {faulty.fw} is the faulty rollout
                  </h2>
                  <p className="text-sm text-slate-400 leading-relaxed mt-1">
                    Peak device error <span className="text-rose-300 font-mono">{faulty.peak} mg/dL</span> on{' '}
                    <span className="font-mono">{(faulty.day || '').slice(5)}</span> vs <span className="text-emerald-300">~0</span> baseline.
                    {faultyImpact && (
                      <> <span className="text-slate-200 font-mono">{faultyImpact.affectedDevices.toLocaleString()}</span> devices ·{' '}
                      <span className="text-slate-200 font-mono">{faultyImpact.affectedPatients.toLocaleString()}</span> patients were faulted on this firmware — the recall / outreach list.</>
                    )}
                  </p>
                </div>
              </div>
              <button
                onClick={() => navigate('/roadmap')}
                className="text-xs font-mono px-3 py-2 rounded-lg border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 transition-colors shrink-0"
              >
                → Flag FW {faulty.fw} for rollback <span className="text-slate-500">(Live Alert · wip)</span>
              </button>
            </div>
            <div className="mt-4 pt-4 border-t border-slate-800/60 flex items-center gap-1 text-xs font-mono text-slate-500">
              See the clinical blast radius of this fault on
              <button onClick={() => navigate('/population-risk')} className="inline-flex items-center gap-0.5 text-cyan-400 hover:text-cyan-300 ml-1">
                Population Risk <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
