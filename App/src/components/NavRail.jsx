import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Wrench, HeartHandshake, BookOpen, Telescope, Info, Compass, Pin, PinOff } from 'lucide-react';
import BrandMark from './BrandMark';

// Persistent left nav rail — the "control tower" shell. Collapsed 64px icon strip
// that expands to ~224px on hover; can be PINNED open (persisted by AppShell). The
// role entries (Device Support / Diabetes Coach) are grouped under a "By role"
// label — the front-door role navigation (replaces the old landing role cards).
const HOME = { to: '/', icon: LayoutDashboard, label: 'Home', sub: 'Fleet overview' };
const ROLES = [
  { to: '/device-support', icon: Wrench, label: 'Device Support', sub: 'Biomedical Eng.' },
  { to: '/diabetes-coach', icon: HeartHandshake, label: 'Diabetes Coach', sub: 'Coaching' },
];
const MORE = [
  { to: '/metrics-explained', icon: BookOpen, label: 'Metrics Explained', sub: 'How metrics compute' },
  { to: '/roadmap', icon: Telescope, label: 'Roadmap', sub: 'Where this goes' },
  { to: '/about', icon: Info, label: 'About', sub: 'Naming · data · repo' },
];

export default function NavRail({ pinned = false, onTogglePin }) {
  // Labels show when pinned, else only on hover (CSS group-hover).
  const reveal = pinned ? 'opacity-100' : 'opacity-0 group-hover:opacity-100';

  const Item = ({ to, icon: Icon, label, sub }) => (
    <NavLink to={to} end={to === '/'}
      className={({ isActive }) =>
        `flex items-center gap-3 px-[18px] py-2.5 border-l-[3px] whitespace-nowrap transition-colors ${
          isActive ? 'border-cyan-400 text-cyan-300 bg-cyan-500/5' : 'border-transparent text-slate-300 hover:bg-slate-800/60'
        }`}>
      <Icon className="w-5 h-5 shrink-0" />
      <span className={`${reveal} transition-opacity text-sm`}>
        {label}<span className="block text-[10px] text-slate-500">{sub}</span>
      </span>
    </NavLink>
  );

  return (
    <nav className={`group fixed top-0 left-0 z-[90] h-screen ${pinned ? 'w-56' : 'w-16 hover:w-56'} bg-[#0b1220] border-r border-slate-800 transition-all duration-200 overflow-hidden flex flex-col py-3`}>
      {/* Brand + pin toggle */}
      <div className="flex items-center gap-3 px-[18px] pb-3 mb-2 border-b border-slate-800/70">
        <BrandMark className="w-7 h-7 text-cyan-400 shrink-0" />
        <div className={`${reveal} transition-opacity whitespace-nowrap flex-1 min-w-0`}>
          <p className="text-sm font-semibold text-slate-100" style={{ fontFamily: 'Georgia, serif' }}>Glucosphere</p>
          <p className="text-[10px] text-slate-500 font-mono">CGM control tower</p>
        </div>
        <button onClick={onTogglePin} title={pinned ? 'Unpin sidebar' : 'Pin sidebar open'} aria-label={pinned ? 'Unpin sidebar' : 'Pin sidebar open'}
          className={`${reveal} transition-opacity shrink-0 ${pinned ? 'text-cyan-400' : 'text-slate-500'} hover:text-cyan-300`}>
          {pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}
        </button>
      </div>

      <Item {...HOME} />

      {/* By role — front-door role navigation */}
      <p className={`overflow-hidden px-[18px] text-[9px] font-mono uppercase tracking-wider text-slate-600 transition-all ${pinned ? 'max-h-5 opacity-100 pt-2 pb-1' : 'max-h-0 opacity-0 group-hover:max-h-5 group-hover:opacity-100 group-hover:pt-2 group-hover:pb-1'}`}>By role</p>
      {ROLES.map((it) => <Item key={it.to} {...it} />)}

      <div className="mt-2 mb-1 mx-[18px] border-t border-slate-800/70" />
      {MORE.map((it) => <Item key={it.to} {...it} />)}

      <div className="flex-1" />
      <button onClick={() => window.dispatchEvent(new Event('glucosphere:start-tour'))}
        className="flex items-center gap-3 px-[18px] py-2.5 border-l-[3px] border-transparent text-slate-300 hover:bg-slate-800/60 whitespace-nowrap">
        <Compass className="w-5 h-5 shrink-0 text-cyan-400" />
        <span className={`${reveal} transition-opacity text-sm text-cyan-300`}>Take a tour</span>
      </button>
    </nav>
  );
}
