import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Wrench, HeartHandshake, BookOpen, Telescope, Info, Compass } from 'lucide-react';
import BrandMark from './BrandMark';

// Persistent left nav rail — the "control tower" shell. Collapsed 64px icon
// strip; expands to ~224px on hover as a fixed overlay (above content, so no
// layout shift). Active route gets a cyan left-border outline (no solid fill).
const ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Home', sub: 'Fleet overview' },
  { to: '/device-support', icon: Wrench, label: 'Device Support', sub: 'Biomedical Eng.' },
  { to: '/diabetes-coach', icon: HeartHandshake, label: 'Diabetes Coach', sub: 'Coaching' },
  { to: '/metrics-explained', icon: BookOpen, label: 'Metrics Explained', sub: 'How metrics compute' },
  { to: '/roadmap', icon: Telescope, label: 'Roadmap', sub: 'Where this goes' },
  { to: '/about', icon: Info, label: 'About', sub: 'Naming · data · repo' },
];

export default function NavRail() {
  return (
    <nav className="group fixed top-0 left-0 z-[90] h-screen w-16 hover:w-56 bg-[#0b1220] border-r border-slate-800 transition-all duration-200 overflow-hidden flex flex-col py-3">
      <div className="flex items-center gap-3 px-[18px] pb-3 mb-2 border-b border-slate-800/70">
        <BrandMark className="w-7 h-7 text-cyan-400 shrink-0" />
        <div className="opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
          <p className="text-sm font-semibold text-slate-100" style={{ fontFamily: 'Georgia, serif' }}>Glucosphere</p>
          <p className="text-[10px] text-slate-500 font-mono">CGM control tower</p>
        </div>
      </div>

      {ITEMS.map(({ to, icon: Icon, label, sub }) => (
        <NavLink key={to} to={to} end={to === '/'}
          className={({ isActive }) =>
            `flex items-center gap-3 px-[18px] py-2.5 border-l-[3px] whitespace-nowrap transition-colors ${
              isActive ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5' : 'border-transparent text-slate-300 hover:bg-slate-800/60'
            }`}>
          <Icon className="w-5 h-5 shrink-0" />
          <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm">
            {label}<span className="block text-[10px] text-slate-500">{sub}</span>
          </span>
        </NavLink>
      ))}

      {/* Tour sits directly under the nav items (not pinned to the bottom). */}
      <button onClick={() => window.dispatchEvent(new Event('glucosphere:start-tour'))}
        className="flex items-center gap-3 px-[18px] py-2.5 mt-1 border-l-[3px] border-transparent text-slate-300 hover:bg-slate-800/60 whitespace-nowrap">
        <Compass className="w-5 h-5 shrink-0 text-cyan-400" />
        <span className="opacity-0 group-hover:opacity-100 transition-opacity text-sm text-cyan-300">Take a tour</span>
      </button>
    </nav>
  );
}
