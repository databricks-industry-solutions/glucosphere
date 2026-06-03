import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clipboard, AlertCircle, Phone, MessageCircle, CheckCircle, Clock, Filter, ChevronDown } from 'lucide-react';
import { useGoBack } from '../hooks/useGoBack';

export default function CareManagementDashboard() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const [selectedPriority, setSelectedPriority] = useState('all');
  const [expandedPatient, setExpandedPatient] = useState(null);
  const [triageCount, setTriageCount] = useState(47);
  
  useEffect(() => {
    const interval = setInterval(() => {
      setTriageCount(prev => prev + Math.floor(Math.random() * 3 - 1));
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const priorities = [
    { label: 'All Patients', value: 'all', count: 47, color: 'slate' },
    { label: 'Critical', value: 'critical', count: 5, color: 'rose' },
    { label: 'High Priority', value: 'high', count: 12, color: 'amber' },
    { label: 'Medium', value: 'medium', count: 18, color: 'yellow' },
    { label: 'Low', value: 'low', count: 12, color: 'emerald' }
  ];

  const patients = [
    {
      id: 'PT-8473',
      name: 'Sarah K.',
      age: 34,
      priority: 'critical',
      riskScore: 94,
      alert: 'Severe hypoglycemia risk - 3 nocturnal events last 48h',
      lastContact: '2 days ago',
      deviceIssue: false,
      pattern: 'Nocturnal hypoglycemia increasing',
      recommendations: [
        'Call patient immediately - assess symptoms and recent changes',
        'Review basal insulin timing and dose with provider',
        'Schedule urgent telehealth visit within 24 hours'
      ],
      vitals: { avgGlucose: 167, timeInRange: 64, hypoEvents: 8 },
      context: 'Recently increased basal insulin 2 weeks ago. New morning exercise routine.'
    },
    {
      id: 'PT-2918',
      name: 'John D.',
      age: 56,
      priority: 'high',
      riskScore: 82,
      alert: 'Persistent hyperglycemia - TIR declining',
      lastContact: '5 days ago',
      deviceIssue: false,
      pattern: 'Post-meal spikes >250 mg/dL',
      recommendations: [
        'Outreach to discuss meal timing and carb counting',
        'Review bolus calculator settings',
        'Send educational materials on carb-to-insulin ratios'
      ],
      vitals: { avgGlucose: 198, timeInRange: 52, hypoEvents: 2 },
      context: 'Reported increased stress at work. Skipping some bolus doses.'
    },
    {
      id: 'PT-5632',
      name: 'Maria L.',
      age: 42,
      priority: 'high',
      riskScore: 78,
      alert: 'Device connectivity issues + rising glucose',
      lastContact: '1 day ago',
      deviceIssue: true,
      pattern: 'Sensor gaps increasing',
      recommendations: [
        'Troubleshoot device connectivity - may need replacement',
        'Temporary SMBG monitoring protocol',
        'Order new sensor if issues persist'
      ],
      vitals: { avgGlucose: 182, timeInRange: 61, hypoEvents: 3 },
      context: 'Sensor showing intermittent connection. Patient reports adhesive issues.'
    },
    {
      id: 'PT-7821',
      name: 'Robert M.',
      age: 67,
      priority: 'medium',
      riskScore: 61,
      alert: 'Gradual TIR decline over 2 weeks',
      lastContact: '3 days ago',
      deviceIssue: false,
      pattern: 'Morning hyperglycemia pattern',
      recommendations: [
        'Check-in call to assess recent changes',
        'Review nighttime snacking habits',
        'Consider basal insulin adjustment'
      ],
      vitals: { avgGlucose: 175, timeInRange: 68, hypoEvents: 4 },
      context: 'Recent dietary changes. Grandchildren visiting.'
    },
    {
      id: 'PT-9183',
      name: 'Linda P.',
      age: 29,
      priority: 'medium',
      riskScore: 58,
      alert: 'Increased glucose variability',
      lastContact: '4 days ago',
      deviceIssue: false,
      pattern: 'CV increased from 32% to 41%',
      recommendations: [
        'Discuss recent lifestyle changes',
        'Review insulin administration technique',
        'Assess stress and sleep patterns'
      ],
      vitals: { avgGlucose: 162, timeInRange: 71, hypoEvents: 5 },
      context: 'Started new job with irregular schedule. Sleep disruption reported.'
    },
    {
      id: 'PT-4509',
      name: 'David H.',
      age: 51,
      priority: 'low',
      riskScore: 42,
      alert: 'Routine follow-up - stable management',
      lastContact: '1 week ago',
      deviceIssue: false,
      pattern: 'Stable TIR, well-controlled',
      recommendations: [
        'Scheduled routine check-in',
        'Reinforce positive behaviors',
        'Update care plan documentation'
      ],
      vitals: { avgGlucose: 142, timeInRange: 82, hypoEvents: 1 },
      context: 'Excellent adherence. Engaged patient. No recent concerns.'
    }
  ];

  const filteredPatients = selectedPriority === 'all' 
    ? patients 
    : patients.filter(p => p.priority === selectedPriority);

  const getPriorityColor = (priority) => {
    switch(priority) {
      case 'critical': return { bg: 'bg-rose-500/10', border: 'border-rose-500/30', text: 'text-rose-400', badge: 'bg-rose-500' };
      case 'high': return { bg: 'bg-amber-500/10', border: 'border-amber-500/30', text: 'text-amber-400', badge: 'bg-amber-500' };
      case 'medium': return { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400', badge: 'bg-yellow-500' };
      case 'low': return { bg: 'bg-emerald-500/10', border: 'border-emerald-500/30', text: 'text-emerald-400', badge: 'bg-emerald-500' };
      default: return { bg: 'bg-slate-500/10', border: 'border-slate-500/30', text: 'text-slate-400', badge: 'bg-slate-500' };
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-[88rem] mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={goBack}
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 flex items-center justify-center">
                <Clipboard className="w-5 h-5 text-white" strokeWidth={2.5} />
              </div>
              <div>
                <h1 className="text-xl font-semibold tracking-tight" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                  Care Management Dashboard
                </h1>
                <p className="text-xs text-slate-500 font-mono">Remote Patient Monitoring - Triage Queue</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-xs text-slate-500 font-mono">Active Queue</p>
                <p className="text-lg font-mono font-bold text-slate-300">{triageCount}</p>
              </div>
              <div className="w-px h-8 bg-slate-800" />
              <div className="text-right">
                <p className="text-xs text-slate-500 font-mono">Avg Response Time</p>
                <p className="text-lg font-mono font-bold text-emerald-400">3.8m</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[88rem] mx-auto px-6 py-8">
        {/* Priority Filters */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-slate-300" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
              Priority Triage Queue
            </h2>
            <div className="flex items-center gap-3">
              <Filter className="w-5 h-5 text-slate-500" />
              <select className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-300 font-mono focus:outline-none focus:border-cyan-500">
                <option>Sort by Risk Score</option>
                <option>Sort by Last Contact</option>
                <option>Sort by Priority</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-5 gap-4 mb-6">
            {priorities.map((priority) => (
              <button
                key={priority.value}
                onClick={() => setSelectedPriority(priority.value)}
                className={`p-4 rounded-lg border transition-all ${
                  selectedPriority === priority.value
                    ? `${getPriorityColor(priority.value).bg} ${getPriorityColor(priority.value).border}`
                    : 'bg-slate-900/30 border-slate-800 hover:border-slate-700'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`text-xs font-mono uppercase ${
                    selectedPriority === priority.value 
                      ? getPriorityColor(priority.value).text 
                      : 'text-slate-500'
                  }`}>
                    {priority.label}
                  </span>
                  <div className={`w-2 h-2 rounded-full ${
                    selectedPriority === priority.value 
                      ? getPriorityColor(priority.value).badge 
                      : 'bg-slate-700'
                  }`} />
                </div>
                <p className={`text-2xl font-mono font-bold ${
                  selectedPriority === priority.value 
                    ? 'text-slate-100' 
                    : 'text-slate-400'
                }`}>
                  {priority.count}
                </p>
              </button>
            ))}
          </div>
        </section>

        {/* Patient Worklist */}
        <section>
          <div className="space-y-4">
            {filteredPatients.map((patient, idx) => {
              const colors = getPriorityColor(patient.priority);
              const isExpanded = expandedPatient === idx;
              
              return (
                <div 
                  key={idx}
                  className={`bg-slate-900/50 border rounded-lg overflow-hidden transition-all ${
                    isExpanded ? 'border-cyan-500/50 shadow-lg shadow-cyan-500/10' : `${colors.border} hover:border-slate-700`
                  }`}
                >
                  {/* Main Card */}
                  <div 
                    className="p-6 cursor-pointer"
                    onClick={() => setExpandedPatient(isExpanded ? null : idx)}
                  >
                    <div className="flex items-start gap-6">
                      {/* Priority Indicator */}
                      <div className="flex-shrink-0">
                        <div className={`w-16 h-16 rounded-lg ${colors.bg} border ${colors.border} flex flex-col items-center justify-center`}>
                          <span className={`text-2xl font-mono font-bold ${colors.text}`}>
                            {patient.riskScore}
                          </span>
                          <span className="text-xs font-mono text-slate-500">RISK</span>
                        </div>
                      </div>

                      {/* Patient Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-start justify-between mb-3">
                          <div>
                            <div className="flex items-center gap-3 mb-1">
                              <h3 className="text-lg font-semibold text-slate-100" style={{ fontFamily: '"Avenir Next", Avenir, "Segoe UI", system-ui, sans-serif' }}>
                                {patient.name}
                              </h3>
                              <span className="text-sm font-mono text-slate-500">
                                {patient.id} • Age {patient.age}
                              </span>
                              {patient.deviceIssue && (
                                <span className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/30 rounded text-xs font-mono text-amber-400">
                                  DEVICE ISSUE
                                </span>
                              )}
                            </div>
                            <p className={`text-sm font-medium ${colors.text} mb-2`}>
                              ⚠️ {patient.alert}
                            </p>
                            <p className="text-xs text-slate-500 font-mono">
                              Pattern: {patient.pattern}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-xs text-slate-500 font-mono mb-1">Last Contact</p>
                            <p className="text-sm font-mono text-slate-300">{patient.lastContact}</p>
                          </div>
                        </div>

                        {/* Vitals Strip */}
                        <div className="flex items-center gap-6 p-3 bg-slate-950 rounded border border-slate-800">
                          <div>
                            <p className="text-xs text-slate-500 font-mono">Avg Glucose</p>
                            <p className="text-sm font-mono font-bold text-slate-300">{patient.vitals.avgGlucose} mg/dL</p>
                          </div>
                          <div className="w-px h-8 bg-slate-800" />
                          <div>
                            <p className="text-xs text-slate-500 font-mono">Time in Range</p>
                            <p className={`text-sm font-mono font-bold ${
                              patient.vitals.timeInRange > 70 ? 'text-emerald-400' :
                              patient.vitals.timeInRange > 50 ? 'text-amber-400' :
                              'text-rose-400'
                            }`}>{patient.vitals.timeInRange}%</p>
                          </div>
                          <div className="w-px h-8 bg-slate-800" />
                          <div>
                            <p className="text-xs text-slate-500 font-mono">Hypo Events (7d)</p>
                            <p className={`text-sm font-mono font-bold ${
                              patient.vitals.hypoEvents > 5 ? 'text-rose-400' :
                              patient.vitals.hypoEvents > 2 ? 'text-amber-400' :
                              'text-emerald-400'
                            }`}>{patient.vitals.hypoEvents}</p>
                          </div>
                        </div>
                      </div>

                      {/* Quick Actions */}
                      <div className="flex-shrink-0 flex flex-col gap-2">
                        <button className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                          <Phone className="w-4 h-4" />
                          Call
                        </button>
                        <button className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded-lg text-sm font-medium transition-colors flex items-center gap-2">
                          <MessageCircle className="w-4 h-4" />
                          Message
                        </button>
                        <button 
                          className="p-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 rounded-lg transition-colors"
                          onClick={(e) => {
                            e.stopPropagation();
                            setExpandedPatient(isExpanded ? null : idx);
                          }}
                        >
                          <ChevronDown className={`w-5 h-5 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details */}
                  {isExpanded && (
                    <div className="border-t border-slate-800 bg-slate-950/50 p-6">
                      <div className="grid grid-cols-2 gap-6">
                        {/* Recommended Actions */}
                        <div>
                          <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                            <AlertCircle className="w-4 h-4 text-cyan-400" />
                            Recommended Actions
                          </h4>
                          <div className="space-y-2">
                            {patient.recommendations.map((rec, i) => (
                              <div key={i} className="flex items-start gap-3 p-3 bg-slate-900 rounded border border-slate-800 hover:border-cyan-500/30 transition-colors group">
                                <CheckCircle className="w-4 h-4 text-slate-600 group-hover:text-cyan-400 flex-shrink-0 mt-0.5 transition-colors" />
                                <span className="text-sm text-slate-400 group-hover:text-slate-300 transition-colors">
                                  {rec}
                                </span>
                              </div>
                            ))}
                          </div>
                        </div>

                        {/* Patient Context */}
                        <div>
                          <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-cyan-400" />
                            Patient Context
                          </h4>
                          <div className="p-4 bg-slate-900 rounded border border-slate-800">
                            <p className="text-sm text-slate-400 mb-4">{patient.context}</p>
                            
                            <div className="flex gap-2">
                              <button className="flex-1 px-3 py-2 bg-cyan-500/10 border border-cyan-500/30 rounded text-sm text-cyan-400 hover:bg-cyan-500/20 transition-colors">
                                View Full History
                              </button>
                              <button className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm text-slate-400 hover:bg-slate-700 transition-colors">
                                Care Plan
                              </button>
                            </div>
                          </div>

                          <button className="w-full mt-3 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded text-sm font-medium text-emerald-400 hover:bg-emerald-500/20 transition-colors flex items-center justify-center gap-2">
                            <CheckCircle className="w-4 h-4" />
                            Mark as Contacted
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {filteredPatients.length === 0 && (
            <div className="text-center py-12 bg-slate-900/30 border border-slate-800 rounded-lg">
              <Clipboard className="w-12 h-12 text-slate-700 mx-auto mb-3" />
              <p className="text-slate-500 font-mono">No patients in this priority level</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

