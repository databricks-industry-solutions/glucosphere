import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import FirmwareLifecycleChart from '../components/FirmwareLifecycleChart';
import { getFirmwareLifecycle } from '../api/databricksSQL';

// ② Diagnose — trace a fleet-wide accuracy spike to the device firmware at fault.
export default function FirmwareLifecyclePage() {
  const navigate = useNavigate();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { setLoading(true); setData(await getFirmwareLifecycle()); }
      catch (e) { console.error('Firmware lifecycle fetch failed:', e); setData([]); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-4">
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

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">② DIAGNOSE</span>
          <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>Out-of-range rate by firmware version</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Once the fleet-wide monitor flags an accuracy spike, the next question is <span className="text-slate-200">which firmware</span>.
            Each line is the share of device readings out of range (&lt;70 or &gt;180 mg/dL) per firmware version over the recent window —
            the <span className="text-rose-300">faulty version</span> climbs while clean versions stay flat, pointing at the rollout to roll back or patch.
          </p>
        </section>

        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          {loading
            ? <div className="flex items-center justify-center h-64 text-slate-500">Loading firmware lifecycle…</div>
            : <FirmwareLifecycleChart data={data} />}
        </section>
      </main>
    </div>
  );
}
