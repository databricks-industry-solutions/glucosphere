import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import PopulationRiskChart from '../components/PopulationRiskChart';
import { getPopulationRisk } from '../api/databricksSQL';

// ③ Assess — which patient cohorts a device fault pushed into hypo/hyper exposure.
export default function PopulationRiskPage() {
  const navigate = useNavigate();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { setLoading(true); setData(await getPopulationRisk()); }
      catch (e) { console.error('Population risk fetch failed:', e); setData([]); }
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
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>Population Risk</h1>
              <p className="text-xs text-slate-500 font-mono">③ Assess — the clinical blast radius</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30">③ ASSESS</span>
          <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>Hypo / hyper exposure by cohort</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The clinical question: <span className="text-slate-200">who got pushed into danger</span>. Share of device-reported readings in the
            <span className="text-blue-300"> hypoglycemic (&lt;70 mg/dL)</span> and <span className="text-rose-300">hyperglycemic (&gt;180 mg/dL)</span> ranges,
            per cohort. The over-reading cohort is driven into apparent <span className="text-rose-300">highs</span>, the under-reading cohort into apparent
            <span className="text-blue-300"> lows</span> — both vs the unaffected <span className="text-slate-200">baseline</span>. That gap is the blast radius.
          </p>
        </section>

        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          {loading
            ? <div className="flex items-center justify-center h-64 text-slate-500">Loading population risk…</div>
            : <PopulationRiskChart data={data} />}
        </section>
      </main>
    </div>
  );
}
