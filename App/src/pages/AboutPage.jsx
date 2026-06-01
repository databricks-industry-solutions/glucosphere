import React from 'react';
import { useNavigate } from 'react-router-dom';
import { HeartHandshake, Wrench, BookOpen, ArrowLeft, Github } from 'lucide-react';
import BrandMark from '../components/BrandMark';

const REPO_URL = 'https://github.com/databricks-industry-solutions/glucosphere';

const ROLE_CARDS = [
  { icon: Wrench, title: 'Device Support', sub: 'Biomedical Engineering', route: '/device-support' },
  { icon: HeartHandshake, title: 'Diabetes Coach', sub: 'Diabetes Coaching', route: '/diabetes-coach' },
  { icon: BookOpen, title: 'Metrics Explained', sub: 'How every metric is computed', route: '/metrics-explained' },
];

export default function AboutPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-slate-500 hover:text-slate-300 shrink-0" aria-label="Back to home">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3 min-w-0">
            <BrandMark className="w-7 h-7 text-cyan-400 shrink-0" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>About Glucosphere</h1>
              <p className="text-xs text-slate-500 font-mono truncate">CGM Stream Intelligence — fleet control tower · detect · diagnose · act</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-3 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>What this is</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            <span className="text-cyan-400 font-medium">Glucosphere</span> is a control tower for a
            continuous-glucose-monitor (CGM) device fleet: detect device-accuracy drift, diagnose it to the
            firmware at fault, and assess the patient-risk impact. <span className="text-slate-500">(The
            live monitoring feed is nicknamed "GlucoStream" — the continuous stream of device readings the
            platform watches.)</span>
          </p>
          <div className="flex justify-end mt-4">
            <a href={REPO_URL} target="_blank" rel="noopener noreferrer" title="View on GitHub"
              className="flex items-center gap-2 px-3 py-1.5 border border-slate-700 rounded-lg hover:bg-slate-800/60 transition-colors">
              <Github className="w-4 h-4 text-slate-400" />
              <span className="text-xs font-mono text-slate-400">industry-solutions/glucosphere</span>
            </a>
          </div>
        </section>

        <section className="bg-amber-500/5 border border-amber-500/20 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-3 text-amber-300" style={{ fontFamily: 'Georgia, serif' }}>What's simulated vs real</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            The underlying ground-truth glucose signal (<span className="font-mono text-slate-300">glucose_true</span>) is
            <span className="text-slate-200"> real by default</span> — seeded from the HUPA-UCM type-1-diabetes dataset; a
            fully-synthetic generator mode is also available for clean demos (chosen per deployment via{' '}
            <span className="font-mono text-cyan-400">baseline_source</span>). What the device <em>reports</em>{' '}
            (<span className="font-mono text-slate-300">glucose_observed</span>) is that signal with a{' '}
            <span className="text-amber-300 font-medium">simulated</span> ±40 mg/dL calibration bias layered on during
            incident windows — the gap between the two is the device fault the platform detects. Patient identifiers,
            device metadata, and the calibration-bug incidents themselves are <span className="text-amber-300 font-medium">always
            simulated</span> for demonstration — there is no real adverse-event PHI.
          </p>
        </section>

        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6 flex items-center gap-5">
          <BrandMark className="w-12 h-12 text-cyan-400 shrink-0" />
          <div>
            <h2 className="text-lg font-semibold mb-1 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>The mark</h2>
            <p className="text-sm text-slate-400 leading-relaxed">
              The Glucosphere mark is the <span className="text-slate-200">glucose ring</span> — the six-membered
              pyranose form of the glucose molecule (5 carbons + 1 oxygen) that a CGM actually measures — drawn
              Haworth-style with its <span className="text-slate-200">CH₂OH and hydroxyl branches</span>, plus a
              <span className="text-cyan-400 font-medium"> live-reading sensor node</span> for the continuous monitoring.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-lg font-semibold mb-4 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>Jump to a view</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {ROLE_CARDS.map((c) => (
              <button key={c.title} onClick={() => navigate(c.route)}
                className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 text-left hover:border-cyan-500/40 transition-colors group">
                <c.icon className="w-6 h-6 text-cyan-400 mb-3" strokeWidth={2.5} />
                <h3 className="text-base font-semibold text-slate-100" style={{ fontFamily: 'Georgia, serif' }}>{c.title}</h3>
                <p className="text-xs text-slate-500 mt-1 font-mono">{c.sub}</p>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
