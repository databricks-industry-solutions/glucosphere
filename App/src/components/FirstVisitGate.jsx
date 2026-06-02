import React, { useState, useEffect } from 'react';
import AboutModal from './AboutModal';

// Shows the first-visit orientation modal once per browser (localStorage flag).
// Re-openable from anywhere via the 'glucosphere:open-intro' window event.
const SEEN_KEY = 'glucosphere-seen-intro';

export default function FirstVisitGate({ children, onStartTour }) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(SEEN_KEY)) setOpen(true);
    const reopen = () => setOpen(true);
    window.addEventListener('glucosphere:open-intro', reopen);
    return () => window.removeEventListener('glucosphere:open-intro', reopen);
  }, []);

  const close = () => { localStorage.setItem(SEEN_KEY, '1'); setOpen(false); };
  const startTour = () => { close(); onStartTour?.(); };

  return (
    <>
      {children}
      <AboutModal open={open} onClose={close} onStartTour={startTour} />
    </>
  );
}
