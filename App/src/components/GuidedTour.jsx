import React, { useState, useEffect, useCallback, useLayoutEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { TOUR_STEPS, TOUR_STEPS_FULL, TOUR_STEPS_INTERACTIVE } from '../tour/steps';
import { useLakebaseConfigured } from '../hooks/useLakebase';

// Lightweight coachmark tour (no external dep). Listens for the
// 'glucosphere:start-tour' window event, navigates per step, spotlights the
// step's target element, and renders a Next/Back/Done card.
export default function GuidedTour() {
  const [active, setActive] = useState(false);
  const [variant, setVariant] = useState(null); // null → show Quick/Full chooser; 'quick' | 'full' once picked
  const [i, setI] = useState(0);
  const [rect, setRect] = useState(null);
  const [cardStyle, setCardStyle] = useState(null);
  const [paused, setPaused] = useState(false); // interactive variant: overlay steps aside so the page is clickable; Resume returns to the same step
  const [assistantOpen, setAssistantOpen] = useState(false); // mirrors the assistant panel's real open state (broadcast by GlobalAssistant) → dock Resume beside the open slide-over
  const [justResumed, setJustResumed] = useState(false); // true right after Resume → highlight Next so the eye knows to continue; cleared on Next/Back/pause/close
  const cardRef = useRef(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Start the tour. A launcher may preset the variant (e.g. {detail:{variant:'full'}})
    // — used for A/B; with no variant we show the Quick/Full chooser first.
    const start = (e) => { setVariant(e?.detail?.variant ?? null); setI(0); setPaused(false); setJustResumed(false); setActive(true); };
    window.addEventListener('glucosphere:start-tour', start);
    return () => window.removeEventListener('glucosphere:start-tour', start);
  }, []);

  // Track the assistant panel's real open state (broadcast by GlobalAssistant) so the Resume
  // button docks beside the open slide-over whether the panel was opened by the tour or by the user.
  useEffect(() => {
    const onState = (e) => setAssistantOpen(!!e.detail?.open);
    window.addEventListener('glucosphere:assistant-state', onState);
    return () => window.removeEventListener('glucosphere:assistant-state', onState);
  }, []);

  // Lakebase-gated stops (requiresLakebase) are filtered out on deploys without
  // the binding — their /triage target shows a "not enabled" panel there, so
  // there'd be nothing to spotlight. The chooser counts use the same arrays.
  const lakebaseConfigured = useLakebaseConfigured();
  const gate = (arr) => arr.filter(s => !s.requiresLakebase || lakebaseConfigured);
  const quickSteps = gate(TOUR_STEPS);
  const fullSteps = gate(TOUR_STEPS_FULL);
  const interactiveSteps = gate(TOUR_STEPS_INTERACTIVE);
  const steps = variant === 'full' ? fullSteps
    : variant === 'interactive' ? interactiveSteps
    : quickSteps;
  const step = variant ? steps[i] : null;

  // Ensure we're on the right route for this step.
  useEffect(() => {
    // While paused (interactive "try it"), don't yank the user back to the step's route —
    // they may be exploring elsewhere; resuming re-runs this and returns them to the step.
    if (active && !paused && step && location.pathname !== step.route) navigate(step.route);
  }, [active, paused, i, step, location.pathname, navigate]);

  // Tour automation: open/close the assistant per step (fires on step ENTRY only, so it
  // doesn't override what the user does during a "try it" pause). Steps that spotlight an
  // assistant-internal control set `openAssistant` to a mode ('genie' | 'mas'); every other
  // step closes the panel so it doesn't linger. GlobalAssistant listens for this event.
  useEffect(() => {
    if (!active || !step) return;
    window.dispatchEvent(new CustomEvent('glucosphere:assistant', {
      detail: { open: !!step.openAssistant, mode: step.openAssistant || undefined },
    }));
  }, [active, i, step]); // eslint-disable-line react-hooks/exhaustive-deps

  // Position the spotlight on the step's target. CLEAR the prior step's rect first so a
  // stale box never lingers at the previous target's coordinates during the search, then
  // retry until the element is present (route change + async data-load guards can delay it),
  // MEASURE AFTER the smooth scroll settles, and keep re-measuring on scroll/resize so the
  // box stays glued to the element (measuring too early lands it off-target).
  useEffect(() => {
    if (!active || !step || paused) return;
    setRect(null);   // drop the previous step's highlight immediately (no stale box mid-transition)
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
      } else if (++tries > 100) {
        // ~10s budget: a target can sit behind an async data-load guard (e.g. the Coach
        // page renders coach-risk only after its live patient query returns) and appear
        // well after the route transition — give it time before giving up.
        clearInterval(find);
        setRect(null);
      }
    }, 100);
    return () => { clearInterval(find); cleanup(); };
  }, [active, paused, i, step, location.pathname]);

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
    else {
      // Oversized target (a full-width, taller-than-viewport panel): no room on any
      // side, so tuck the card into whichever viewport CORNER has more free space —
      // covering as little of the highlight as possible instead of sitting dead-center.
      const left = (vw - rect.right) >= rect.left ? vw - card.width - M : M;
      const top = (vh - rect.bottom) >= rect.top ? vh - card.height - M : M;
      pos = { top: clampY(top), left: clampX(left) };
    }
    setCardStyle({ position: 'fixed', ...pos, pointerEvents: 'auto' });
  }, [rect, i]);

  const close = useCallback(() => { setActive(false); setVariant(null); setPaused(false); setJustResumed(false); setRect(null); setCardStyle(null); }, []);
  if (!active) return null;

  // Quick/Full chooser (A/B) — shown when the tour starts without a preset variant.
  if (!variant) {
    return (
      <div className="fixed inset-0 z-[110]">
        <div className="absolute inset-0 bg-black/40" onClick={close} />
        <div className="fixed left-1/2 -translate-x-1/2 bottom-40 w-[92%] max-w-md bg-slate-900 border border-cyan-500/50 rounded-xl p-5 shadow-2xl">
          <h3 className="text-base font-semibold text-slate-100" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>Take a tour</h3>
          <p className="text-sm text-slate-400 mt-1 leading-relaxed">Pick how much you'd like to see.</p>
          <div className="flex flex-col gap-2 mt-4">
            <button onClick={() => { setVariant('quick'); setI(0); }}
              className="px-3 py-2.5 text-sm text-cyan-300 border border-cyan-500/50 rounded-lg hover:bg-cyan-500/10 text-left">
              Quick overview
              <span className="block text-[11px] text-slate-500 font-mono mt-0.5">{quickSteps.length} steps · Detect → Diagnose → Assess{lakebaseConfigured ? ' → Act' : ''} → platform</span>
            </button>
            {/* Full walkthrough commented out for now: the Interactive variant is Full + pause-to-try
                + the metrics/about close, so it subsumes Full. Un-comment to restore the read-only path. */}
            {/* <button onClick={() => { setVariant('full'); setI(0); }}
              className="px-3 py-2.5 text-sm text-cyan-300 border border-cyan-500/50 rounded-lg hover:bg-cyan-500/10 text-left">
              Full walkthrough
              <span className="block text-[11px] text-slate-500 font-mono mt-0.5">{fullSteps.length} steps · every panel + AI assistant</span>
            </button> */}
            <button onClick={() => { setVariant('interactive'); setI(0); }}
              className="px-3 py-2.5 text-sm text-amber-300 border border-amber-500/50 rounded-lg hover:bg-amber-500/10 text-left">
              Interactive walkthrough
              <span className="block text-[11px] text-slate-500 font-mono mt-0.5">{interactiveSteps.length} steps · pause any step to try it, then resume</span>
            </button>
          </div>
          <button onClick={close} className="mt-3 text-xs text-slate-500 hover:text-slate-300">Skip</button>
        </div>
      </div>
    );
  }

  if (!step) return null;

  // Interactive "try it" — the overlay steps aside so the whole page is clickable; a floating
  // Resume pill brings the user back to THIS step (active + i are preserved → no restart).
  if (paused) {
    // Dock the Resume pill NEAR the Assistant whenever this step is about it; else top-center.
    // panelShown: the panel is (or is about to be) open — either the tour auto-opens it on this step
    // (step.openAssistant, e.g. the Genie/MAS steps — keyed off the step itself so the dock doesn't
    // wait on the assistant-state broadcast) OR the user opened it manually (assistantOpen).
    // fabStep: a paused step that spotlights an assistant control (data-tour selector contains
    // "assistant") while the panel is still CLOSED → dock above the Ask FAB. Defensive fallback:
    // the current FAB step isn't pausable (the next steps auto-open the assistant), so no live step
    // hits this arm today — it keeps the dock correct if a closed-panel assistant pause is added later.
    const panelShown = !!step.openAssistant || assistantOpen;
    const fabStep = (step.selector || '').includes('assistant');
    const resumePos = panelShown
      ? 'top-20 right-[456px]'                 // panel OPEN (sm:w-[440px] right slide-over) → beside its tab row (440 + 16 gap)
      : fabStep
        ? 'bottom-24 right-6'                  // assistant step, panel still CLOSED → just above the bottom-right "Ask" FAB
        : 'top-20 left-1/2 -translate-x-1/2';  // everything else → top-center, clear of the FAB and the left nav rail
    return (
      // Prominent (solid amber border + glow) so it doesn't blend into the dark page — matches the
      // in-card "Try it yourself" button. Inline backgroundColor forces a fully-opaque slate-900: the
      // paused state has no dim backdrop, so a translucent bg (Tailwind --tw-bg-opacity) would let the
      // page bleed through.
      <button onClick={() => { setPaused(false); setJustResumed(true); }}
        style={{ backgroundColor: '#0f172a' }}
        className={`fixed ${resumePos} z-[110] flex items-center gap-2 px-6 py-3 border-2 border-amber-400 rounded-lg shadow-2xl shadow-amber-500/30 text-base font-semibold text-amber-300 hover:brightness-125`}>
        ▶ Resume tour <span className="text-[11px] font-mono font-normal text-slate-400">Step {i + 1}/{steps.length}</span>
      </button>
    );
  }

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
        <p className="text-xs text-cyan-400 font-mono mb-1">Step {i + 1} of {steps.length}</p>
        <h3 className="text-base font-semibold text-slate-100" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>{step.title}</h3>
        <p className="text-sm text-slate-400 mt-1 leading-relaxed">{step.body}</p>
        {/* Pause only where there's something to do: toggle steps (step.interactive → "Try it
            yourself"), assistant-explore steps (step.openAssistant) and read/deep-link pages
            (step.explore) → "Explore". Pure-narrative steps and the FAB step — where the next steps
            auto-open the assistant — get a plain Next, no redundant pause. */}
        {variant === 'interactive' && (step.interactive || step.openAssistant || step.explore) && (
          <button onClick={() => { setPaused(true); setJustResumed(false); }}
            className="mt-3 w-full px-3 py-2 text-sm text-amber-300 border border-amber-500/40 rounded-lg hover:bg-amber-500/10">
            ⏸ {step.interactive ? "Try it yourself — I'll wait here" : "Explore — I'll wait here"}
          </button>
        )}
        <div className="flex justify-between items-center mt-4">
          <button onClick={close} className="text-xs text-slate-500 hover:text-slate-300">Skip</button>
          <div className="flex gap-2">
            {i > 0 && <button onClick={() => { setI(i - 1); setJustResumed(false); }} className="px-3 py-1.5 text-sm text-slate-300 border border-slate-700 rounded-lg hover:bg-slate-800">Back</button>}
            {i < steps.length - 1
              ? <button onClick={() => { setI(i + 1); setJustResumed(false); }}
                  className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${justResumed ? 'bg-cyan-500 text-slate-950 font-semibold border border-cyan-400 ring-2 ring-cyan-400/50' : 'text-cyan-300 border border-cyan-500/50 hover:bg-cyan-500/10'}`}>Next</button>
              : <button onClick={() => { close(); navigate('/'); }} className="px-3 py-1.5 text-sm text-cyan-300 border border-cyan-500/50 rounded-lg hover:bg-cyan-500/10">Done</button>}
          </div>
        </div>
      </div>
    </div>
  );
}
