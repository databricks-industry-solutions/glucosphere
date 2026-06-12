import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  HeartHandshake, Wrench, BookOpen, ArrowLeft, ArrowRight, Github, ExternalLink,
  Layers, Database, FlaskConical, Server, Sparkles, Boxes, MessagesSquare, HardDrive, Telescope,
} from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { useGoBack } from '../hooks/useGoBack';
import { getConfig } from '../api/config';

const REPO_URL = 'https://github.com/databricks-industry-solutions/glucosphere';
const ARCH_URL = 'https://github.com/databricks-industry-solutions/glucosphere/tree/main#architecture';   // jumps to the README ## Architecture section (architecture.png)

// Official Databricks resource pages for the intro prose (all verified 200, 2026-06-02).
const DBX = {
  home: 'https://www.databricks.com/',
  lakehouse: 'https://www.databricks.com/product/data-lakehouse',
  agentBricks: 'https://www.databricks.com/product/artificial-intelligence/agent-bricks',
};

const ROLE_CARDS = [
  { icon: Wrench, title: 'Device Support', sub: 'Biomedical Engineering', route: '/device-support' },
  { icon: HeartHandshake, title: 'Diabetes Coach', sub: 'Diabetes Coaching', route: '/diabetes-coach' },
  { icon: BookOpen, title: 'Metrics Explained', sub: 'How every metric is computed', route: '/metrics-explained' },
  { icon: Telescope, title: 'The Full Loop', sub: 'Detect · Diagnose · Assess — how it comes together', route: '/roadmap' },
];

// "Under the hood" platform stack, grouped as a Data → ML/AI → Agentic pipeline flow.
// Declarative so a future layer (streaming, …) is a one-line add — the Lakebase tile
// below landed exactly that way (flag-gated via `flagKey`). `hrefKey`
// resolves to a live workspace deep-link built from /api/config at render time
// (see linksFromConfig); naming matches the repo — no "Mosaic".
// Icons are lucide monochrome line-icons (consistent with the rest of the app) as a
// PLACEHOLDER — follow-up is to swap in monochrome Databricks product glyphs (DLT /
// Unity Catalog / MLflow / Model Serving / Agent Bricks) once the SVGs are sourced.
const STAGES = [
  {
    key: 'data', label: 'Data', items: [
      { icon: Layers, name: 'Delta Live Tables', blurb: 'silver → gold medallion', hrefKey: 'pipeline' },
      { icon: Database, name: 'Unity Catalog', blurb: 'governed data + models', hrefKey: 'uc' },
      // Shown only on deployments with the Lakebase binding (lakebase_configured) —
      // the Alert Triage queue's OLTP store, the app's transactional write path.
      { icon: HardDrive, name: 'Lakebase', blurb: 'OLTP alert-triage state (managed Postgres)', hrefKey: 'lakebase', flagKey: 'lakebase' },
    ],
  },
  {
    key: 'ml', label: 'ML / AI', items: [
      { icon: FlaskConical, name: 'MLflow', blurb: 'experiments + model registry', hrefKey: 'mlflow' },
      { icon: Server, name: 'Model Serving', blurb: '15-/30-min glucose forecast', hrefKey: 'serving' },
    ],
  },
  {
    key: 'agentic', label: 'Agentic', items: [
      // Agent Bricks = the managed agent builders (Knowledge Assistant + Multi-Agent
      // Supervisor). AI/BI Genie is a SEPARATE Databricks capability (NL-to-SQL over
      // UC tables) that the Multi-Agent Supervisor orchestrates — NOT part of Agent
      // Bricks (per the Agent Bricks product page, Genie is listed under "Related
      // Products"). So they're two distinct nodes, not one.
      {
        icon: Sparkles, name: 'Agent Bricks', subLinks: [
          { label: 'Knowledge Assistant', hrefKey: 'ka' },
          { label: 'Multi-Agent Supervisor', hrefKey: 'mas' },
        ],
      },
      { icon: MessagesSquare, name: 'AI/BI Genie', blurb: 'NL-to-SQL over UC tables · orchestrated by the MAS', hrefKey: 'genie' },
    ],
  },
];

// Build the live workspace deep-links from runtime config. Each falls back to a
// workspace listing page when the specific id isn't available (e.g. PIPELINE_ID
// empty pre-render), so the panel is always actionable for a logged-in SA.
function linksFromConfig(cfg) {
  const wh = (cfg && cfg.workspace_host) || '';
  const enc = (s) => encodeURIComponent(s || '');
  return {
    pipeline: cfg?.pipeline_url || (wh ? `${wh}/pipelines` : ''),
    uc: wh && cfg?.catalog && cfg?.schema ? `${wh}/explore/data/${enc(cfg.catalog)}/${enc(cfg.schema)}` : (wh ? `${wh}/explore/data` : ''),
    mlflow: wh ? `${wh}/ml/experiments` : '',
    // deep-link straight to the forecast endpoint (the list page has no URL filter);
    // fall back to the full endpoints listing if the name wasn't discovered.
    serving: cfg?.forecast_endpoint_url || (wh ? `${wh}/ml/endpoints` : ''),
    lakebase: wh ? `${wh}/lakebase` : '',
    genie: wh && cfg?.genie_space_id ? `${wh}/genie/rooms/${cfg.genie_space_id}` : '',
    ka: cfg?.ka_endpoint_url || (wh ? `${wh}/ml/endpoints` : ''),
    mas: cfg?.mas_endpoint_url || (wh ? `${wh}/ml/endpoints` : ''),
    jobs: cfg?.setup_job_url || (wh ? `${wh}/jobs` : ''),
  };
}

function StackNode({ icon: Icon, name, blurb, href, subLinks, resolve }) {
  const cls = 'block rounded-md border border-slate-800 bg-slate-950/40 px-3 py-2 transition-colors';

  // Multi-link node (e.g. Agent Bricks → Knowledge Assistant · Multi-Agent Supervisor):
  // the card itself isn't a link; each service is its own small deep-link, clickable individually.
  if (subLinks) {
    return (
      <div className={cls}>
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-cyan-400 shrink-0" strokeWidth={2.25} />
          <span className="text-sm font-medium text-slate-100">{name}</span>
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 pl-6">
          {subLinks.map((s) => {
            const url = resolve(s.hrefKey);
            return url
              ? <a key={s.label} href={url} target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-0.5 text-[11px] text-slate-400 hover:text-cyan-300">
                  {s.label} <ExternalLink className="w-2.5 h-2.5" />
                </a>
              : <span key={s.label} className="text-[11px] text-slate-500">{s.label}</span>;
          })}
        </div>
      </div>
    );
  }

  const inner = (
    <>
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-cyan-400 shrink-0" strokeWidth={2.25} />
        <span className="text-sm font-medium text-slate-100">{name}</span>
        {href && <ExternalLink className="w-3 h-3 text-slate-500 group-hover:text-cyan-300 ml-auto shrink-0" />}
      </div>
      <p className="text-[11px] text-slate-500 leading-snug mt-0.5 pl-6">{blurb}</p>
    </>
  );
  return href
    ? <a href={href} target="_blank" rel="noopener noreferrer" className={`${cls} group hover:border-cyan-500/40`}>{inner}</a>
    : <div className={cls}>{inner}</div>;
}

export default function AboutPage() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const [links, setLinks] = useState(() => linksFromConfig(null));
  const [lakebaseOn, setLakebaseOn] = useState(false);  // gates the Lakebase stack tile

  useEffect(() => {
    getConfig().then((cfg) => {
      setLinks(linksFromConfig(cfg));
      setLakebaseOn(Boolean(cfg.lakebase_configured));
    }).catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-3 flex items-center gap-4">
          <button onClick={goBack} className="text-slate-500 hover:text-slate-300 shrink-0" aria-label="Back">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3 min-w-0">
            <BrandMark className="w-7 h-7 text-cyan-400 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>About Glucosphere</h1>
              <p className="text-xs text-slate-500 font-mono truncate">CGM Stream Intelligence — fleet control tower · detect · diagnose · act</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-5 space-y-4">
        {/* What this is + the logo — combined into one compact section. The BrandMark
            sits beside the paragraph that actually describes it (the logo), not up by the
            heading. Kept vertically tight so the "Under the hood" panel below has room. */}
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-base font-semibold text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>What this is</h2>
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" title="View on GitHub"
              className="flex items-center gap-2 px-2.5 py-1 border border-slate-700 rounded-lg hover:bg-slate-800/60 transition-colors shrink-0">
              <Github className="w-3.5 h-3.5 text-slate-400" />
              <span className="text-xs font-mono text-slate-400">industry-solutions/glucosphere</span>
            </a>
          </div>
          <p className="text-sm text-slate-400 leading-relaxed mt-1.5">
            <span className="text-cyan-400 font-medium">Glucosphere</span> is a{' '}
            <button onClick={() => navigate('/metrics-explained#me-why-monitoring')}
              className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2"
              title="Why this monitoring stack matters — the platform-value overview">control tower</button> for a
            continuous-glucose-monitor (CGM) device fleet: detect device-accuracy drift, diagnose it to the
            firmware at fault, and{' '}
            <button onClick={() => navigate('/metrics-explained#me-firmware-fault-impact')}
              className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2"
              title="Clinical burden vs device-fault impact — how the patient-risk numbers are derived">assess the patient-risk impact</button>. <span className="text-slate-500">(The live
            monitoring feed is nicknamed "GlucoStream" — the continuous stream of device readings the platform
            watches.)</span>
          </p>
          {/* logo row — mark adjacent to the text that explains it */}
          <div className="flex items-center gap-4 mt-2.5">
            <BrandMark className="w-10 h-10 text-cyan-400 shrink-0" />
            <p className="text-xs text-slate-500 leading-relaxed">
              <span className="text-slate-400 font-medium">The logo</span> is the <span className="text-slate-300">glucose ring</span> —
              the six-membered pyranose form of the glucose molecule (5 carbons + 1 oxygen) a CGM actually measures —
              drawn Haworth-style with its <span className="text-slate-300">CH₂OH and hydroxyl branches</span>, plus a
              <span className="text-cyan-400 font-medium"> live-reading sensor node</span> for the continuous monitoring.
            </p>
          </div>
        </section>

        {/* Under the hood — the platform plumbing as a Data → ML/AI → Agentic pipeline flow,
            each node deep-linking into the deploying workspace. */}
        <section data-tour="about-hood" className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-1 text-slate-200" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
            Under the hood — powered by{' '}
            <a href={DBX.home} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2">Databricks</a>
          </h2>
          <p className="text-sm text-slate-400 leading-relaxed mb-4">
            One{' '}
            <a href={DBX.lakehouse} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2">Lakehouse</a>{' '}
            pipeline, from raw device telemetry to{' '}
            <a href={DBX.agentBricks} target="_blank" rel="noopener noreferrer" className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2">agentic</a>{' '}
            assistance.
          </p>

          <div className="flex flex-col md:flex-row md:items-stretch gap-3">
            {STAGES.map((stage, si) => (
              <React.Fragment key={stage.key}>
                <div className="flex-1 rounded-lg border border-slate-800/80 bg-slate-900/40 p-3">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-500 mb-2">{stage.label}</div>
                  <div className="space-y-2">
                    {stage.items.filter((it) => !it.flagKey || lakebaseOn).map((it) => (
                      <StackNode key={it.name} icon={it.icon} name={it.name} blurb={it.blurb}
                        href={it.hrefKey ? links[it.hrefKey] : undefined}
                        subLinks={it.subLinks} resolve={(k) => links[k]} />
                    ))}
                  </div>
                </div>
                {si < STAGES.length - 1 && (
                  <div className="flex items-center justify-center shrink-0" aria-hidden="true">
                    <ArrowRight className="w-4 h-4 text-slate-600 rotate-90 md:rotate-0" />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>

          <div className="mt-3 pt-2.5 border-t border-slate-800/70 flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="flex items-center gap-1.5 text-xs text-slate-500">
              <Boxes className="w-3.5 h-3.5 text-slate-500" />
              All orchestrated by one Databricks Asset Bundle
            </span>
            {links.jobs && (
              <a href={links.jobs} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 text-xs font-mono text-cyan-400 hover:text-cyan-300">
                Jobs <ExternalLink className="w-3 h-3" />
              </a>
            )}
            <a href={ARCH_URL} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 text-xs font-mono text-cyan-400 hover:text-cyan-300 md:ml-auto">
              Full architecture <ExternalLink className="w-3 h-3" />
            </a>
          </div>
          <p className="text-[11px] text-slate-600 leading-relaxed mt-2">
            Links open the deploying Databricks workspace (sign-in / object access required) — the inline descriptions read without it.
          </p>
        </section>

        <section className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-4">
          <h2 className="text-base font-semibold mb-2 text-amber-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>What's simulated vs real</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The underlying ground-truth glucose signal (<span className="font-mono text-slate-300">glucose_true</span>) is
            <span className="text-slate-200"> real by default</span> — seeded from the{' '}
            <a href="https://data.mendeley.com/datasets/3hbcscwz44/1" target="_blank" rel="noopener noreferrer"
              className="text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2">HUPA-UCM type-1-diabetes dataset</a>{' '}
            <span className="text-slate-500">(Universidad Complutense de Madrid)</span>; a
            fully-synthetic generator mode is also available for clean demos (chosen per deployment via{' '}
            <span className="font-mono text-cyan-400">baseline_source</span>). What the device <em>reports</em>{' '}
            (<span className="font-mono text-slate-300">glucose_observed</span>) is that signal with a{' '}
            <span className="text-amber-300 font-medium">simulated</span> ±40 mg/dL calibration bias layered on during
            incident windows — the gap between the two is the device fault the platform detects. Patient identifiers,
            device metadata, and the calibration-bug incidents themselves are <span className="text-amber-300 font-medium">always
            simulated</span> for demonstration — there is no real adverse-event PHI.
          </p>
          <p className="text-sm text-slate-400 leading-relaxed mt-3">
            <span className="text-slate-200 font-medium">How this extrapolates to real devices.</span> The demo can measure
            device error directly because it generates the ground-truth <span className="font-mono text-slate-300">glucose_true</span>.
            A fielded CGM fleet has <span className="text-slate-200">no such reference</span> — the sensor <em>is</em> the
            measurement — so the same calibration drift is caught from the <em>observed</em> readings alone: by watching a
            firmware/model cohort's glucose <span className="text-slate-200">distribution shift</span> away from a matched
            baseline (other firmware, its own pre-rollout window, or the fleet), corroborated by occasional fingerstick/lab
            reference checks (the industry <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC7189145/" target="_blank" rel="noopener noreferrer" className="font-mono text-cyan-400 hover:text-cyan-300 underline decoration-dotted underline-offset-2">MARD</a> accuracy metric) and per-lot
            sensor-quality telemetry. The operator views are unchanged — same Firmware × Day heatmap and its
            In-incident ⇄ Fleet-wide toggle — only the cell metric swaps from <em>error-vs-truth</em> to
            <em> distribution divergence from a matched baseline</em>. On this same Lakehouse that would run as streaming
            drift detection, with a low-latency operational store (Lakebase) holding the live alert state — the app's
            Alert Triage queue already runs on exactly that store (on deployments that enable it).
            <span className="text-slate-500"> (CGM accuracy methods are general industry practice — confirm against
            device-specific documentation for a real deployment.)</span>
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-2.5 text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Jump to a view</h2>
          {/* compact icon-left cards (vs tall stacked) so the row tucks into the fold */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ROLE_CARDS.map((c) => (
              <button key={c.title} onClick={() => navigate(c.route)}
                className="bg-slate-900/50 border border-slate-800 rounded-lg p-3.5 text-left hover:border-cyan-500/40 transition-colors group flex items-center gap-3">
                <c.icon className="w-5 h-5 text-cyan-400 shrink-0" strokeWidth={2.5} />
                <div className="min-w-0">
                  <h3 className="text-sm font-semibold text-slate-100 leading-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>{c.title}</h3>
                  <p className="text-[11px] text-slate-500 font-mono leading-tight mt-0.5">{c.sub}</p>
                </div>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
