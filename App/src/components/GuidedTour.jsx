import React, { useState, useEffect, useCallback, useLayoutEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TOUR_STEPS } from '../tour/steps';

// Lightweight coachmark tour (no external dep). Listens for the
// 'glucosphere:start-tour' window event, navigates per step, spotlights the
// step's target element, and renders a Next/Back/Done card.
export default function GuidedTour() {
  const [active, setActive] = useState(false);
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const [cardStyle, setCardStyle] = useState(null);
  const cardRef = useRef(null);
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
        // Re-measure when the target's size changes (async data renders into the
        // heatmap/charts AFTER the initial measure → box would otherwise be too small)
        // and when the page scrolls/resizes, so the spotlight stays glued + correctly sized.
        const ro = new ResizeObserver(measure);
        ro.observe(el);
        ro.observe(document.body);
        window.addEventListener('scroll', measure, true);
        window.addEventListener('resize', measure);
        cleanup = () => {
          clearTimeout(t);
          ro.disconnect();
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

  // Place the tooltip card RELATIVE to the spotlighted element: below it when there's
  // room, else above, else pinned near the bottom — so the card never covers the highlight.
  useLayoutEffect(() => {
    if (!rect || !cardRef.current) { setCardStyle(null); return; }
    const card = cardRef.current.getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight, M = 16, GAP = 14;
    const clampX = (x) => Math.max(M, Math.min(x, vw - card.width - M));
    const clampY = (y) => Math.max(M, Math.min(y, vh - card.height - M));
    const cx = rect.left + rect.width / 2 - card.width / 2;   // horizontally centered on element
    const cy = rect.top + rect.height / 2 - card.height / 2;  // vertically centered on element
    let pos;
    if (rect.bottom + GAP + card.height <= vh - M)        pos = { top: rect.bottom + GAP, left: clampX(cx) };            // below
    else if (rect.top - GAP - card.height >= M)           pos = { top: rect.top - GAP - card.height, left: clampX(cx) }; // above
    else if (rect.right + GAP + card.width <= vw - M)     pos = { top: clampY(cy), left: rect.right + GAP };             // right (tall element)
    else if (rect.left - GAP - card.width >= M)           pos = { top: clampY(cy), left: rect.left - GAP - card.width }; // left
    else                                                  pos = { top: Math.max(M, vh - card.height - M), left: clampX(cx) }; // pinned fallback
    setCardStyle({ position: 'fixed', ...pos, pointerEvents: 'auto' });
  }, [rect, i]);

  const close = useCallback(() => { setActive(false); setRect(null); setCardStyle(null); }, []);
  if (!active || !step) return null;

  return (
    <div className="fixed inset-0 z-[110]" style={{ pointerEvents: 'none' }}>
      <div className="absolute inset-0 bg-black/40" style={{ pointerEvents: 'auto' }} onClick={close} />
      {rect && (
        <div className="absolute border-2 border-cyan-400 rounded-lg transition-all"
          style={{ top: rect.top - 6, left: rect.left - 6, width: rect.width + 12, height: rect.height + 12, boxShadow: '0 0 0 9999px rgba(2,6,23,0.55)' }} />
      )}
      <div ref={cardRef}
        className="fixed w-[92%] max-w-md bg-slate-900 border border-cyan-500/50 rounded-xl p-5 shadow-2xl transition-all"
        style={cardStyle || { left: '50%', transform: 'translateX(-50%)', bottom: 40, pointerEvents: 'auto' }}>
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
