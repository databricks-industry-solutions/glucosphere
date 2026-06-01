import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Compass, AlertTriangle, ArrowRight } from 'lucide-react';
import BrandMark from '../components/BrandMark';
import { getActivePatients, getDevicesOnline, getHighRiskAlerts, getIncidentAffectedPatients } from './GlucoseLanding/queries';
import { IncidentImpactChart, GlucoseAbsoluteChart, GlucoseTimelineChart } from '../components/IncidentCharts';
// Clipboard import available if Care Management is restored

export default function GlucoseLandingDashboard() {
  const navigate = useNavigate();
  
  // Real metrics from CGM schema
  const [activePatients, setActivePatients] = useState(null);
  const [devicesOnline, setDevicesOnline] = useState(null);
  const [highRiskAlerts, setHighRiskAlerts] = useState(null);
  const [incidentAffected, setIncidentAffected] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  // Fetch real metrics from CGM schema
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setMetricsLoading(true);
        const [patients, devices, alerts, incidentCount] = await Promise.all([
          getActivePatients(),
          getDevicesOnline(),
          getHighRiskAlerts(),
          getIncidentAffectedPatients()
        ]);

        setActivePatients(patients);
        setDevicesOnline(devices);
        setHighRiskAlerts(alerts);
        setIncidentAffected(incidentCount);
      } catch (error) {
        console.error('Failed to fetch landing page metrics:', error);
      } finally {
        setMetricsLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <BrandMark className="w-7 h-7 text-cyan-400" />
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                  Glucosphere
                </h1>
                <p className="text-xs text-slate-500 font-mono">CGM Stream Intelligence <span className="text-cyan-400/80">· fleet control tower</span></p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.dispatchEvent(new Event('glucosphere:start-tour'))}
              className="flex items-center gap-2 px-4 py-2 border border-cyan-500/40 rounded-lg hover:bg-cyan-500/10 transition-colors"
            >
              <Compass className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-400">Take a tour</span>
            </button>
            <button
              onClick={() => navigate('/metrics-explained')}
              className="flex items-center gap-2 px-4 py-2 bg-cyan-500/10 border border-cyan-500/30 rounded-lg hover:bg-cyan-500/20 transition-colors"
            >
              <BookOpen className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-cyan-400">Metrics Explained</span>
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
              <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
              <span className="text-xs font-mono text-emerald-400">SYSTEM ACTIVE</span>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500 font-mono">Current Time</p>
              <p className="text-sm font-mono text-slate-300">{new Date().toLocaleTimeString()}</p>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8">
        {/* Hero Metrics */}
        <div data-tour="hero-metrics" className="grid grid-cols-4 gap-4 mb-12">
          <MetricCard
            label="Active Patients"
            value={metricsLoading ? '...' : (activePatients !== null ? activePatients.toLocaleString() : 'N/A')}
            subtitle="last 24h"
            sparkline={[65, 68, 70, 73, 71, 75, 78]}
          />
          <MetricCard
            label="Devices Online"
            value={metricsLoading ? '...' : (devicesOnline !== null ? devicesOnline.toLocaleString() : 'N/A')}
            subtitle="active now"
            sparkline={[98, 99, 99, 98, 99, 100, 99]}
          />
          <MetricCard
            label="High-Risk Alerts"
            value={metricsLoading ? '...' : (highRiskAlerts !== null ? highRiskAlerts.toLocaleString() : 'N/A')}
            subtitle="<54 / >250 · 3h"
            sparkline={[55, 52, 50, 48, 51, 49, 47]}
            to="/device-support"
            cta="Review"
          />
          <MetricCard
            label="Device-Incident-Affected"
            value={metricsLoading ? '...' : (incidentAffected !== null ? incidentAffected.toLocaleString() : 'N/A')}
            subtitle="past 7d"
            sparkline={[0, 0, 300, 300, 300, 600, 600]}
            to="/firmware-lifecycle"
            cta="Diagnose"
            flag={!metricsLoading && incidentAffected !== null && incidentAffected > 0}
          />
        </div>

        {/* Incident Analysis — the Detect detail (fleet/incident overview).
            Role navigation lives in the nav rail (Device Support / Diabetes Coach),
            so the old bottom "Quick Access by Role" cards were removed as redundant. */}
        <section data-tour="incident-charts" className="mb-8">
          <h2 className="text-lg font-semibold mb-4 text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
            Recent Incident Analysis
          </h2>
          <div className="space-y-3">
            <IncidentImpactChart />
            <GlucoseAbsoluteChart />
            <GlucoseTimelineChart />
          </div>
        </section>
      </main>
    </div>
  );
}

function MetricCard({ label, value, change, trend, subtitle, period, sparkline, to, cta, flag }) {
  const navigate = useNavigate();
  const clickable = !!to;
  const Wrapper = clickable ? 'button' : 'div';
  return (
    <Wrapper
      {...(clickable ? { type: 'button', onClick: () => navigate(to) } : {})}
      className={`text-left w-full bg-slate-900/50 border rounded-lg p-5 transition-colors ${
        flag ? 'border-amber-500/40 hover:border-amber-400/70' : 'border-slate-800 hover:border-slate-700'
      } ${clickable ? 'cursor-pointer group' : ''}`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs text-slate-500 font-mono mb-1 flex items-center gap-1">
            {flag && <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />}
            {label}
          </p>
          <p className={`text-2xl font-mono font-bold ${flag ? 'text-amber-300' : 'text-slate-100'}`}>{value}</p>
        </div>
        {sparkline && (
          <div className="w-16 h-8 flex items-end gap-0.5">
            {sparkline.map((val, i) => (
              <div
                key={i}
                className={`flex-1 rounded-t ${flag ? 'bg-amber-500/40' : 'bg-cyan-500/40'}`}
                style={{ height: `${(val / Math.max(...sparkline)) * 100}%` }}
              />
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        {change && (
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${
            trend === 'up' ? 'bg-emerald-500/10 text-emerald-400' :
            trend === 'down' ? 'bg-rose-500/10 text-rose-400' :
            'bg-slate-700 text-slate-400'
          }`}>
            {change}
          </span>
        )}
        {subtitle && <span className="text-xs text-slate-500 font-mono">{subtitle}</span>}
        {period && <span className="text-xs text-slate-500 font-mono">{period}</span>}
        {clickable && cta && (
          <span className="ml-auto text-xs font-mono text-cyan-400 inline-flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
            {cta} <ArrowRight className="w-3 h-3" />
          </span>
        )}
      </div>
    </Wrapper>
  );
}

