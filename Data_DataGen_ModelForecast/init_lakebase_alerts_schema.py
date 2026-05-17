# Databricks notebook source
# MAGIC %md
# MAGIC # Initialize Lakebase Alert State Cache Schema
# MAGIC
# MAGIC Plan's Commit F (#42) — step 2: create the `alerts` + `alert_transitions` tables
# MAGIC in the Lakebase Postgres instance. Idempotent — safe to re-run.
# MAGIC
# MAGIC **Inputs (widgets):**
# MAGIC - `LAKEBASE_INSTANCE_NAME` — Lakebase database_instance name (default matches mmt_aws_usw2 target)
# MAGIC - `PG_SCHEMA` — Postgres schema to hold the tables (default `glucosphere`)
# MAGIC
# MAGIC **What this creates:**
# MAGIC - `<PG_SCHEMA>.alerts` — mutable alert lifecycle state
# MAGIC - `<PG_SCHEMA>.alert_transitions` — append-only audit log of state changes
# MAGIC - Indexes on alerts(status, severity) / lot_id / detected_at
# MAGIC
# MAGIC **Connection pattern:** Databricks OAuth via WorkspaceClient → standard psycopg2
# MAGIC connection. App SP will use the same pattern for runtime reads/writes (task #42 step 3).

# COMMAND ----------

# MAGIC %pip install psycopg2-binary --quiet
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

dbutils.widgets.text("LAKEBASE_INSTANCE_NAME", "glucosphere-oltp-mmt-aws-usw2", "Lakebase database_instance name")
dbutils.widgets.text("PG_SCHEMA", "glucosphere", "Postgres schema for alerts tables")

LAKEBASE_INSTANCE_NAME = dbutils.widgets.get("LAKEBASE_INSTANCE_NAME")
PG_SCHEMA = dbutils.widgets.get("PG_SCHEMA")

print(f"Initializing Lakebase alerts schema")
print(f"  instance: {LAKEBASE_INSTANCE_NAME}")
print(f"  schema:   {PG_SCHEMA}")

# COMMAND ----------

# Resolve instance DNS endpoint + mint Postgres credential via Lakebase REST API.
#
# Two-step auth flow:
#   1. WorkspaceClient handles workspace-level auth (picks up notebook context on
#      serverless + classic compute; databricks-sdk-py >= 0.20 handles this cleanly).
#      Doesn't have `.database` attribute as of 2026-05-17, so we hit the raw API.
#   2. `POST /api/2.0/database/credentials` mints a short-lived (~10 min) JWT that
#      Postgres accepts as a password. The workspace OAuth token would NOT work directly
#      as a PG password (Lakebase rejects with "not a valid JWT encoding") — caught on
#      first attempt 2026-05-17.
import requests
import uuid
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Step 1: instance metadata (DNS endpoint)
instance = w.api_client.do(
    'GET',
    f'/api/2.0/database/instances/{LAKEBASE_INSTANCE_NAME}',
)
PG_HOST = instance["read_write_dns"]
PG_PORT = 5432
PG_DATABASE = "databricks_postgres"

# Step 2: mint a Lakebase-specific Postgres credential
cred = w.api_client.do(
    'POST',
    '/api/2.0/database/credentials',
    body={
        'instance_names': [LAKEBASE_INSTANCE_NAME],
        'request_id': str(uuid.uuid4()),
    },
)
PG_PASSWORD = cred['token']  # ~922-char JWT, expires in ~10 min
cred_expiry = cred.get('expiration_time', '?')

current_user = w.current_user.me().user_name

print(f"  host:        {PG_HOST}")
print(f"  port:        {PG_PORT}")
print(f"  user:        {current_user}")
print(f"  pg cred:     <{len(PG_PASSWORD)} chars, expires {cred_expiry}>")

# COMMAND ----------

import psycopg2
from psycopg2 import sql

conn = psycopg2.connect(
    host=PG_HOST,
    port=PG_PORT,
    database=PG_DATABASE,
    user=current_user,
    password=PG_PASSWORD,
    sslmode="require",
)
conn.autocommit = True  # DDL outside transactions — simpler error semantics

with conn.cursor() as cur:
    # Ensure the target schema exists
    cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(PG_SCHEMA)))
    print(f"[ok] schema {PG_SCHEMA} ensured")

    # Required extension for gen_random_uuid()
    cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    print("[ok] pgcrypto extension ensured (for gen_random_uuid)")

    # alerts table — mutable alert lifecycle state
    cur.execute(sql.SQL("""
        CREATE TABLE IF NOT EXISTS {schema}.alerts (
            alert_id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            detected_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            severity               TEXT CHECK (severity IN ('low','medium','high','critical')),
            bias_direction         TEXT CHECK (bias_direction IN ('positive','negative')),
            bias_magnitude_mgdl    REAL,
            lot_id                 TEXT,
            firmware_version       TEXT,
            affected_patient_count INT,
            status                 TEXT NOT NULL DEFAULT 'open'
                                   CHECK (status IN ('open','acknowledged','resolved','closed')),
            acknowledged_by        TEXT,
            acknowledged_at        TIMESTAMPTZ,
            resolved_at            TIMESTAMPTZ,
            note                   TEXT
        )
    """).format(schema=sql.Identifier(PG_SCHEMA)))
    print(f"[ok] table {PG_SCHEMA}.alerts ensured")

    # Indexes for common query patterns (dashboard open-alerts list, per-lot drill, time-sort)
    for idx_name, cols in [
        ("idx_alerts_status_severity", "(status, severity)"),
        ("idx_alerts_lot_id",           "(lot_id)"),
        ("idx_alerts_detected_at",      "(detected_at DESC)"),
    ]:
        cur.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {idx} ON {schema}.alerts {cols}").format(
            idx=sql.Identifier(idx_name),
            schema=sql.Identifier(PG_SCHEMA),
            cols=sql.SQL(cols),
        ))
    print(f"[ok] alerts indexes ensured (status_severity, lot_id, detected_at)")

    # alert_transitions — append-only audit log of state changes
    cur.execute(sql.SQL("""
        CREATE TABLE IF NOT EXISTS {schema}.alert_transitions (
            transition_id  SERIAL PRIMARY KEY,
            alert_id       UUID NOT NULL REFERENCES {schema}.alerts(alert_id),
            from_status    TEXT,
            to_status      TEXT,
            actor          TEXT,
            occurred_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            note           TEXT
        )
    """).format(schema=sql.Identifier(PG_SCHEMA)))
    print(f"[ok] table {PG_SCHEMA}.alert_transitions ensured")

    cur.execute(sql.SQL("CREATE INDEX IF NOT EXISTS idx_transitions_alert_id ON {schema}.alert_transitions(alert_id)").format(
        schema=sql.Identifier(PG_SCHEMA)
    ))
    print(f"[ok] alert_transitions index ensured (alert_id)")

# COMMAND ----------

# Verify by inspecting the schema
with conn.cursor() as cur:
    cur.execute(sql.SQL("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s
        ORDER BY table_name, ordinal_position
    """), [PG_SCHEMA])
    rows = cur.fetchall()

print(f"\nVerification — columns in {PG_SCHEMA}:")
prev_tbl = None
for tbl, col, typ in rows:
    if tbl != prev_tbl:
        print(f"\n  {tbl}:")
        prev_tbl = tbl
    print(f"    {col:25s} {typ}")

# Also count any existing rows (should be 0 on first run)
with conn.cursor() as cur:
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {schema}.alerts").format(schema=sql.Identifier(PG_SCHEMA)))
    n_alerts = cur.fetchone()[0]
    cur.execute(sql.SQL("SELECT COUNT(*) FROM {schema}.alert_transitions").format(schema=sql.Identifier(PG_SCHEMA)))
    n_transitions = cur.fetchone()[0]
print(f"\nRow counts: alerts={n_alerts}, alert_transitions={n_transitions}")

conn.close()
print("\n[SUCCESS] Lakebase alerts schema initialized.")
