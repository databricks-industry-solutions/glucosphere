import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TOUR_STEPS } from '../tour/steps';

// Lightweight coachmark tour (no external dep). Listens for the
// 'glucosphere:start-tour' window event, navigates per step, spotlights the
// step's target element, and renders a Next/Back/Done card.
export default function GuidedTour() {
  const [active, setActive] = useState(false);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const start = () => { setI(0); setActive(true); };
    window.addEventListener('glucosphere:start-tour', start);
    return () => window.removeEventListener('glucosphere:start-tour', start);
  }, []);

  const step = TOUR_STEPS[i];

  // Ensure we're on the right route for this step.
  useEffect(() => {
    if (active && step && location.pathname !== step.route) navigate(step.route);
  }, [active, i, step, location.pathname, navigate]);

  // Position the spotlight on the step's target. Retry until present (route change),
  // then MEASURE AFTER the smooth scroll settles + keep re-measuring on scroll/resize
  // so the box stays glued to the element (measuring too early lands it off-target).
  useEffect(() => {
    if (!active || !step) return;
    let tries = 0;
    let cleanup = () => {};
    const find = setInterval(() => {
      const el = document.querySelector(step.selector);
      if (el) {
        clearInterval(find);
        const measure = () => setRect(el.getBoundingClientRect());
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        const t = setTimeout(measure, 380);           // after smooth-scroll settles
        window.addEventListener('scroll', measure, true);
        window.addEventListener('resize', measure);
        cleanup = () => {
          clearTimeout(t);
          window.removeEventListener('scroll', measure, true);
          window.removeEventListener('resize', measure);
        };
      } else if (++tries > 25) {
        clearInterval(find);
        setRect(null);
      }
    }, 100);
    return () => { clearInterval(find); cleanup(); };
  }, [active, i, step, location.pathname]);

  const close = useCallback(() => { setActive(false); setRect(null); }, []);
  if (!active || !step) return null;

  return (
    <div className="fixed inset-0 z-[110]" style={{ pointerEvents: 'none' }}>
      <div className="absolute inset-0 bg-black/40" style={{ pointerEvents: 'auto' }} onClick={close} />
      {rect && (
        <div className="absolute border-2 border-cyan-400 rounded-lg transition-all"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12, boxShadow: '0 0 0 9999px rgba(2,6,23,0.55)' }} />
      )}
      <div className="absolute left-1/2 -translate-x-1/2 bottom-10 w-[92%] max-w-md bg-slate-900 border border-cyan-500/50 rounded-xl p-5 shadow-2xl"
        style={{ pointerEvents: 'auto' }}>
        <p className="text-xs text-cyan-400 font-mono mb-1">Step {i + 1} of {TOUR_STEPS.length}</p>
        <h3 className="text-base font-semibold text-slate-100" style={{ fontFamily: 'Georgia, serif' }}>{step.title}</h3>
        <p className="text-sm text-slate-400 mt-1 leading-relaxed">{step.body}</p>
        <div className="flex justify-between items-center mt-4">
          <button onClick={close} className="text-xs text-slate-500 hover:text-slate-300">Skip</button>
          <div className="flex gap-2">
            {i > 0 && <button onClick={() => setI(i - 1)} className="px-3 py-1.5 text-sm text-slate-300 border border-slate-700 rounded-lg hover:bg-slate-800">Back</button>}
            {i < TOUR_STEPS.length - 1
              ? <button onClick={() => setI(i + 1)} className="px-3 py-1.5 text-sm text-cyan-300 border border-cyan-500/50 rounded-lg hover:bg-cyan-500/10">Next</button>
              : <button onClick={close} className="px-3 py-1.5 text-sm text-cyan-300 border border-cyan-500/50 rounded-lg hover:bg-cyan-500/10">Done</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
