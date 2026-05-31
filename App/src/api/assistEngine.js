// Shared assistant-engine preference, persisted in localStorage so the chat toggle and
// the Clinical-Analysis drill-down agree on which engine to use.
//   'direct' = fast app-side router (FM / KA / Genie, one direct call)
//   'mas'    = the Multi-Agent Supervisor (kept available for live A/B at the booth)
const KEY = 'glucosphere.assistEngine';

export const getEngine = () => {
  try { return localStorage.getItem(KEY) === 'mas' ? 'mas' : 'direct'; } catch { return 'direct'; }
};

export const setEngine = (v) => {
  try { localStorage.setItem(KEY, v === 'mas' ? 'mas' : 'direct'); } catch { /* ignore */ }
};
