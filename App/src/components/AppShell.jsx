import React from 'react';
import NavRail from './NavRail';

// Wraps the routed pages with the persistent nav rail. The rail is a fixed
// overlay (expands on hover above content), so content only reserves the 64px
// collapsed width via pl-16 — no layout shift when the rail expands.
export default function AppShell({ children }) {
  return (
    <div className="min-h-screen bg-slate-950">
      <NavRail />
      <div className="pl-16">{children}</div>
    </div>
  );
}
