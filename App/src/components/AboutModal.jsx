import React from 'react';
import { X, Compass } from 'lucide-react';

// First-visit orientation modal. Brief version of the About page; the "Take the
// tour" CTA hands off to the GuidedTour via the onStartTour callback.
export default function AboutModal({ open, onClose, onStartTour }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()}
        className="max-w-md w-[92%] bg-slate-900 border border-slate-700 rounded-xl p-6 shadow-2xl">
        <div className="flex items-start justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-100" style={{ fontFamily: 'Georgia, serif' }}>Welcome to Glucosphere</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300" aria-label="Close"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-slate-400 leading-relaxed">
          A control tower for a CGM device fleet. Three moves: <span className="text-cyan-400">detect</span> drift,
          <span className="text-cyan-400"> diagnose</span> the firmware at fault, <span className="text-cyan-400">assess</span> patient risk.
          The ground-truth CGM signal is real by default (HUPA-UCM; a synthetic mode is also available); device readings and the ±40 mg/dL calibration incidents are simulated.
        </p>
        <div className="flex flex-wrap gap-3 mt-5">
          <button onClick={onStartTour}
            className="flex items-center gap-2 px-4 py-2 border border-cyan-500/50 text-cyan-300 rounded-lg hover:bg-cyan-500/10 transition-colors text-sm font-medium">
            <Compass className="w-4 h-4" /> Take the 60-second tour
          </button>
          <button onClick={onClose} className="px-4 py-2 text-slate-400 hover:text-slate-200 text-sm">Explore on my own</button>
        </div>
      </div>
    </div>
  );
}
