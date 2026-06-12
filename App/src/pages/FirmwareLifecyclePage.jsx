import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, AlertTriangle, ChevronRight } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import FirmwareLifecycleChart from '../components/FirmwareLifecycleChart';
import CalibrationDriftPanel from '../components/CalibrationDriftPanel';
import { getFirmwareLifecycle, getFirmwareImpact } from '../api/databricksSQL';
import { useGoBack } from '../hooks/useGoBack';
import { useLakebaseConfigured } from '../hooks/useLakebase';

// ② Diagnose — trace a fleet-wide accuracy spike to the device firmware at fault,
// then hand off to ACT: who was faulted on that firmware + flag it for rollback.
export default function FirmwareLifecyclePage() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const lakebaseConfigured = useLakebaseConfigured();
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
  // getFirmwareLifecycle now reports the in-incident MAE, so the faulty firmware peaks
  // at ~40 mg/dL while clean firmwares sit at ~0 — threshold 5 separates them with wide
  // margin on both the real and synthetic baselines (verified).
  const peakByFw = {};
  data.forEach((d) => {
    if (!peakByFw[d.firmwareVersion] || d.mae > peakByFw[d.firmwareVersion].peak) {
      peakByFw[d.firmwareVersion] = { peak: d.mae, day: d.day };
    }
  });
  const ranked = Object.entries(peakByFw).sort((a, b) => b[1].peak - a[1].peak);
  // EVERY firmware whose peak clears baseline is a culprit — there can be more than one
  // (e.g. 4.0 over-read + its 4.0.3 hotfix under-read), so we flag them all, not just the
  // single highest. Each carries its own recall count (patients faulted ON that firmware,
  // in-incident — NOT everyone who ran it; verified: 600 ran FW 4.0 but only 300 faulted).
  const faulties = ranked
    .filter(([, v]) => v.peak >= 5)
    .map(([fw, v]) => ({ fw, peak: v.peak, day: v.day, impact: impact.find((f) => f.firmwareVersion === fw) || null }));
  const hasFault = faulties.length > 0;
  const faultyFws = faulties.map((f) => f.fw);
  const faultLabel = faulties.length === 1
    ? `FW ${faulties[0].fw} is the faulty rollout`
    : `FW ${faultyFws.join(' and FW ')} are the faulty rollouts`;

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
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Firmware Lifecycle</h1>
              <p className="text-xs text-slate-500 font-mono">② Diagnose — trace the spike to the firmware at fault</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">② DIAGNOSE</span>
          <h2 className="text-lg font-semibold mt-3 mb-2 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Calibration error (MAE) by firmware version</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Once the fleet-wide monitor flags an accuracy spike, the next question is <span className="text-slate-200">which firmware</span>.
            Each line is the mean device error — <span className="font-mono">|observed − true| glucose</span> — per firmware version per day,
            measured over the <span className="text-slate-300">affected readings</span> so the fault shows at full magnitude.
            Clean firmwares sit near <span className="text-emerald-300">0 mg/dL</span>; a <span className="text-rose-300">faulty rollout</span> spikes
            to <span className="text-rose-300 font-mono">~40 mg/dL</span> during its incident, pointing at the exact version to roll back or patch.
          </p>
          <p className="text-xs text-slate-500 leading-relaxed mt-2">
            Scoped to the in-incident readings (not a whole-week average, which would dilute even a 12h event to a few mg/dL) — the same <span className="font-mono">±40 mg/dL</span> fault the Device Support dashboard's <span className="text-slate-400">Device Error by Firmware × Day</span> heatmap shows.
          </p>
        </section>

        <section data-tour="firmware-chart" className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          {loading
            ? <div className="flex items-center justify-center h-64 text-slate-500">Loading firmware lifecycle…</div>
            : <FirmwareLifecycleChart data={data} faultyFws={faultyFws} />}
        </section>

        {/* Per-model / per-direction triage detail — which device models drifted, and which
            way (over- vs under-read), in each incident window. The companion to the chart's
            magnitude-over-time view; relocated here from the Device Support overview, which
            now shows the consolidated firmware × day heatmap with direction glyphs. */}
        <section>
          {/* Gated on parent `loading` (same pattern as the firmware chart above) so the
              panel mounts only once `data` → the 7-day axis is ready. Without this, it mounts
              with days=[] during the parent fetch and briefly renders its incident-only
              2-column fallback (06-01 red / 06-04 blue) before the full 7-day grid. */}
          {!loading && <CalibrationDriftPanel days={[...new Set(data.map(d => d.day))].sort()} />}
        </section>

        {/* → ACT — name every culprit firmware + its recall fleet + the rollback handoff */}
        {!loading && hasFault && (
          <section data-tour="firmware-act" className="bg-rose-500/5 border border-rose-500/30 rounded-lg p-6">
            <div className="flex items-start gap-3">
              <div className="w-9 h-9 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center justify-center shrink-0">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
              </div>
              <div className="min-w-0 flex-1">
                <span className="text-xs font-mono px-2.5 py-1 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/30">→ ACT</span>
                {/* headline + the clinical blast-radius hand-off share one row */}
                <div className="flex items-start justify-between gap-4 mt-2">
                  <h2 className="text-lg font-semibold text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                    {faultLabel}
                  </h2>
                  <button onClick={() => navigate('/population-risk')} className="inline-flex items-center gap-0.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 shrink-0 mt-1">
                    See blast radius on Population Risk <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
                {/* one row per culprit: detail (left) + its OWN Flag-for-rollback button (right),
                    so the action sits next to the firmware it acts on. */}
                <div className="mt-2 space-y-2">
                  {faulties.map((f) => (
                    <div key={f.fw} className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="text-sm text-slate-400 leading-relaxed min-w-0">
                        <span className="text-rose-300 font-mono">FW {f.fw}</span> — peak device error <span className="text-slate-500">(MAE)</span>{' '}
                        <span className="text-rose-300 font-mono">{f.peak} mg/dL</span> on{' '}
                        <span className="font-mono">{(f.day || '').slice(5)}</span> vs <span className="text-emerald-300">~0</span> baseline
                        {f.impact && (
                          <> · <span className="text-slate-200 font-mono">{f.impact.affectedPatients.toLocaleString()}</span> patients <span className="text-slate-500">(1 device each)</span> faulted — recall / outreach list</>
                        )}
                      </div>
                      {/* Lakebase-configured targets land in the REAL triage queue;
                          others keep the wip preview pointing at the roadmap. */}
                      {/* Carries THIS firmware into the queue (?fw=…) so the operator
                          lands on exactly the rollback cohort. */}
                      <button
                        onClick={() => navigate(lakebaseConfigured ? `/triage?fw=${encodeURIComponent(f.fw)}` : '/roadmap')}
                        title={lakebaseConfigured ? `Open the triage queue filtered to FW ${f.fw}. "Live Alert" = the workflow — alerts are batch-derived today; streaming ingestion would raise them in real time (Roadmap).` : undefined}
                        className="text-xs font-mono px-3 py-2 rounded-lg border border-cyan-500/40 text-cyan-300 hover:bg-cyan-500/10 transition-colors shrink-0"
                      >
                        → Flag FW {f.fw} for rollback {lakebaseConfigured ? <span className="text-emerald-300">(Live Alert)</span> : <span className="text-slate-500">(Live Alert · wip)</span>}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
