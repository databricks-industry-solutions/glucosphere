import React, { useState } from 'react';
import NavRail from './NavRail';

const PIN_KEY = 'glucosphere-rail-pinned';

// Wraps the routed pages with the persistent nav rail. Owns the rail's pinned
// state (persisted to localStorage): when pinned the rail stays expanded and
// pushes content (pl-56); when not, the collapsed 64px strip expands on hover as
// an overlay (content reserves only pl-16).
export default function AppShell({ children }) {
  const [pinned, setPinned] = useState(() => {
    try { return localStorage.getItem(PIN_KEY) === '1'; } catch { return false; }
  });
  const togglePin = () => setPinned((p) => {
    const next = !p;
    try { localStorage.setItem(PIN_KEY, next ? '1' : '0'); } catch { /* ignore */ }
    return next;
  });

  return (
    <div className="min-h-screen bg-slate-950">
      <NavRail pinned={pinned} onTogglePin={togglePin} />
      <div className={`${pinned ? 'pl-56' : 'pl-16'} transition-all duration-200`}>{children}</div>
    </div>
  );
}
