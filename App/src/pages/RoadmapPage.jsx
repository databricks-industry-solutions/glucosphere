import React from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import SplashGallery from '../components/SplashGallery';

// "Where this goes" vision page — the pitch trio (detect · diagnose · assess) as
// preview cards, off the operational landing. Today's app realizes ① Detect; these
// preview the not-yet-built ② Diagnose + ③ Assess views on the same governed data.
export default function RoadmapPage() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 py-4 flex items-center gap-4">
          <button onClick={() => navigate('/')} className="text-slate-500 hover:text-slate-300" aria-label="Back to home">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <BrandMark className="w-7 h-7 text-cyan-400" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>Roadmap</h1>
              <p className="text-xs text-slate-500 font-mono">Where the control tower goes next — detect · diagnose · assess</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        <section className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-2 text-slate-200" style={{ fontFamily: 'Georgia, serif' }}>Fuller control-tower views</h2>
          <p className="text-sm text-slate-400 leading-relaxed">
            Today the app realizes <span className="text-cyan-400 font-medium">① Detect</span> — the fleet
            and incident overview on the home page. These previews show where it goes next, completing the
            <span className="text-slate-200"> detect → diagnose → assess</span> arc — all built on the same
            governed Databricks data.
          </p>
        </section>
        <SplashGallery />
      </main>
    </div>
  );
}
