#!/usr/bin/env python3
"""
grant_app_sp.py — Entitle a Databricks App's service principal on the resources
the Glucosphere app needs at runtime.

WHY THIS EXISTS
    `databricks apps create` (and a standalone `apps deploy`) mints a fresh
    service principal for the app but grants it NOTHING. Until the SP is granted
    access, every data/agent call from the app returns 403 PERMISSION_DENIED
    (blank metrics, "no data", and `403` from the MAS/Genie assistants). Bundle-
    managed apps may pick some of this up, but standalone app instances (e.g. the
    A/B `glucosphere-app-v0-N` apps) do NOT — so this step is required for them.

WHAT IT GRANTS (idempotent — safe to re-run)
    Looks up the app's `service_principal_client_id`, derives the resource ids
    from App/databricks/app.yaml (no hardcoding), and applies:
      - UC:               USE CATALOG <catalog>; USE SCHEMA + SELECT on <catalog>.<schema>
      - SQL warehouse:    CAN_USE
      - serving endpoints (MAS + KA + FM): CAN_QUERY
      - Genie space:      CAN_RUN
    Grants take effect per-request — no app redeploy needed afterward.

RUN SEQUENCE
    databricks apps deploy <app> --source-code-path <ws-path> -p <profile>
    uv run python scripts/grant_app_sp.py --app <app> --profile <profile>

USAGE
    uv run python scripts/grant_app_sp.py --app glucosphere-app-v0-3 --profile fevm-mmt-aws-usw2
    # profile defaults to $DATABRICKS_CONFIG_PROFILE (e.g. via `source .env.bundle`)
    # --dry-run prints the planned grants without applying them
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_YAML = REPO_ROOT / "App" / "databricks" / "app.yaml"
# Run the CLI from a NON-bundle dir: this script issues no `databricks bundle`
# commands, and running `apps`/`permissions`/`api` from the repo (which holds
# databricks.yml) makes the CLI demand a bundle target ("please specify target").
NEUTRAL_CWD = tempfile.gettempdir()


def run_cli(args: list[str], profile: str | None, check: bool = True) -> str:
    """Run a `databricks` CLI command and return stdout (raises on failure if check)."""
    cmd = ["databricks", *args]
    if profile:
        cmd += ["-p", profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=NEUTRAL_CWD)
    if result.returncode != 0:
        msg = f"[FATAL] `{' '.join(cmd)}` failed:\n{result.stderr.strip()}"
        if check:
            print(msg, file=sys.stderr)
            sys.exit(result.returncode)
        raise RuntimeError(msg)
    return result.stdout


def app_yaml_env(content: str) -> dict[str, str]:
    """Extract the `env:` name/value pairs from app.yaml."""
    env = {}
    for m in re.finditer(r"-\s*name:\s*(\w+)\s*\n\s*value:\s*['\"]?([^'\"\n]*)['\"]?", content):
        env[m.group(1)] = m.group(2).strip()
    return env


def app_yaml_serving_endpoints(content: str) -> list[str]:
    """Extract serving_endpoint names from the resources block (MAS + KA)."""
    return re.findall(r"serving_endpoint:\s*\n\s*name:\s*(\S+)", content)


def main() -> None:
    ap = argparse.ArgumentParser(description="Grant a Databricks App's SP the Glucosphere runtime resources.")
    ap.add_argument("--app", required=True, help="App name, e.g. glucosphere-app-v0-3")
    ap.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
                    help="CLI profile (default: $DATABRICKS_CONFIG_PROFILE)")
    ap.add_argument("--dry-run", action="store_true", help="Print planned grants without applying")
    args = ap.parse_args()
    profile = args.profile

    # 1. App SP client id ----------------------------------------------------
    app = json.loads(run_cli(["apps", "get", args.app, "-o", "json"], profile))
    sp = app.get("service_principal_client_id")
    if not sp:
        print(f"[FATAL] no service_principal_client_id on app {args.app}", file=sys.stderr)
        sys.exit(1)

    # 2. Resource ids from app.yaml -----------------------------------------
    content = APP_YAML.read_text()
    env = app_yaml_env(content)
    catalog = env.get("CATALOG_NAME")
    schema = env.get("SCHEMA_NAME")
    warehouse_id = env.get("WAREHOUSE_ID")
    genie_id = env.get("GENIE_SPACE_ID")
    endpoints = app_yaml_serving_endpoints(content)  # MAS + KA names
    missing = [k for k, v in {"CATALOG_NAME": catalog, "SCHEMA_NAME": schema,
                              "WAREHOUSE_ID": warehouse_id, "GENIE_SPACE_ID": genie_id}.items() if not v]
    if missing:
        print(f"[FATAL] app.yaml missing {missing} — run scripts/render_app_yaml.py first", file=sys.stderr)
        sys.exit(1)

    print(f"App SP:        {sp}  ({args.app})")
    print(f"Catalog.schema {catalog}.{schema}")
    print(f"Warehouse:     {warehouse_id}")
    print(f"Endpoints:     {endpoints}")
    print(f"Genie space:   {genie_id}")
    if args.dry_run:
        print("\n[dry-run] no grants applied.")
        return

    # 3. UC grants (run as SQL on the warehouse; backticks are safe via subprocess args) ---
    for stmt in (
        f"GRANT USE CATALOG ON CATALOG {catalog} TO `{sp}`",
        f"GRANT USE SCHEMA ON SCHEMA {catalog}.{schema} TO `{sp}`",
        f"GRANT SELECT ON SCHEMA {catalog}.{schema} TO `{sp}`",
        # READ VOLUME powers the app's /uc-assets/ PNG route (mirrors notebook
        # 09_grant_app_permissions.py). Non-fatal if the volume isn't present:
        # the statements API returns a FAILED state in-body (CLI exit 0).
        f"GRANT READ VOLUME ON VOLUME {catalog}.{schema}.pipeline_data TO `{sp}`",
    ):
        payload = json.dumps({"warehouse_id": warehouse_id, "statement": stmt, "wait_timeout": "30s"})
        out = run_cli(["api", "post", "/api/2.0/sql/statements", "--json", payload], profile)
        state = json.loads(out).get("status", {}).get("state", "?")
        print(f"  [{state}] {stmt}")

    # 4. Warehouse CAN_USE ---------------------------------------------------
    acl = json.dumps({"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_USE"}]})
    run_cli(["permissions", "update", "warehouses", warehouse_id, "--json", acl], profile)
    print(f"  [ok] warehouse {warehouse_id}: CAN_USE")

    # 5. Serving endpoints CAN_QUERY (resolve name -> id) --------------------
    q_acl = json.dumps({"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_QUERY"}]})
    for name in endpoints:
        ep = json.loads(run_cli(["serving-endpoints", "get", name, "-o", "json"], profile))
        ep_id = ep.get("id")
        if not ep_id:
            print(f"  [skip] endpoint {name}: no id", file=sys.stderr)
            continue
        run_cli(["permissions", "update", "serving-endpoints", ep_id, "--json", q_acl], profile)
        print(f"  [ok] endpoint {name} ({ep_id}): CAN_QUERY")

    # 6. Genie space CAN_RUN -------------------------------------------------
    g_acl = json.dumps({"access_control_list": [{"service_principal_name": sp, "permission_level": "CAN_RUN"}]})
    run_cli(["api", "patch", f"/api/2.0/permissions/genie/{genie_id}", "--json", g_acl], profile)
    print(f"  [ok] genie space {genie_id}: CAN_RUN")

    print(f"\n✅ {args.app} SP entitled. Grants are effective per-request — no redeploy needed.")


if __name__ == "__main__":
    main()
