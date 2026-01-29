import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Activity, Wifi, AlertCircle, Clock, Wrench, Stethoscope, BookOpen } from 'lucide-react';
import { getActivePatients, getDevicesOnline, getHighRiskAlerts } from './GlucoseLanding/queries';
import { IncidentImpactChart, GlucoseTimelineChart } from '../components/IncidentCharts';
// Clipboard import available if Care Management is restored

export default function GlucoseLandingDashboard() {
  const navigate = useNavigate();
  
  // Real metrics from CGM schema
  const [activePatients, setActivePatients] = useState(null);
  const [devicesOnline, setDevicesOnline] = useState(null);
  const [highRiskAlerts, setHighRiskAlerts] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  
  // Fetch real metrics from CGM schema
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setMetricsLoading(true);
        const [patients, devices, alerts] = await Promise.all([
          getActivePatients(),
          getDevicesOnline(),
          getHighRiskAlerts()
        ]);
        
        setActivePatients(patients);
        setDevicesOnline(devices);
        setHighRiskAlerts(alerts);
      } catch (error) {
        console.error('Failed to fetch landing page metrics:', error);
      } finally {
        setMetricsLoading(false);
      }
    };
    
    fetchMetrics();
  }, []);

  const personas = [
    {
      icon: Wrench,
      title: 'Device Support',
      subtitle: 'Biomedical Engineering',
      metric: '12 devices flagged',
      color: 'from-amber-500 to-orange-500',
      bgColor: 'bg-amber-500/10',
      borderColor: 'border-amber-500/30',
      route: '/device-support'
    },
    {
      icon: Stethoscope,
      title: 'Coaches',
      subtitle: 'Diabetes Coaching',
      metric: 'View Dashboard',
      color: 'from-cyan-500 to-blue-500',
      bgColor: 'bg-cyan-500/10',
      borderColor: 'border-cyan-500/30',
      route: '/clinician'
    }
    // Care Management option temporarily hidden - uncomment to restore
    // {
    //   icon: Clipboard,
    //   title: 'Care Management',
    //   subtitle: 'RPM Nursing',
    //   metric: '5 priority interventions',
    //   color: 'from-emerald-500 to-teal-500',
    //   bgColor: 'bg-emerald-500/10',
    //   borderColor: 'border-emerald-500/30',
    //   route: '/care-management'
    // }
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif' }}>
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <Activity className="w-7 h-7 text-cyan-400" strokeWidth={2.5} />
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
                  GlucoStream Intelligence
                </h1>
                <p className="text-xs text-slate-500 font-mono">Continuous Glucose Monitoring Platform</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
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

      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Hero Metrics */}
        <div className="grid grid-cols-3 gap-4 mb-12">
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
            subtitle="last 24h"
            sparkline={[55, 52, 50, 48, 51, 49, 47]}
          />
        </div>

        {/* Incident Analysis */}
        <section className="mb-12">
          <h2 className="text-lg font-semibold mb-6 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
            Recent Incident Analysis
          </h2>
          <div className="space-y-6">
            <IncidentImpactChart />
            <GlucoseTimelineChart />
          </div>
        </section>

        {/* Quick Access by Role */}
        <section>
          <h2 className="text-lg font-semibold mb-6 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
            Quick Access by Role
          </h2>
          <div className="grid grid-cols-2 gap-6">
            {personas.map((persona, idx) => (
              <button
                key={idx}
                onClick={() => navigate(persona.route)}
                className={`${persona.bgColor} border ${persona.borderColor} rounded-lg p-6 text-left hover:scale-[1.02] transition-all duration-300 group`}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-12 h-12 rounded-lg bg-gradient-to-br ${persona.color} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                    <persona.icon className="w-6 h-6 text-white" strokeWidth={2.5} />
                  </div>
                  <svg className="w-5 h-5 text-slate-500 group-hover:text-slate-300 group-hover:translate-x-1 transition-all" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
                <h3 className="text-lg font-semibold text-slate-100 mb-1" style={{ fontFamily: 'Georgia, serif' }}>
                  {persona.title}
                </h3>
                <p className="text-xs text-slate-500 mb-4 font-mono">{persona.subtitle}</p>
                <div className="flex items-center gap-2">
                  {persona.metric.match(/^\d+/) ? (
                    <>
                      <span className="text-2xl font-mono font-bold bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
                        {persona.metric.split(' ')[0]}
                      </span>
                      <span className="text-sm text-slate-400">{persona.metric.split(' ').slice(1).join(' ')}</span>
                    </>
                  ) : (
                    <span className="text-base font-medium text-slate-400">
                      {persona.metric}
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}

function MetricCard({ label, value, change, trend, subtitle, period, sparkline }) {
  return (
    <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div>
          <p className="text-xs text-slate-500 font-mono mb-1">{label}</p>
          <p className="text-2xl font-mono font-bold text-slate-100">{value}</p>
        </div>
        {sparkline && (
          <div className="w-16 h-8 flex items-end gap-0.5">
            {sparkline.map((val, i) => (
              <div 
                key={i}
                className="flex-1 bg-cyan-500/40 rounded-t"
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
      </div>
    </div>
  );
}

