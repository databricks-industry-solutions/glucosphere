// Alert Triage API client — the Lakebase-backed queue (Flask routes in
// App/databricks/app.py; storage = Postgres, see App/databricks/lakebase.py).
// All routes are flag-gated server-side: on targets without the Lakebase
// binding they return 503, and the UI never calls them (links/page are hidden
// behind useLakebaseConfigured) — belt and braces.

async function asJson(resp) {
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(body.error || `${resp.status} ${resp.statusText}`);
  return body;
}

/** Queue + per-status counts + per-alert audit trails. status: open|acked|resolved|all */
export async function fetchAlerts(status = 'all') {
  return asJson(await fetch(`/api/alerts?status=${encodeURIComponent(status)}`));
}

/** action: ack | assign | resolve. assignee only used for assign. Returns the updated alert. */
export async function alertAction(alertId, action, assignee = null) {
  return asJson(await fetch(`/api/alerts/${alertId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(assignee ? { assignee } : {}),
  }));
}

/** Idempotent seed from the gold layer's affected cohort (UNIQUE key → re-runs no-op). */
export async function seedAlerts() {
  return asJson(await fetch('/api/alerts/seed', { method: 'POST' }));
}

/** Booth demo reset: wipe queue + audit, reseed fresh open alerts (disposable demo state). */
export async function resetAlerts() {
  return asJson(await fetch('/api/alerts/reset', { method: 'POST' }));
}
