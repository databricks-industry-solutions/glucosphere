import React from 'react';

// "Preview / Roadmap" tiles for the fuller control-tower views (the pitch trio).
// Static previews — built on the same governed data; promoted to live in later phases.
// Explicit per-card classes (no interpolation) so Tailwind's purge keeps them.
export default function SplashGallery() {
  return (
    <section className="mb-12">
      <h2 className="text-lg font-semibold mb-2 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>Roadmap — fuller control-tower views</h2>
      <p className="text-xs text-slate-500 mb-5 font-mono">Preview of where this goes — built on the same governed data.</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-dashed border-cyan-500/30 rounded-lg p-5 bg-slate-900/30">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">PREVIEW · ① DETECT</span>
          <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Live Alert &amp; Triage</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Alerts stream in, acknowledge/assign, audit trail — real-time fleet ops (Lakebase-backed — wip).</p>
        </div>
        <div className="border border-dashed border-amber-500/30 rounded-lg p-5 bg-slate-900/30">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">PREVIEW · ② DIAGNOSE</span>
          <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Firmware Lifecycle Timeline</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Rollout → fault → fix across firmware versions — the recall sequence at a glance.</p>
        </div>
        <div className="border border-dashed border-rose-500/30 rounded-lg p-5 bg-slate-900/30">
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/30">PREVIEW · ③ ASSESS</span>
          <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Population Risk Stratification</h3>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Which cohorts were pushed into hypo/hyper exposure — the clinical blast radius.</p>
        </div>
      </div>
    </section>
  );
}
