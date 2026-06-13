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

/** The alerts ⋈ audit join, newest first — the in-app "Verify in Postgres" peek. */
export async function fetchRawRows(limit = 12) {
  return asJson(await fetch(`/api/alerts/raw?limit=${limit}`));
}

/** Queue + per-status counts + per-alert audit trails. status: open|acked|resolved|all */
export async function fetchAlerts(status = 'all') {
  return asJson(await fetch(`/api/alerts?status=${encodeURIComponent(status)}`));
}

/** action: ack | assign | resolve | note | followup. `detail` = assignee (assign),
 * addendum text (note — audit-only), resolution outcome (resolve), or the
 * follow-up request (followup — keeps the alert working, status → acked).
 * Returns the updated alert. */
export async function alertAction(alertId, action, detail = null) {
  const body = action === 'assign' && detail ? { assignee: detail }
    : action === 'note' && detail ? { note: detail }
    : action === 'resolve' && detail ? { resolution: detail }
    : action === 'followup' && detail ? { followup: detail }
    : {};
  return asJson(await fetch(`/api/alerts/${alertId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }));
}

/** Idempotent seed from the gold layer's affected cohort (UNIQUE key → re-runs no-op). */
export async function seedAlerts() {
  return asJson(await fetch('/api/alerts/seed', { method: 'POST' }));
}

/** Bulk ack/resolve over alert ids — the fleet move (rollback resolves a cohort).
 * `resolution` only used for resolve. Returns {requested, transitioned}. */
export async function bulkAlerts(ids, action, resolution = null) {
  return asJson(await fetch('/api/alerts/bulk', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(resolution ? { ids, action, resolution } : { ids, action }),
  }));
}

/** Booth demo reset: wipe queue + audit, reseed fresh open alerts (disposable demo state). */
export async function resetAlerts() {
  return asJson(await fetch('/api/alerts/reset', { method: 'POST' }));
}
