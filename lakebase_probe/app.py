# Throwaway Lakebase-Autoscaling connection probe (dev/lakebase-integration).
# Proves the #1 integration risk: can THIS app's service principal reach the
# Autoscaling Postgres (projects/test) — via (A) the declarative app->postgres
# resource binding's injected env vars, and/or (B) an SDK-minted OAuth credential.
# Reports everything as JSON at "/" and prints the same to app logs at startup.
# DELETE after the probe (teardown: app + nothing else — the DB is May's manual project).
import json
import os
import traceback

from flask import Flask, jsonify

app = Flask(__name__)

REDACT = ("SECRET", "TOKEN", "PASSWORD", "PGPASSWORD")


def env_survey():
    """All PG*/LAKEBASE*/DATABRICKS* env vars, secret-ish values redacted."""
    out = {}
    for k in sorted(os.environ):
        if k.startswith(("PG", "LAKEBASE", "DATABRICKS")):
            v = os.environ[k]
            out[k] = (v[:8] + f"…REDACTED({len(v)})") if any(s in k.upper() for s in REDACT) else v
    return out


def attempt_env_connect():
    """(A) Declarative-binding path: psycopg honors libpq PG* env vars directly."""
    step = {"attempt": "A-injected-PG-env", "pghost": os.environ.get("PGHOST")}
    try:
        import psycopg
        if not os.environ.get("PGHOST"):
            step["result"] = "SKIP — no PGHOST injected"
            return step
        with psycopg.connect("", connect_timeout=15) as conn:  # "" -> libpq env vars
            with conn.cursor() as cur:
                cur.execute("SELECT version(), current_user, current_database()")
                v, u, d = cur.fetchone()
        step.update(result="PASS", version=v, connected_as=u, database=d)
    except Exception as e:
        step.update(result="FAIL", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
    return step


def attempt_sdk_mint():
    """(B) SDK path: introspect WorkspaceClient (no guessed names), mint cred, connect."""
    step = {"attempt": "B-sdk-mint"}
    try:
        from databricks.sdk import WorkspaceClient
        w = WorkspaceClient()
        step["sdk_namespaces"] = [n for n in dir(w) if "post" in n.lower() or "database" in n.lower()]
        pg = getattr(w, "postgres", None)
        if pg is None:
            step["result"] = "FAIL — WorkspaceClient has no `postgres` namespace (SDK too old?)"
            return step
        step["postgres_methods"] = [m for m in dir(pg) if not m.startswith("_")]
        endpoint = os.environ.get("LAKEBASE_ENDPOINT", "")
        mint = getattr(pg, "generate_database_credential", None)
        if mint is None:
            step["result"] = "FAIL — no generate_database_credential on w.postgres"
            return step
        cred = mint(endpoint=endpoint)
        token = getattr(cred, "token", None)
        step["minted"] = bool(token)
        step["expire_time"] = str(getattr(cred, "expire_time", "?"))

        import psycopg
        sp_id = os.environ.get("DATABRICKS_CLIENT_ID", "")
        host = os.environ.get("LAKEBASE_HOST", "")
        dbname = os.environ.get("LAKEBASE_DB", "databricks_postgres")
        tried = []
        for user in [u for u in (os.environ.get("PGUSER"), sp_id) if u]:
            try:
                with psycopg.connect(host=host, dbname=dbname, user=user,
                                     password=token, sslmode="require", connect_timeout=15) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT version(), current_user, current_database()")
                        v, u2, d = cur.fetchone()
                step.update(result="PASS", version=v, connected_as=u2, database=d, user_tried=user)
                return step
            except Exception as e:
                tried.append({"user": user, "error": f"{type(e).__name__}: {e}"})
        step.update(result="FAIL", connect_attempts=tried)
    except Exception as e:
        step.update(result="FAIL", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-1500:])
    return step


def run_probe():
    report = {"env": env_survey(), "steps": [attempt_env_connect(), attempt_sdk_mint()]}
    report["verdict"] = "PASS" if any(s.get("result") == "PASS" for s in report["steps"]) else "FAIL"
    return report


@app.route("/")
def probe():
    return jsonify(run_probe())


if __name__ == "__main__":
    # Print once at startup so `databricks apps logs` carries the result even if
    # nobody can curl the OAuth-gated app URL.
    print("=== LAKEBASE PROBE (startup) ===")
    print(json.dumps(run_probe(), indent=2, default=str))
    print("=== END PROBE ===")
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8080")))
