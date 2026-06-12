import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import SplashGallery from '../components/SplashGallery';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';

// "Where this goes" vision page — the pitch trio (detect · diagnose · assess).
// ② Diagnose + ③ Assess are live views; ① Live Alert & Triage is live on
// Lakebase-enabled deployments (preview elsewhere) — the intro copy adapts.
export default function RoadmapPage() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const lakebaseConfigured = useLakebaseConfigured();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={goBack} className="text-slate-500 hover:text-slate-300" aria-label="Back">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <BrandMark className="w-7 h-7 text-cyan-400" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Detect · Diagnose · Assess{lakebaseConfigured ? ' → Act' : ''}</h1>
              <p className="text-xs text-slate-500 font-mono">How it comes together — the control-tower arc, plus what's next</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-2 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Fuller control-tower views</h2>
          {lakebaseConfigured ? (
            <p className="text-sm text-slate-400 leading-relaxed">
              The <span className="text-slate-200">detect → diagnose → assess</span> arc is <span className="text-emerald-300">live end-to-end</span> —
              including the <span className="text-cyan-400 font-medium">Lakebase-backed Alert Triage queue</span> (the act:
              acknowledge / assign / resolve with an audit trail, the app's transactional write path). The cards below open
              the live views — all on the same governed Databricks data.
            </p>
          ) : (
            <p className="text-sm text-slate-400 leading-relaxed">
              Today the app realizes <span className="text-cyan-400 font-medium">① Detect</span> — the fleet
              and incident overview on the home page — plus the live <span className="text-slate-200">② Diagnose</span> and
              <span className="text-slate-200"> ③ Assess</span> views below. The Lakebase-backed Live Alert &amp; Triage queue
              ships on deployments that enable it — all built on the same governed Databricks data.
            </p>
          )}
        </section>
        <div data-tour="roadmap-views"><SplashGallery /></div>

        {/* Planned enhancements — the textual backlog the in-app "on the roadmap"
            references (e.g. Coach forecast) point to. Kept honest: real logged items. */}
        {/* De-emphasized: collapsed disclosure so the backlog is present + honest
            but doesn't compete with the live preview cards above. */}
        <details className="bg-slate-900/40 border border-slate-800/60 rounded-lg px-6 py-4">
          <summary className="cursor-pointer select-none text-sm font-mono text-slate-400 hover:text-slate-300">
            Planned next — logged enhancements (expand)
          </summary>
          <ul className="space-y-2 text-sm text-slate-500 mt-4">
            <li>
              <span className="text-slate-400">60-minute glucose forecast</span> — extend the near-term model
              (today <span className="font-mono">15 / 30-min</span>) to a longer horizon for the Diabetes Coach.
            </li>
            <li>
              <span className="text-slate-400">Live 5-minute device-accuracy monitoring</span> — continuous rolling-MAE
              detection so the "① Detect" signal is real-time rather than a batch snapshot.
            </li>
            <li>
              <span className="text-slate-400">Real-time CGM streaming</span> — sub-minute dashboard updates as new
              readings arrive, in place of periodic refreshes.
            </li>
            <li>
              <span className="text-slate-400">Monitoring-created alerts</span> — the detection layer writes the triage
              queue itself (forecast / danger-band crossings → new alerts), replacing the demo's seed step; the queue's
              "Last 3h" live-risk view is the read-only precursor.
            </li>
            <li>
              <span className="text-slate-400">Triage analytics in the lakehouse</span> — register the Lakebase database
              as a Unity Catalog catalog so the alert + audit state is queryable from the warehouse (MTTR, open-vs-resolved
              burn-down, outcomes by firmware) — OLTP state flowing back into analytics.
            </li>
            <li>
              <span className="text-slate-400">Incident playback</span> — replay an incident window as if live: alerts
              appear progressively, dashboards animate through the timeline — the booth demo in motion rather than
              retrospective.
            </li>
          </ul>
        </details>
      </main>
    </div>
  );
}
