import React from 'react';
import { Link } from 'react-router-dom';

// The pitch trio (detect · diagnose · assess). ② Diagnose + ③ Assess are now
// LIVE views (link out); ① Detect (Live Alert & Triage) stays a preview — it's
// the Lakebase-backed one (wip). Pure card grid; framing supplied by RoadmapPage.
// Explicit per-card classes (no interpolation) so Tailwind's purge keeps them.
export default function SplashGallery() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* ① Detect — preview (Lakebase-backed, wip) */}
      <div className="border border-dashed border-cyan-500/30 rounded-lg p-5 bg-slate-900/30">
        <span className="text-xs font-mono px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">PREVIEW · ① DETECT</span>
        <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Live Alert &amp; Triage</h3>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Alerts stream in, acknowledge/assign, audit trail — real-time fleet ops (Lakebase-backed — wip).</p>
      </div>

      {/* ② Diagnose — LIVE */}
      <Link to="/firmware-lifecycle" className="group border border-amber-500/40 rounded-lg p-5 bg-slate-900/30 hover:bg-slate-900/60 hover:border-amber-400/70 transition-colors block">
        <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-500/15 text-amber-300 border border-amber-500/40">● LIVE · ② DIAGNOSE</span>
        <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Firmware Lifecycle Timeline</h3>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Out-of-range rate by firmware version over time — the rollout → fault → fix read.</p>
        <span className="text-xs text-amber-300 font-mono mt-3 inline-block group-hover:translate-x-0.5 transition-transform">Open view →</span>
      </Link>

      {/* ③ Assess — LIVE */}
      <Link to="/population-risk" className="group border border-rose-500/40 rounded-lg p-5 bg-slate-900/30 hover:bg-slate-900/60 hover:border-rose-400/70 transition-colors block">
        <span className="text-xs font-mono px-2.5 py-1 rounded bg-rose-500/15 text-rose-300 border border-rose-500/40">● LIVE · ③ ASSESS</span>
        <h3 className="text-base font-semibold text-slate-200 mt-3" style={{ fontFamily: 'Georgia, serif' }}>Population Risk Stratification</h3>
        <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">Which cohorts were pushed into hypo/hyper exposure — the clinical blast radius.</p>
        <span className="text-xs text-rose-300 font-mono mt-3 inline-block group-hover:translate-x-0.5 transition-transform">Open view →</span>
      </Link>
    </div>
  );
}
