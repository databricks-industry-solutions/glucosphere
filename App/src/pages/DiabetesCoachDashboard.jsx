import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Stethoscope, Search, TrendingUp, TrendingDown, AlertCircle, MessageSquare, FileText, Activity, Loader2 } from 'lucide-react';
import { getPopulationMetrics, getInsulinMetrics } from './DiabetesCoachDashboard/queries';

export default function DiabetesCoachDashboard() {
  const navigate = useNavigate();
  const [selectedPatient, setSelectedPatient] = useState('Sarah K.');
  const [queryText, setQueryText] = useState('');
  
  // Clinical metrics state
  const [populationMetrics, setPopulationMetrics] = useState(null);
  const [insulinMetrics, setInsulinMetrics] = useState(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  
  // Genie query state
  const [genieResponse, setGenieResponse] = useState(null);
  const [genieLoading, setGenieLoading] = useState(false);
  const [genieError, setGenieError] = useState(null);
  const [conversationId, setConversationId] = useState(null);
  
  // Fetch population-level clinical metrics
  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setMetricsLoading(true);
        const [popMetrics, insulinData] = await Promise.all([
          getPopulationMetrics(),
          getInsulinMetrics()
        ]);
        
        setPopulationMetrics(popMetrics);
        setInsulinMetrics(insulinData);
      } catch (error) {
        console.error('Failed to fetch clinical metrics:', error);
      } finally {
        setMetricsLoading(false);
      }
    };
    
    fetchMetrics();
  }, []);
  
  // Handle Genie query
  const handleGenieQuery = async () => {
    if (!queryText.trim()) return;
    
    try {
      setGenieLoading(true);
      setGenieError(null);
      
      const response = await fetch('/api/genie/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          question: queryText,
          conversation_id: conversationId
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to query Genie');
      }
      
      const data = await response.json();
      console.log('Genie response:', data);
      
      // Update conversation ID for follow-up questions
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
      }
      
      setGenieResponse(data);
    } catch (error) {
      console.error('Genie query error:', error);
      setGenieError(error.message);
    } finally {
      setGenieLoading(false);
    }
  };


  const glucoseData = [
    { time: '12am', value: 110 },
    { time: '3am', value: 95 },
    { time: '6am', value: 140 },
    { time: '9am', value: 180 },
    { time: '12pm', value: 160 },
    { time: '3pm', value: 145 },
    { time: '6pm', value: 190 },
    { time: '9pm', value: 130 }
  ];

  const patterns = [
    { type: 'Nocturnal Hypoglycemia', frequency: '3x/week', trend: 'increasing', severity: 'high' },
    { type: 'Post-Meal Spikes', frequency: 'Daily', trend: 'stable', severity: 'medium' },
    { type: 'Dawn Phenomenon', frequency: '5x/week', trend: 'decreasing', severity: 'low' }
  ];

  const recentQueries = [
    'How many patients had hypoglycemia in the last 24 hours?',
    'What is the average glucose level by region?',
    'Show me patients with glucose out of range grouped by device model',
    'How many patients are using each device model?',
    'What is the average time in range for all patients?',
    'Show the distribution of patients by diagnosis type'
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[1600px] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => navigate('/')}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                <Stethoscope className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: 'Georgia, serif' }}>
                  Diabetes Coach Dashboard
                </h1>
                <p className="text-xs text-slate-500 font-mono">Provider Encounter Preparation</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 rounded-full">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            <span className="text-xs font-mono text-emerald-400">LIVE DATA</span>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        {/* Population-Level Clinical Metrics */}
        <section className="mb-8">
          <div className="flex items-center gap-3 mb-4">
            <Activity className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
              Population Clinical Metrics
            </h2>
            <span className="text-xs text-slate-500 font-mono">(Last 24 Hours)</span>
          </div>
          
          <div className="grid grid-cols-6 gap-4 mb-6">
            {/* Time in Range - Most Important */}
            <div className="bg-gradient-to-br from-emerald-500/10 to-emerald-600/5 border border-emerald-500/30 rounded-lg p-5 hover:border-emerald-500/50 transition-colors">
              <p className="text-xs text-emerald-400 font-mono mb-2">TIME IN RANGE</p>
              <p className="text-3xl font-mono font-bold text-emerald-400">
                {metricsLoading ? '...' : (populationMetrics?.timeInRange != null ? `${populationMetrics.timeInRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">70-180 mg/dL</p>
              <div className="mt-3 h-1.5 bg-slate-900 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400" 
                  style={{ width: `${populationMetrics?.timeInRange || 0}%` }}
                />
              </div>
            </div>

            {/* Average Glucose */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">AVG GLUCOSE</p>
              <p className="text-3xl font-mono font-bold text-slate-200">
                {metricsLoading ? '...' : (populationMetrics?.avgGlucose != null ? populationMetrics.avgGlucose : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">mg/dL</p>
              {populationMetrics?.stddevGlucose && (
                <p className="text-xs text-slate-600 mt-1">±{populationMetrics.stddevGlucose} SD</p>
              )}
            </div>

            {/* Hypoglycemia */}
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-lg p-5 hover:border-rose-500/50 transition-colors">
              <p className="text-xs text-rose-400 font-mono mb-2">HYPOGLYCEMIA</p>
              <p className="text-3xl font-mono font-bold text-rose-400">
                {metricsLoading ? '...' : (populationMetrics?.pctTimeBelowRange != null ? `${populationMetrics.pctTimeBelowRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">&lt;70 mg/dL</p>
              {populationMetrics?.patientsWithHypo && (
                <p className="text-xs text-rose-400/60 mt-1">{populationMetrics.patientsWithHypo} patients</p>
              )}
            </div>

            {/* Hyperglycemia */}
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-5 hover:border-amber-500/50 transition-colors">
              <p className="text-xs text-amber-400 font-mono mb-2">HYPERGLYCEMIA</p>
              <p className="text-3xl font-mono font-bold text-amber-400">
                {metricsLoading ? '...' : (populationMetrics?.pctTimeAboveRange != null ? `${populationMetrics.pctTimeAboveRange}%` : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">&gt;180 mg/dL</p>
              {populationMetrics?.patientsWithHyper && (
                <p className="text-xs text-amber-400/60 mt-1">{populationMetrics.patientsWithHyper} patients</p>
              )}
            </div>

            {/* Patients Monitored */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">PATIENTS</p>
              <p className="text-3xl font-mono font-bold text-cyan-400">
                {metricsLoading ? '...' : (populationMetrics?.totalPatientsMonitored != null ? populationMetrics.totalPatientsMonitored : 'N/A')}
              </p>
              <p className="text-xs text-slate-500 mt-2">Monitored</p>
              <div className="mt-3 flex items-center gap-1">
                <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
                <span className="text-xs text-emerald-400 font-mono">Active</span>
              </div>
            </div>

            {/* Glucose Range */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-5 hover:border-slate-700 transition-colors">
              <p className="text-xs text-slate-500 font-mono mb-2">GLUCOSE RANGE</p>
              <div className="flex items-baseline gap-1">
                <p className="text-2xl font-mono font-bold text-slate-200">
                  {metricsLoading ? '...' : (populationMetrics?.minGlucose != null ? Math.round(populationMetrics.minGlucose) : 'N/A')}
                </p>
                <span className="text-slate-600">-</span>
                <p className="text-2xl font-mono font-bold text-slate-200">
                  {metricsLoading ? '...' : (populationMetrics?.maxGlucose != null ? Math.round(populationMetrics.maxGlucose) : 'N/A')}
                </p>
              </div>
              <p className="text-xs text-slate-500 mt-2">mg/dL</p>
            </div>
          </div>

          {/* Insulin Delivery Metrics */}
          {insulinMetrics && (
            <div className="grid grid-cols-4 gap-4">
              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">BASAL EVENTS</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.basalEvents?.toLocaleString() || 'N/A'}
                </p>
                {insulinMetrics.avgBasalRate && (
                  <p className="text-xs text-slate-600 mt-1">Avg: {insulinMetrics.avgBasalRate}u/hr</p>
                )}
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">BOLUS EVENTS</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.bolusEvents?.toLocaleString() || 'N/A'}
                </p>
                {insulinMetrics.avgBolusVolume && (
                  <p className="text-xs text-slate-600 mt-1">Avg: {insulinMetrics.avgBolusVolume}u</p>
                )}
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">CARB ENTRIES</p>
                <p className="text-xl font-mono font-bold text-slate-300">
                  {insulinMetrics.carbEvents?.toLocaleString() || 'N/A'}
                </p>
                <p className="text-xs text-slate-600 mt-1">Patient logged</p>
              </div>

              <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-4">
                <p className="text-xs text-slate-500 font-mono mb-1">HYPO EVENTS</p>
                <p className="text-xl font-mono font-bold text-rose-400">
                  {populationMetrics?.hypoEvents?.toLocaleString() || 'N/A'}
                </p>
                <p className="text-xs text-slate-600 mt-1">Readings &lt;70</p>
              </div>
            </div>
          )}
        </section>

        {/* Patient Selector */}
        <section className="mb-8">
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <div className="relative">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
              <input
                type="text"
                placeholder="Patient search — coming soon (demo cohort fixed); see GitHub issue #5"
                disabled
                className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-12 pr-4 py-3 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors cursor-not-allowed opacity-60"
              />
            </div>
          </div>
        </section>

        {/* Pre-Visit Summary Panel */}
        <div className="grid grid-cols-12 gap-6 mb-8">
          {/* Left Column - Main Summary */}
          <div className="col-span-8 space-y-6">
            {/* Patient Header */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-2xl font-semibold" style={{ fontFamily: 'Georgia, serif' }}>
                      {selectedPatient}
                    </h2>
                    <span className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 rounded text-xs text-amber-400 font-mono" title="Patient demographics, KPIs, and 24h chart are demo data — see GitHub issue #5 to wire to real per-patient data.">Demo data</span>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-slate-400 font-mono">
                    <span>Age: 34</span>
                    <span>•</span>
                    <span>Type 1 Diabetes</span>
                    <span>•</span>
                    <span>Device: Dexcom G6</span>
                  </div>
                </div>
                <div className="px-4 py-2 bg-rose-500/10 border border-rose-500/30 rounded-lg">
                  <p className="text-xs text-rose-400 font-mono mb-1">RISK LEVEL</p>
                  <p className="text-xl font-mono font-bold text-rose-400">HIGH</p>
                </div>
              </div>
              
              <div className="grid grid-cols-4 gap-4">
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">AVG GLUCOSE</p>
                  <p className="text-2xl font-mono font-bold text-slate-200">167</p>
                  <p className="text-xs text-slate-500 mt-1">mg/dL (30d)</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">TIME IN RANGE</p>
                  <p className="text-2xl font-mono font-bold text-amber-400">64%</p>
                  <p className="text-xs text-slate-500 mt-1">Target: 70-180</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">HYPOGLYCEMIA</p>
                  <p className="text-2xl font-mono font-bold text-rose-400">12%</p>
                  <p className="text-xs text-slate-500 mt-1">&lt;70 mg/dL</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-slate-500 font-mono mb-1">CV</p>
                  <p className="text-2xl font-mono font-bold text-slate-200">38%</p>
                  <p className="text-xs text-slate-500 mt-1">Variability</p>
                </div>
              </div>
            </div>

            {/* Glucose Trend Chart */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h3 className="text-sm font-medium text-slate-300 mb-1">24-Hour Glucose Profile</h3>
                  <p className="text-xs text-slate-500 font-mono">Last updated: 15 minutes ago</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 px-3 py-1 bg-slate-950 rounded border border-slate-800">
                    <div className="w-3 h-0.5 bg-emerald-500" />
                    <span className="text-xs text-slate-400 font-mono">Target Range</span>
                  </div>
                </div>
              </div>
              
              <div className="relative h-64">
                {/* Target Range Band */}
                <div className="absolute inset-x-0 bg-emerald-500/5 border-y border-emerald-500/20" style={{ top: '30%', height: '40%' }} />
                
                {/* Grid Lines */}
                {[0, 25, 50, 75, 100].map((val) => (
                  <div key={val} className="absolute inset-x-0 border-t border-slate-800" style={{ top: `${val}%` }}>
                    <span className="absolute -left-12 -top-2 text-xs font-mono text-slate-600">
                      {250 - (val * 2.5)}
                    </span>
                  </div>
                ))}
                
                {/* Glucose Line */}
                <svg className="absolute inset-0 w-full h-full" preserveAspectRatio="none">
                  <polyline
                    points={glucoseData.map((d, i) => 
                      `${(i / (glucoseData.length - 1)) * 100}%,${100 - ((d.value - 50) / 200) * 100}%`
                    ).join(' ')}
                    fill="none"
                    stroke="rgb(34 211 238)"
                    strokeWidth="2"
                    className="drop-shadow-[0_0_8px_rgba(34,211,238,0.5)]"
                  />
                  {glucoseData.map((d, i) => (
                    <circle
                      key={i}
                      cx={`${(i / (glucoseData.length - 1)) * 100}%`}
                      cy={`${100 - ((d.value - 50) / 200) * 100}%`}
                      r="3"
                      fill="rgb(34 211 238)"
                      className="cursor-pointer hover:r-5 transition-all"
                    />
                  ))}
                </svg>
                
                {/* Time Labels */}
                <div className="absolute -bottom-6 inset-x-0 flex justify-between text-xs font-mono text-slate-600">
                  {glucoseData.map((d, i) => (
                    <span key={i}>{d.time}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Detected Patterns */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Detected Patterns (Last 30 Days)</h3>
              <div className="space-y-3">
                {patterns.map((pattern, idx) => (
                  <div key={idx} className="flex items-center justify-between p-4 bg-slate-950 rounded border border-slate-800 hover:border-slate-700 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                        pattern.severity === 'high' ? 'bg-rose-500/10 border border-rose-500/30' :
                        pattern.severity === 'medium' ? 'bg-amber-500/10 border border-amber-500/30' :
                        'bg-yellow-500/10 border border-yellow-500/30'
                      }`}>
                        <AlertCircle className={`w-5 h-5 ${
                          pattern.severity === 'high' ? 'text-rose-400' :
                          pattern.severity === 'medium' ? 'text-amber-400' :
                          'text-yellow-400'
                        }`} />
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-slate-200">{pattern.type}</h4>
                        <p className="text-xs text-slate-500 font-mono">{pattern.frequency}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      {pattern.trend === 'increasing' ? (
                        <div className="flex items-center gap-1 text-rose-400">
                          <TrendingUp className="w-4 h-4" />
                          <span className="text-xs font-mono">Increasing</span>
                        </div>
                      ) : pattern.trend === 'decreasing' ? (
                        <div className="flex items-center gap-1 text-emerald-400">
                          <TrendingDown className="w-4 h-4" />
                          <span className="text-xs font-mono">Decreasing</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1 text-slate-500">
                          <span className="text-xs font-mono">→ Stable</span>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column - Risk & Context */}
          <div className="col-span-4 space-y-6">
            {/* Risk Forecast */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-4">72-Hour Risk Forecast</h3>
              
              <div className="space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-mono">Hypoglycemia Risk</span>
                    <span className="text-sm font-mono font-bold text-amber-400">MED - 78%</span>
                  </div>
                  <div className="h-2 bg-slate-950 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-amber-500 to-amber-400" style={{ width: '78%' }} />
                  </div>
                </div>
                
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-mono">Hyperglycemia Risk</span>
                    <span className="text-sm font-mono font-bold text-amber-400">MED - 52%</span>
                  </div>
                  <div className="h-2 bg-slate-950 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-amber-500 to-amber-400" style={{ width: '52%' }} />
                  </div>
                </div>
                
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-slate-500 font-mono">Severe Event Risk</span>
                    <span className="text-sm font-mono font-bold text-emerald-400">LOW - 18%</span>
                  </div>
                  <div className="h-2 bg-slate-950 rounded-full overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400" style={{ width: '18%' }} />
                  </div>
                </div>
              </div>
              
              <div className="mt-4 p-3 bg-amber-500/5 border border-amber-500/20 rounded text-xs text-amber-400">
                <p className="font-mono mb-1">⚠️ Key Driver:</p>
                <p>Nocturnal hypoglycemia pattern + recent basal insulin adjustment</p>
              </div>
            </div>

            {/* Device Status */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Device Status</h3>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Sensor Age</span>
                  <span className="text-sm font-mono text-slate-300">6 days</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Signal Quality</span>
                  <span className="text-sm font-mono text-emerald-400">Excellent</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Last Calibration</span>
                  <span className="text-sm font-mono text-slate-300">18 hours ago</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500 font-mono">Data Coverage</span>
                  <span className="text-sm font-mono text-slate-300">97%</span>
                </div>
              </div>
              
              <div className="mt-4 pt-4 border-t border-slate-800">
                <div className="flex items-center gap-2 text-emerald-400">
                  <div className="w-2 h-2 bg-emerald-400 rounded-full" />
                  <span className="text-xs font-mono">No device issues detected</span>
                </div>
              </div>
            </div>

            {/* Historical Context */}
            <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Relevant History</h3>
              
              <div className="space-y-3">
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-cyan-400 font-mono mb-1">2 weeks ago</p>
                  <p className="text-xs text-slate-400">Basal insulin increased from 24u to 28u due to persistent hyperglycemia</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-cyan-400 font-mono mb-1">1 month ago</p>
                  <p className="text-xs text-slate-400">Started new exercise routine (morning cardio), correlates with nocturnal lows</p>
                </div>
                <div className="p-3 bg-slate-950 rounded border border-slate-800">
                  <p className="text-xs text-cyan-400 font-mono mb-1">3 months ago</p>
                  <p className="text-xs text-slate-400">HbA1c: 7.8% (improved from 8.4%)</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Natural Language Query with CGM Genie */}
        <section>
          <h2 className="text-lg font-semibold mb-6 text-slate-300" style={{ fontFamily: 'Georgia, serif' }}>
            Natural Language Query - CGM Genie
          </h2>
          
          <div className="bg-slate-900/50 border border-slate-800 rounded-lg p-6">
            <div className="relative mb-4">
              <MessageSquare className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
              <input 
                type="text"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleGenieQuery()}
                placeholder="Ask a question about CGM data... (e.g., 'Show patients with hypoglycemia in the last 24 hours')"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-12 pr-32 py-3 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors"
                disabled={genieLoading}
              />
              <button
                onClick={handleGenieQuery}
                disabled={genieLoading || !queryText.trim()}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
              >
                {genieLoading && <Loader2 className="w-4 h-4 animate-spin" />}
                {genieLoading ? 'Querying...' : 'Query'}
              </button>
            </div>

            {/* Visible status line when query is in flight — earlier the only
                feedback was the button label flipping to "Querying...", which
                wasn't clear enough that the query had actually been submitted. */}
            {genieLoading && (
              <div className="mb-4 flex items-center gap-2 text-xs text-cyan-300 font-mono bg-cyan-500/10 border border-cyan-500/30 rounded px-3 py-2">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Sending query to CGM Genie — this typically takes 3–10 seconds…</span>
              </div>
            )}

            <div className="mb-4">
              <p className="text-xs text-slate-500 mb-2">Suggested Queries:</p>
              <div className="grid grid-cols-2 gap-2">
                {recentQueries.map((query, idx) => (
                  <button 
                    key={idx}
                    onClick={() => setQueryText(query)}
                    disabled={genieLoading}
                    className="px-3 py-2 bg-slate-800 hover:bg-slate-700 disabled:bg-slate-800 disabled:cursor-not-allowed rounded text-xs text-slate-400 text-left transition-colors border border-slate-700"
                  >
                    💬 {query}
                  </button>
                ))}
              </div>
              
              {/* Query Categories */}
              <details className="mt-3">
                <summary className="text-xs text-cyan-400 cursor-pointer hover:text-cyan-300">
                  View more query examples by category →
                </summary>
                <div className="mt-3 space-y-3">
                  {/* Glycemic Control */}
                  <div className="p-3 bg-slate-900 rounded border border-slate-800">
                    <p className="text-xs text-emerald-400 font-mono mb-2">📊 Glycemic Control</p>
                    <div className="space-y-1">
                      {[
                        'What percentage of patients have time in range above 70%?',
                        'Show average glucose levels by patient diagnosis',
                        'How many readings were below 70 mg/dL today?',
                        'What is the coefficient of variation across all patients?'
                      ].map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setQueryText(q)}
                          disabled={genieLoading}
                          className="block w-full text-left text-xs text-slate-400 hover:text-emerald-400 px-2 py-1 rounded hover:bg-slate-950"
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Device Analytics */}
                  <div className="p-3 bg-slate-900 rounded border border-slate-800">
                    <p className="text-xs text-amber-400 font-mono mb-2">🔧 Device Analytics</p>
                    <div className="space-y-1">
                      {[
                        'Which device models have the most out-of-range readings?',
                        'Show device distribution by region',
                        'How many patients are using firmware version greater than 2.0?',
                        'What is the average sensor age by device model?'
                      ].map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setQueryText(q)}
                          disabled={genieLoading}
                          className="block w-full text-left text-xs text-slate-400 hover:text-amber-400 px-2 py-1 rounded hover:bg-slate-950"
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Patient Insights */}
                  <div className="p-3 bg-slate-900 rounded border border-slate-800">
                    <p className="text-xs text-cyan-400 font-mono mb-2">👥 Patient Insights</p>
                    <div className="space-y-1">
                      {[
                        'How many patients are in each region?',
                        'Show patient count by diagnosis type',
                        'What is the distribution of patient birth years?',
                        'How many new patients were activated this month?'
                      ].map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setQueryText(q)}
                          disabled={genieLoading}
                          className="block w-full text-left text-xs text-slate-400 hover:text-cyan-400 px-2 py-1 rounded hover:bg-slate-950"
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  </div>
                  
                  {/* Insulin & Activity */}
                  <div className="p-3 bg-slate-900 rounded border border-slate-800">
                    <p className="text-xs text-purple-400 font-mono mb-2">💉 Insulin & Activity</p>
                    <div className="space-y-1">
                      {[
                        'Show total bolus events in the last 24 hours',
                        'What is the average basal rate for patients with good control?',
                        'How many carb entries were logged today?',
                        'Show correlation between activity and glucose levels'
                      ].map((q, i) => (
                        <button
                          key={i}
                          onClick={() => setQueryText(q)}
                          disabled={genieLoading}
                          className="block w-full text-left text-xs text-slate-400 hover:text-purple-400 px-2 py-1 rounded hover:bg-slate-950"
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </details>
            </div>
            
            {/* Genie Response */}
            {genieError && (
              <div className="mt-4 p-4 bg-rose-500/10 border border-rose-500/30 rounded-lg">
                <p className="text-sm text-rose-400">❌ Error: {genieError}</p>
              </div>
            )}
            
            {genieResponse && !genieError && (
              <div className="mt-4 p-4 bg-slate-950 border border-slate-700 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center flex-shrink-0">
                    <MessageSquare className="w-4 h-4 text-white" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-cyan-400 font-mono mb-2">CGM Genie Response:</p>
                    
                    {/* Display query results from attachments */}
                    {genieResponse.attachments && genieResponse.attachments.length > 0 && (
                      <div className="space-y-4">
                        {genieResponse.attachments.map((attachment, idx) => (
                          <div key={idx}>
                            {/* Query results */}
                            {attachment.query && attachment.query.statement_response && (
                              <div className="mb-4">
                                <div className="text-sm text-slate-300 mb-3">
                                  {attachment.query.statement_response.result?.data_array?.length > 0 ? (
                                    <div className="space-y-2">
                                      <p className="font-medium text-emerald-400">
                                        ✓ Found {attachment.query.statement_response.result.data_array.length} result(s):
                                      </p>
                                      <div className="overflow-x-auto">
                                        <table className="w-full text-xs border border-slate-800 rounded">
                                          <thead className="bg-slate-900">
                                            <tr>
                                              {attachment.query.statement_response.manifest.schema.columns.map((col, colIdx) => (
                                                <th key={colIdx} className="px-3 py-2 text-left text-slate-400 border-b border-slate-800 font-mono">
                                                  {col.name}
                                                </th>
                                              ))}
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {attachment.query.statement_response.result.data_array.map((row, rowIdx) => (
                                              <tr key={rowIdx} className="border-b border-slate-800 hover:bg-slate-900/50">
                                                {row.map((cell, cellIdx) => (
                                                  <td key={cellIdx} className="px-3 py-2 text-slate-300 font-mono">
                                                    {typeof cell === 'number' ? cell.toFixed(2) : cell}
                                                  </td>
                                                ))}
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                      </div>
                                    </div>
                                  ) : (
                                    <p className="text-slate-400">Query executed successfully but returned no results.</p>
                                  )}
                                </div>
                                
                                {/* Show the SQL query used */}
                                {attachment.query.query && (
                                  <details className="mt-3">
                                    <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400 flex items-center gap-2">
                                      <span>View SQL Query</span>
                                      {attachment.query.description && (
                                        <span className="text-slate-600">- {attachment.query.description}</span>
                                      )}
                                    </summary>
                                    <pre className="mt-2 p-3 bg-slate-900 rounded border border-slate-800 text-xs text-cyan-400 overflow-x-auto">
                                      {attachment.query.query}
                                    </pre>
                                  </details>
                                )}
                              </div>
                            )}
                            
                            {/* Suggested follow-up questions */}
                            {attachment.suggested_questions && attachment.suggested_questions.questions && (
                              <div className="mt-4 p-3 bg-cyan-500/5 border border-cyan-500/20 rounded">
                                <p className="text-xs text-cyan-400 font-mono mb-2">💡 Suggested follow-up questions:</p>
                                <div className="space-y-1">
                                  {attachment.suggested_questions.questions.map((question, qIdx) => (
                                    <button
                                      key={qIdx}
                                      onClick={() => setQueryText(question)}
                                      className="block w-full text-left text-xs text-slate-400 hover:text-cyan-400 py-1 px-2 rounded hover:bg-slate-900 transition-colors"
                                    >
                                      → {question}
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                            
                            {/* Text responses from Genie */}
                            {attachment.text && attachment.text.content && (
                              <div className="mt-3 p-3 bg-slate-900 rounded border border-slate-800">
                                <p className="text-xs text-slate-400">{attachment.text.content}</p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}

