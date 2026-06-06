import React, { useState, useRef, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Bot, User, Send, Loader, X, Sparkles, Wrench, Database, Zap, RotateCcw } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { callAssistant } from '../api/databricksAgent';
import { getEngine, setEngine } from '../api/assistEngine';

// Default assistant mode for the current route: device-domain pages open to the
// Device-support (MAS) agent, everything else to CGM-data (Genie). A manual
// toggle overrides this and sticks across navigation (see manualMode below).
const routeDefaultMode = (pathname) =>
  (pathname.startsWith('/device-support') || pathname.startsWith('/firmware-lifecycle') || pathname.startsWith('/population-risk'))
    ? 'mas' : 'genie';

// Unified global assistant (spec D4): a single FAB → slide-over, mounted once in
// AppShell so it's available on every page. Replaces the two former page-local
// chats — the Device Support multi-agent-supervisor panel and the Diabetes Coach
// inline Genie box. Two modes share one surface:
//   • Device support  → /api/assist with a switchable engine: 'direct' (fast router →
//     FM/KA) or 'mas' (Multi-Agent Supervisor). Toggle live in the header. Markdown answers.
//   • CGM data (Genie) → Genie (/api/genie/query), STRUCTURED results (table/SQL/follow-ups)
// Each mode keeps its own thread + conversation id so switching is non-destructive.

const uuid = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
  const r = Math.random() * 16 | 0;
  return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
});

const MODES = {
  mas: {
    label: 'Device support',
    icon: Wrench,
    greeting: "👋 I'm the Device Troubleshooting Assistant (powered by Databricks AI agents). Ask about sensor drift, calibration errors, firmware, or troubleshooting steps.",
    // All shown at once in the open assistant — alert-scenario prompts + general
    // device-troubleshooting topics.
    suggestions: ["What does a CGM 'sensor error' / 'wait 10 minutes' alert mean?", 'When should a sensor be replaced vs left to recover?', 'Sensor erroring for 3–4 hours — what are the options?', 'Should a patient finger-prick during a sensor error if symptomatic?', 'Sensor drift in cold temperatures', 'Calibration error troubleshooting', 'Adhesive failure solutions', 'Battery drain issues'],
  },
  genie: {
    label: 'CGM data (Genie)',
    icon: Database,
    greeting: "👋 I'm CGM Genie. Ask questions about the fleet data in natural language — I'll write the SQL and return the results.",
    suggestions: ['How many patients had hypoglycemia in the last 24 hours?', 'Average glucose by region', 'Out-of-range rate by device model', 'Average time in range for all patients'],
  },
};

// Markdown renderer shared by MAS answers (matches the former AgentChatInterface styling).
const mdComponents = {
  h1: (p) => <h1 className="text-base font-bold text-slate-200 mt-2 mb-1" {...p} />,
  h2: (p) => <h2 className="text-sm font-semibold text-slate-200 mt-2 mb-1" {...p} />,
  h3: (p) => <h3 className="text-sm font-medium text-slate-300 mt-1 mb-1" {...p} />,
  ul: (p) => <ul className="list-disc list-inside my-1 space-y-0.5" {...p} />,
  ol: (p) => <ol className="list-decimal list-inside my-1 space-y-0.5" {...p} />,
  li: (p) => <li className="text-slate-300" {...p} />,
  p: (p) => <p className="my-1 text-slate-300" {...p} />,
  code: ({ inline, ...p }) => inline
    ? <code className="bg-slate-900 px-1 py-0.5 rounded text-cyan-400 text-xs" {...p} />
    : <code className="block bg-slate-900 p-2 rounded my-1 text-xs text-cyan-400" {...p} />,
  strong: (p) => <strong className="font-semibold text-slate-200" {...p} />,
};

// Structured Genie result (table + collapsible SQL + suggested follow-ups).
function GenieResult({ payload, onFollowUp }) {
  if (!payload?.attachments?.length) {
    return <p className="text-sm text-slate-400">Query executed, but no structured result was returned.</p>;
  }
  return (
    <div className="space-y-4">
      {payload.attachments.map((att, idx) => {
        const sr = att.query?.statement_response;
        const rows = sr?.result?.data_array;
        const cols = sr?.manifest?.schema?.columns;
        return (
          <div key={idx}>
            {att.query && sr && (
              <div className="mb-3">
                {rows?.length > 0 ? (
                  <div className="space-y-2">
                    <p className="font-medium text-emerald-400 text-sm">✓ {rows.length} result(s):</p>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs border border-slate-800 rounded">
                        <thead className="bg-slate-900">
                          <tr>
                            {cols?.map((c, i) => (
                              <th key={i} className="px-2 py-1.5 text-left text-slate-400 border-b border-slate-800 font-mono">{c.name}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row, r) => (
                            <tr key={r} className="border-b border-slate-800 hover:bg-slate-900/50">
                              {row.map((cell, c) => (
                                <td key={c} className="px-2 py-1.5 text-slate-300 font-mono">{typeof cell === 'number' ? cell.toFixed(2) : cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">Query executed successfully but returned no results.</p>
                )}
                {att.query.query && (
                  <details className="mt-2">
                    <summary className="text-xs text-slate-500 cursor-pointer hover:text-slate-400">View SQL</summary>
                    <pre className="mt-2 p-2 bg-slate-900 rounded border border-slate-800 text-xs text-cyan-400 overflow-x-auto">{att.query.query}</pre>
                  </details>
                )}
              </div>
            )}
            {att.suggested_questions?.questions && (
              <div className="mt-3 p-2 bg-cyan-500/5 border border-cyan-500/20 rounded">
                <p className="text-xs text-cyan-400 font-mono mb-1">💡 Follow-ups:</p>
                {att.suggested_questions.questions.map((q, i) => (
                  <button key={i} onClick={() => onFollowUp(q)} className="block w-full text-left text-xs text-slate-400 hover:text-cyan-400 py-1 px-1 rounded hover:bg-slate-900">→ {q}</button>
                ))}
              </div>
            )}
            {att.text?.content && (
              <div className="mt-2 p-2 bg-slate-900 rounded border border-slate-800">
                <p className="text-xs text-slate-400">{att.text.content}</p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function GlobalAssistant() {
  const location = useLocation();
  const [open, setOpen] = useState(false);
  // null = follow the route default; set once the user picks a mode (sticky).
  const [manualMode, setManualMode] = useState(null);
  const mode = manualMode ?? routeDefaultMode(location.pathname);
  // Engine for the Device-support chat: 'direct' (fast router) or 'mas' (supervisor).
  // Persisted via assistEngine so the Clinical-Analysis drill-down agrees. Live toggle.
  const [engine, setEngineState] = useState(getEngine());
  const [input, setInput] = useState('');
  // Which mode has a request in flight (null = idle). Bound to the ORIGINATING
  // mode so the spinner stays in that thread with the right label even if the
  // user toggles tabs mid-request (and a second concurrent send is blocked).
  const [loadingMode, setLoadingMode] = useState(null);
  const busy = loadingMode !== null;
  // Separate thread + conversation id per mode (non-destructive switching).
  const [threads, setThreads] = useState({
    mas: [{ role: 'assistant', kind: 'text', content: MODES.mas.greeting }],
    genie: [{ role: 'assistant', kind: 'text', content: MODES.genie.greeting }],
  });
  const convIds = useRef({ mas: uuid(), genie: null });
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const messages = threads[mode];
  const ModeIcon = MODES[mode].icon;

  useEffect(() => {
    if (open && messages.length > 1) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [threads, open, mode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tour automation: a guided-tour step can open/close the assistant (and set its mode) via
  // a window event, so the engine toggle / Genie tab exist for the spotlight without a manual
  // click. Same pattern can drive other view toggles later.
  useEffect(() => {
    const onTour = (e) => {
      const { open: o = true, mode: m } = e.detail || {};
      setOpen(!!o);
      if (o && m) setManualMode(m);
    };
    window.addEventListener('glucosphere:assistant', onTour);
    return () => window.removeEventListener('glucosphere:assistant', onTour);
  }, []);

  // Broadcast the panel's open/closed state so the guided tour can reposition its Resume
  // button (clear of the open slide-over) regardless of whether the panel was opened by the
  // tour or by the user clicking the FAB.
  useEffect(() => {
    window.dispatchEvent(new CustomEvent('glucosphere:assistant-state', { detail: { open } }));
  }, [open]);

  const pushMsg = (m, msg) => setThreads((t) => ({ ...t, [m]: [...t[m], msg] }));

  // Reset the CURRENT mode's thread + conversation id (fresh start, e.g. after an error).
  const resetChat = () => {
    if (busy) return;
    setThreads((t) => ({ ...t, [mode]: [{ role: 'assistant', kind: 'text', content: MODES[mode].greeting }] }));
    convIds.current[mode] = mode === 'genie' ? null : uuid();
  };

  const toggleEngine = () => {
    const next = engine === 'direct' ? 'mas' : 'direct';
    setEngineState(next);
    setEngine(next);
  };

  const send = async (text) => {
    const q = (text ?? input).trim();
    if (!q || busy) return;
    const activeMode = mode;
    setInput('');
    pushMsg(activeMode, { role: 'user', kind: 'text', content: q });
    setLoadingMode(activeMode);
    try {
      if (activeMode === 'mas') {
        const history = threads.mas
          .filter((m, i) => !(m.role === 'assistant' && i === 0))
          .map(({ role, content }) => ({ role, content: content || '' }));
        const res = await callAssistant(q, {
          engine,
          mode: 'chat',
          conversationHistory: history,
          conversationId: convIds.current.mas,
        });
        const content = res.response || res.choices?.[0]?.message?.content || res.content
          || (typeof res === 'string' ? res : "I couldn't generate a response. Please try again.");
        pushMsg('mas', { role: 'assistant', kind: 'text', content });
      } else {
        const resp = await fetch('/api/genie/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q, conversation_id: convIds.current.genie }),
        });
        if (!resp.ok) {
          const e = await resp.json().catch(() => ({}));
          throw new Error(e.error || `Genie query failed (${resp.status})`);
        }
        const data = await resp.json();
        if (data.conversation_id) convIds.current.genie = data.conversation_id;
        pushMsg('genie', { role: 'assistant', kind: 'genie', payload: data });
      }
    } catch (err) {
      pushMsg(activeMode, { role: 'assistant', kind: 'text', content: `⚠️ ${err.message}`, isError: true });
    } finally {
      setLoadingMode(null);
      inputRef.current?.focus();
    }
  };

  const onKey = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } };

  return (
    <>
      {/* Floating action button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Open assistant"
          data-tour="assistant-fab"
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 pl-4 pr-5 py-3 rounded-full bg-gradient-to-br from-cyan-500 to-blue-500 text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/40 hover:scale-105 transition-all"
        >
          <Sparkles className="w-5 h-5" />
          <span className="text-sm font-medium">Ask</span>
        </button>
      )}

      {/* Slide-over panel */}
      {open && (
        <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[440px] bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-200">Glucosphere Assistant</h3>
                <p className="text-xs text-slate-500 font-mono">{MODES[mode].label}</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button onClick={resetChat} disabled={busy} aria-label="Reset chat" title="Reset chat"
                className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40 p-1">
                <RotateCcw className="w-4 h-4" />
              </button>
              <button onClick={() => setOpen(false)} aria-label="Close assistant" className="text-slate-500 hover:text-slate-300 transition-colors p-1">
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* Mode toggle + (device-support) engine switch */}
          <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-800">
            {Object.entries(MODES).map(([key, m]) => {
              const Icon = m.icon;
              return (
                <button
                  key={key}
                  data-tour={key === 'genie' ? 'assistant-genie-tab' : undefined}
                  onClick={() => setManualMode(key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono border transition-colors ${
                    mode === key ? 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300' : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" /> {m.label}
                </button>
              );
            })}
            {/* Engine switch — only meaningful for the Device-support agent */}
            {mode === 'mas' && (
              <button
                data-tour="assistant-engine"
                onClick={toggleEngine}
                title={engine === 'direct' ? 'Fast router (Genie/KA/FM) — click for Multi-Agent Supervisor' : 'Multi-Agent Supervisor — click for fast router'}
                className={`ml-auto flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-mono border transition-colors ${
                  engine === 'direct' ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300' : 'bg-amber-500/10 border-amber-500/40 text-amber-300'
                }`}
              >
                {engine === 'direct' ? <><Zap className="w-3.5 h-3.5" /> Fast</> : <><Bot className="w-3.5 h-3.5" /> MAS</>}
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.map((msg, idx) => (
              <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
                    <Bot className="w-4 h-4 text-cyan-400" />
                  </div>
                )}
                <div className={`max-w-[85%] rounded-lg px-3 py-2.5 ${
                  msg.role === 'user' ? 'bg-cyan-500/20 border border-cyan-500/30 text-slate-100'
                    : msg.isError ? 'bg-rose-500/10 border border-rose-500/30 text-rose-300'
                    : 'bg-slate-800/50 border border-slate-700 text-slate-300'
                }`}>
                  {msg.role === 'assistant' && msg.kind === 'genie' ? (
                    <GenieResult payload={msg.payload} onFollowUp={(q) => send(q)} />
                  ) : msg.role === 'assistant' && !msg.isError ? (
                    <div className="text-sm max-w-none">
                      <ReactMarkdown components={mdComponents}>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                  )}
                </div>
                {msg.role === 'user' && (
                  <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-slate-700 border border-slate-600 flex items-center justify-center">
                    <User className="w-4 h-4 text-slate-300" />
                  </div>
                )}
              </div>
            ))}

            {loadingMode === mode && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0 w-7 h-7 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
                  <Bot className="w-4 h-4 text-cyan-400" />
                </div>
                <div className="bg-slate-800/50 border border-slate-700 rounded-lg px-3 py-2.5 flex items-center gap-2">
                  <Loader className="w-4 h-4 text-cyan-400 animate-spin" />
                  <span className="text-sm text-slate-400">{mode === 'genie' ? 'Querying Genie…' : 'Thinking…'}</span>
                </div>
              </div>
            )}

            {/* Suggestions (only the fresh greeting) */}
            {messages.length === 1 && (
              <div className="space-y-2">
                <p className="text-xs text-slate-500 font-mono">Try asking:</p>
                <div className="flex flex-wrap gap-2">
                  {MODES[mode].suggestions.map((s, i) => (
                    <button key={i} onClick={() => send(s)} className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-full text-xs text-slate-400 transition-colors">{s}</button>
                  ))}
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <div className="relative px-5 py-4 border-t border-slate-800">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={onKey}
              placeholder={mode === 'genie' ? 'Ask about the fleet data…' : 'Ask about device issues…'}
              rows="2"
              disabled={busy}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-3 pr-12 py-2.5 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-cyan-500 transition-colors resize-none"
            />
            <button
              onClick={() => send()}
              disabled={!input.trim() || busy}
              className="absolute right-7 bottom-7 p-2 bg-cyan-500 hover:bg-cyan-600 disabled:bg-slate-700 disabled:cursor-not-allowed rounded-lg transition-colors"
            >
              {busy ? <Loader className="w-4 h-4 text-white animate-spin" /> : <Send className="w-4 h-4 text-white" />}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
