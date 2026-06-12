"""Lakebase (Autoscaling Postgres) helper — the App's OLTP layer for Alert Triage.

Feature-flagged: everything no-ops unless the deploy target rendered the Lakebase
binding (render_app_yaml.py sets LAKEBASE_ENDPOINT + the `database` app resource,
which injects PGHOST/PGUSER/PGDATABASE/PGSSLMODE and auto-creates the App SP's PG
role — but NO PGPASSWORD, by design). The password is a short-lived OAuth token
minted per ~50 min via POST /api/2.0/postgres/credentials (raw REST, matching
app.py's requests-based style; shape verified live — see
ref_notes/lakebase/2026-06-12_lakebase-autoscaling-app-connection-PROBE-PASS.md).

Schema (created idempotently on first use, in the app-owned `triage` PG schema —
PG 15+ denies CREATE in `public`; CAN_CONNECT_AND_CREATE lets the app make its own):
  triage.alerts       — one row per affected patient-device-faulttype; status open|acked|resolved
  triage.alert_audit  — append-only action trail (created/acked/assigned/resolved)
"""
import os
import time

import requests

LAKEBASE_ENDPOINT = os.getenv('LAKEBASE_ENDPOINT', '')

# Set by app.py at import time (lakebase.init(get_auth)) so the PG-credential mint
# reuses app.py's cached M2M workspace token instead of re-implementing OAuth.
_get_auth = None


def init(get_auth):
    global _get_auth
    _get_auth = get_auth


def is_configured() -> bool:
    """True only when the deploy target rendered the Lakebase binding
    (LAKEBASE_ENDPOINT env) AND the postgres resource injected PGHOST."""
    return bool(LAKEBASE_ENDPOINT and os.getenv('PGHOST'))


# ── PG credential (the password half; see module docstring) ────────────────────
_pg_cred_cache = {'token': '', 'expires_at': 0.0}


def _pg_password() -> str:
    now = time.time()
    if _pg_cred_cache['token'] and now < _pg_cred_cache['expires_at']:
        return _pg_cred_cache['token']
    host, ws_token = _get_auth()
    resp = requests.post(
        f"{host}/api/2.0/postgres/credentials",
        headers={'Authorization': f'Bearer {ws_token}'},
        json={'endpoint': LAKEBASE_ENDPOINT},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json().get('token', '')
    _pg_cred_cache['token'] = token
    _pg_cred_cache['expires_at'] = now + 3000  # ~50 min (tokens last ~1 h)
    return token


_schema_ready = False


def get_conn():
    """New psycopg connection (PG* env from the binding + minted password).
    Ensures the triage schema exists once per process. Caller closes (use `with`)."""
    import psycopg  # deferred: only Lakebase-configured targets exercise this path
    conn = psycopg.connect(
        host=os.environ['PGHOST'],
        port=int(os.environ.get('PGPORT', '5432')),
        dbname=os.environ.get('PGDATABASE', 'databricks_postgres'),
        user=os.environ['PGUSER'],
        password=_pg_password(),
        sslmode=os.environ.get('PGSSLMODE', 'require'),
        connect_timeout=20,
    )
    global _schema_ready
    if not _schema_ready:
        _ensure_schema(conn)
        _schema_ready = True
    return conn


_SCHEMA_SQL = """
-- Own schema: PG 15+ removed default CREATE on `public`; the binding's
-- CAN_CONNECT_AND_CREATE grants database-level CREATE (= create schemas),
-- so the app provisions its own namespace — no manual grants needed.
CREATE SCHEMA IF NOT EXISTS triage;
CREATE TABLE IF NOT EXISTS triage.alerts (
  alert_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  patient_id   TEXT NOT NULL,
  device_id    TEXT NOT NULL,
  device_model TEXT,
  firmware     TEXT,
  alert_type   TEXT NOT NULL,                   -- 'over-read' | 'under-read'
  severity     TEXT NOT NULL,                   -- 'HIGH' | 'MEDIUM'
  status       TEXT NOT NULL DEFAULT 'open',    -- open | acked | resolved
  assigned_to  TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (patient_id, device_id, alert_type)    -- makes seeding idempotent
);
CREATE TABLE IF NOT EXISTS triage.alert_audit (
  audit_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  alert_id  BIGINT NOT NULL REFERENCES triage.alerts(alert_id),
  action    TEXT NOT NULL,                      -- created | acked | assigned | resolved
  actor     TEXT,
  detail    TEXT,
  at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON triage.alerts(status);
CREATE INDEX IF NOT EXISTS idx_audit_alert ON triage.alert_audit(alert_id);
"""


def _ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute(_SCHEMA_SQL)
    conn.commit()


# ── Queue operations (called by app.py routes) ─────────────────────────────────
_ALERT_COLS = ('alert_id', 'patient_id', 'device_id', 'device_model', 'firmware',
               'alert_type', 'severity', 'status', 'assigned_to', 'created_at', 'updated_at')


def list_alerts(status: str | None = None, limit: int = 1000):
    """Alerts (optionally filtered by status) + per-status counts + audit trails."""
    where, params = '', []
    if status and status != 'all':
        where, params = 'WHERE status = %s', [status]
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT {', '.join(_ALERT_COLS)} FROM triage.alerts {where} "
            f"ORDER BY (status = 'open') DESC, severity = 'HIGH' DESC, updated_at DESC "
            f"LIMIT %s", params + [limit])
        alerts = [dict(zip(_ALERT_COLS, row)) for row in cur.fetchall()]
        cur.execute("SELECT status, COUNT(*) FROM triage.alerts GROUP BY status")
        counts = dict(cur.fetchall())
        ids = [a['alert_id'] for a in alerts]
        audits: dict[int, list] = {i: [] for i in ids}
        if ids:
            cur.execute(
                "SELECT alert_id, action, actor, detail, at FROM triage.alert_audit "
                "WHERE alert_id = ANY(%s) ORDER BY at", (ids,))
            for aid, action, actor, detail, at in cur.fetchall():
                audits[aid].append({'action': action, 'actor': actor,
                                    'detail': detail, 'at': str(at)})
        for a in alerts:
            a['audit'] = audits.get(a['alert_id'], [])
            a['created_at'] = str(a['created_at'])
            a['updated_at'] = str(a['updated_at'])
    return {'alerts': alerts, 'counts': counts}


_ACTIONS = {  # action → resulting status; None = audit-only (no status change)
    'ack': 'acked',
    'assign': 'acked',  # assign implies acked
    'resolve': 'resolved',
    'note': None,       # free-text addendum to the audit trail
}


def act_on_alert(alert_id: int, action: str, actor: str, detail: str | None = None):
    """Apply ack/assign/resolve/note + append the audit row. Returns the updated alert."""
    if action not in _ACTIONS:
        raise ValueError(f"unknown action {action!r} (expected one of {sorted(_ACTIONS)})")
    new_status = _ACTIONS[action]
    with get_conn() as conn, conn.cursor() as cur:
        if action == 'note':
            # audit-only: alert row untouched (just bump updated_at so sorts notice)
            cur.execute(
                "UPDATE triage.alerts SET updated_at=now() "
                "WHERE alert_id=%s RETURNING " + ', '.join(_ALERT_COLS), (alert_id,))
        elif action == 'assign':
            cur.execute(
                "UPDATE triage.alerts SET status=%s, assigned_to=%s, updated_at=now() "
                "WHERE alert_id=%s RETURNING " + ', '.join(_ALERT_COLS),
                (new_status, detail or 'unassigned', alert_id))
        else:
            cur.execute(
                "UPDATE triage.alerts SET status=%s, updated_at=now() "
                "WHERE alert_id=%s RETURNING " + ', '.join(_ALERT_COLS),
                (new_status, alert_id))
        row = cur.fetchone()
        if row is None:
            return None
        audit_action = 'note' if action == 'note' else action + ('ed' if not action.endswith('e') else 'd')
        cur.execute(
            "INSERT INTO triage.alert_audit (alert_id, action, actor, detail) VALUES (%s,%s,%s,%s)",
            (alert_id, audit_action, actor, detail))
        conn.commit()
    alert = dict(zip(_ALERT_COLS, row))
    alert['created_at'] = str(alert['created_at'])
    alert['updated_at'] = str(alert['updated_at'])
    return alert


def bulk_act(ids, action: str, actor: str, detail: str | None = None) -> int:
    """Bulk ack/resolve over a set of alert ids — the fleet move (one firmware
    rollback resolves a whole cohort). ack touches only open alerts; resolve
    touches anything unresolved. One audit row PER ALERT (the compliance trail
    stays per-device). Returns the number actually transitioned."""
    if action not in ('ack', 'resolve'):
        raise ValueError(f"bulk supports ack|resolve, got {action!r}")
    new_status = _ACTIONS[action]
    cond = "status = 'open'" if action == 'ack' else "status <> 'resolved'"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE triage.alerts SET status=%s, updated_at=now() "
            f"WHERE alert_id = ANY(%s) AND {cond} RETURNING alert_id",
            (new_status, list(ids)))
        done = [r[0] for r in cur.fetchall()]
        if done:
            audit_action = action + ('ed' if not action.endswith('e') else 'd')
            cur.execute(
                "INSERT INTO triage.alert_audit (alert_id, action, actor, detail) "
                "SELECT unnest(%s::bigint[]), %s, %s, %s",
                (done, audit_action, actor, detail))
        conn.commit()
    return len(done)


def reset_alerts():
    """Demo reset: wipe the queue + audit so booth visitors can triage fresh.
    Caller (the /api/alerts/reset route) reseeds immediately after. Disposable
    demo state by design — see the bundle-destroy footgun note in databricks.yml."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("TRUNCATE triage.alert_audit, triage.alerts RESTART IDENTITY")
        conn.commit()


def seed_alerts(rows, actor: str = 'seed'):
    """Idempotent bulk-insert of the affected cohort as open alerts.
    `rows` = iterable of (patient_id, device_id, device_model, firmware,
    alert_type, severity). ON CONFLICT (the UNIQUE key) skips → re-running is safe."""
    inserted = 0
    with get_conn() as conn, conn.cursor() as cur:
        for r in rows:
            cur.execute(
                "INSERT INTO triage.alerts (patient_id, device_id, device_model, firmware, alert_type, severity) "
                "VALUES (%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (patient_id, device_id, alert_type) DO NOTHING "
                "RETURNING alert_id", r)
            got = cur.fetchone()
            if got:
                cur.execute(
                    "INSERT INTO triage.alert_audit (alert_id, action, actor) VALUES (%s,'created',%s)",
                    (got[0], actor))
                inserted += 1
        conn.commit()
    return inserted
