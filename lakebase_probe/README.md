# lakebase_probe — App-SP → Lakebase connection probe (reference)

A throwaway single-file Flask app, kept as a **reference**, that proved the riskiest part
of the Lakebase integration before any feature code was written: *can a Databricks App's
service principal actually reach a Lakebase Autoscaling Postgres?* It validated the exact
pattern the production app now uses (`App/databricks/lakebase.py`).

It tests two paths independently and reports both as JSON at `/` (and in the app logs):

- **A — declarative binding**: the app's `postgres` resource binding injects libpq
  `PGHOST` / `PGUSER` / `PGDATABASE` / `PGSSLMODE` (note: **no `PGPASSWORD`**) and
  auto-creates the app SP's Postgres role; `psycopg.connect("")` honors those env vars.
- **B — minted credential**: a short-lived OAuth token from
  `POST /api/2.0/postgres/credentials {"endpoint": …}` used as the PG password (~1 h
  expiry — the production app caches it ~50 min).

The verified outcome (2026-06): **A's env injection + B's token as password** is the
working combination — the binding provides identity + coordinates, the minted credential
provides the password.

## Prerequisites

1. A Lakebase **Autoscaling** Postgres project to probe against — create a disposable one
   manually (UI: **SQL → Database Projects**) or via CLI:

   ```bash
   databricks postgres create-project <your-test-project-id> --profile <profile> --json \
     '{"spec": {"pg_version": 17, "default_endpoint_settings":
       {"autoscaling_limit_min_cu": 0.5, "autoscaling_limit_max_cu": 1,
        "suspend_timeout_duration": "600s"}}}'
   ```

2. Fill the placeholders in `app.yaml` (`LAKEBASE_ENDPOINT`, `LAKEBASE_HOST` — get the
   host from `databricks postgres get-endpoint projects/<id>/branches/production/endpoints/primary`).

## Run it

```bash
# create the app WITH the postgres binding (resources must go on the app object —
# app.yaml's `resources:` section is NOT applied by app deploys):
databricks apps create --json '{
  "name": "lakebase-probe",
  "resources": [{
    "name": "database",
    "postgres": {
      "branch": "projects/<your-test-project-id>/branches/production",
      "database": "projects/<your-test-project-id>/branches/production/databases/databricks-postgres",
      "permission": "CAN_CONNECT_AND_CREATE"
    }
  }]
}' --profile <profile>

databricks workspace import-dir lakebase_probe /Workspace/Users/<you>/lakebase_probe --profile <profile>
databricks apps deploy lakebase-probe --source-code-path /Workspace/Users/<you>/lakebase_probe --profile <profile>
```

Open the app URL: a JSON report with an env survey (secrets redacted) plus the A/B
attempt results. Both `"result": "PASS"` = the integration pattern works for this
workspace/SP.

## Gotchas this probe surfaced

- Database resource id is `databricks-postgres` (hyphen) while the PG database *name* is
  `databricks_postgres` (underscore).
- `apps create --json` requires the app `name` inside the JSON body.
- Bind to the runtime-injected `DATABRICKS_APP_PORT` (the probe falls back to 8080
  when it's absent — see `app.py`'s last line).

## Teardown

```bash
databricks apps delete lakebase-probe --profile <profile>
databricks postgres delete-project projects/<your-test-project-id> --profile <profile>
# (deletion is soft — the id stays reserved ~7 days; undelete via
#  POST /api/2.0/postgres/projects/<id>/undelete)
```

## See also

- `App/databricks/lakebase.py` — the production implementation (token cache, app-owned
  `triage` schema, SP-rotation proofing).
- `DEPLOY.md` → *Lakebase one-time setup* — how real deploy targets wire Lakebase.
- `AGENTS.md` §10 — the full gotcha list for agents working on this integration.
