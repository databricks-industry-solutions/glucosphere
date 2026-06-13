import { useEffect, useState } from 'react';
import { getConfig } from '../api/config';

// Feature flag for the Alert Triage page (Lakebase OLTP). Reads
// `lakebase_configured` from /api/config (cached promise — no extra round-trip).
// False until config resolves AND on any error, so non-Lakebase targets (and a
// briefly-loading app) render exactly the pre-Lakebase UI: wip labels, no /triage
// links, preview roadmap card.
export function useLakebaseConfigured() {
  const [configured, setConfigured] = useState(false);
  useEffect(() => {
    let alive = true;
    getConfig()
      .then(cfg => { if (alive) setConfigured(Boolean(cfg.lakebase_configured)); })
      .catch(() => { if (alive) setConfigured(false); });
    return () => { alive = false; };
  }, []);
  return configured;
}
