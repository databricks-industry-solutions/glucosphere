#!/usr/bin/env python3
"""
smoke_test.py — Pre-PR automated smoke test for the deployed glucosphere App.

Validates the deployed state of the live target end-to-end (deploy + data + agent
endpoints + Genie space). Run after `databricks bundle run glucosphere_app …`
completes (DEPLOY.md Step 9). Catches the backend failure modes that the manual
browser-driven checks in DEPLOY.md Step 10 also catch, without needing SSO auth.

What's automated (8 checks + a 9th on Lakebase-enabled targets):
    1. App state: `databricks api get /api/2.0/apps/<name>` → compute_status.state == ACTIVE
       and app_status.state == RUNNING.
    2. App URL: HEAD request to the App URL → non-5xx response (auth redirect is fine —
       proves the App is serving HTTP).
    3. Warehouse: `databricks warehouses list` contains `glucosphere-warehouse-<target>`
       (create-own targets), OR the reused warehouse id exists (reuse targets that set
       `existing_warehouse_id`, e.g. the DAIS booth — pass `--warehouse-id` or let it resolve).
    4. Gold table: `SELECT COUNT(*) FROM <catalog>.<schema>.gold_patient_device_readings`
       returns > 0 (proves DLT silver/gold pipeline succeeded + SP can read).
    5. KA + MAS serving endpoints: the App's ACTUAL `mas_endpoint`/`ka_endpoint`
       (resolved bundle vars — the same values render writes into app.yaml) both exist
       AND are READY. Falls back to a prefix-existence check (and WARNS) only when those
       vars aren't set (e.g. the ids were passed to render as one-off --flags); a bare
       prefix match is ambiguous when the workspace holds multiple mas-/ka- endpoints
       (e.g. a `_fw_v2` sandbox set alongside the live agents — exactly that case bit us
       2026-06-06: prefix-match silently validated the sandbox pair, not the App's).
    6. Genie space: matches the App's resolved `genie_space_id` (falls back to a
       display-name substring match, and WARNS, only when that var isn't set).
    7. Firmware variety: gold table has >= 3 distinct firmware_version values
       (catches the demo_week_start vs firmware-event-timestamp drift regression —
       2026-05-28 cycle 2 silently dropped from 3 → 2 firmware values).
    8. MetricsExplained PNG: UC Files API GET of
       `/Volumes/<catalog>/<schema>/pipeline_data/incident_inference_assets/distribution_comparison_4panel.png`
       returns 200 + image/png bytes (catches the silent try/except in
       05_incident_inference_bidirectional.py PNG-save block — cycle 2 incident_inference
       task showed SUCCESS while the PNG was never written).
    9. Lakebase (only when the target sets `lakebase_project_id`; skipped otherwise):
       the bundle-managed Autoscaling project exists AND the App carries the postgres
       resource binding to it. Doubles as the DRIFT detector — a CLI/UI-deleted
       project fails here while `bundle deploy` stays silent (no state refresh);
       recovery: `POST /api/2.0/postgres/projects/<id>/undelete` + app restart.

NOT covered (still needs the manual DEPLOY.md Step 10 checklist):
    - React UI build artifacts loading correctly
    - End-to-end agent query roundtrip (`/api/agent/query`) — requires App SSO auth
    - End-to-end Genie NL query roundtrip (`/api/genie/query`) — requires App SSO auth

Usage:
    uv run python scripts/smoke_test.py --target gsphere
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request


# Databricks CLI v1.x rejects the old auth-cache format with
# "stored credentials from older CLI versions are no longer used".
# Setting DATABRICKS_AUTH_STORAGE=plaintext in the subprocess env opts into
# the v1.x-compatible storage path. Harmless on older CLI versions.
_DATABRICKS_ENV = {**os.environ, "DATABRICKS_AUTH_STORAGE": "plaintext"}


def _databricks(cmd_args: list[str], profile: str) -> dict | list:
    """Run a `databricks` CLI command and return parsed JSON output."""
    cmd = ["databricks", *cmd_args, "--profile", profile, "-o", "json"]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, env=_DATABRICKS_ENV)
    return json.loads(out)


def _databricks_api(method: str, path: str, profile: str, body: dict | None = None) -> dict:
    cmd = ["databricks", "api", method.lower(), path, "--profile", profile]
    if body is not None:
        cmd.extend(["--json", json.dumps(body)])
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, env=_DATABRICKS_ENV)
    return json.loads(out)


def check_app_state(app_name: str, profile: str) -> tuple[bool, str]:
    d = _databricks_api("GET", f"/api/2.0/apps/{app_name}", profile)
    compute = d.get("compute_status", {}).get("state", "?")
    appst = d.get("app_status", {}).get("state", "?")
    url = d.get("url", "")
    ok = compute == "ACTIVE" and appst == "RUNNING"
    return ok, f"compute={compute}, app_status={appst}, url={url}"


def check_app_serving(app_name: str, profile: str) -> tuple[bool, str]:
    d = _databricks_api("GET", f"/api/2.0/apps/{app_name}", profile)
    url = d.get("url", "")
    if not url:
        return False, "no URL on App resource"
    req = urllib.request.Request(url, method="HEAD")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return True, f"HTTP {resp.status} from {url}"
    except urllib.error.HTTPError as e:
        # 4xx (auth redirect) is acceptable — proves the App is responding.
        return e.code < 500, f"HTTP {e.code} from {url}"
    except Exception as e:
        return False, f"network error: {e}"


def check_warehouse(target: str, profile: str, warehouse_id: str | None = None) -> tuple[bool, str]:
    d = _databricks(["warehouses", "list"], profile)
    whs = d.get("warehouses", []) if isinstance(d, dict) else d
    if warehouse_id:  # reuse target (e.g. dais): verify the supplied warehouse exists by id
        match = next((w for w in whs if w.get("id") == warehouse_id), None)
        if match is None:
            return False, f"reused warehouse id {warehouse_id!r} not found"
        return True, f"(reused) name={match['name']!r}, id={match.get('id')!r}, state={match.get('state')!r}"
    expected = f"glucosphere-warehouse-{target}"
    match = next((w for w in whs if w.get("name", "").endswith(expected)), None)
    if match is None:
        return False, f"no warehouse matching '*{expected}' found"
    return True, f"name={match['name']!r}, id={match.get('id')!r}, state={match.get('state')!r}"


def check_gold_table(catalog: str, schema: str, warehouse_id: str, profile: str) -> tuple[bool, str]:
    body = {
        "warehouse_id": warehouse_id,
        "statement": f"SELECT COUNT(*) AS n FROM {catalog}.{schema}.gold_patient_device_readings",
        "wait_timeout": "30s",
    }
    d = _databricks_api("POST", "/api/2.0/sql/statements", profile, body)
    status = d.get("status", {}).get("state", "?")
    if status != "SUCCEEDED":
        err = d.get("status", {}).get("error", {}).get("message", "")[:200]
        return False, f"status={status}, error={err!r}"
    rows = d.get("result", {}).get("data_array", [])
    if not rows:
        return False, "0 rows in result"
    n = int(rows[0][0])
    return n > 0, f"COUNT(*) = {n}"


def _warehouse_id(target: str, profile: str, warehouse_id: str | None = None) -> str | None:
    if warehouse_id:  # reuse target: use the supplied id directly
        return warehouse_id
    d = _databricks(["warehouses", "list"], profile)
    whs = d.get("warehouses", []) if isinstance(d, dict) else d
    expected = f"glucosphere-warehouse-{target}"
    match = next((w for w in whs if w.get("name", "").endswith(expected)), None)
    return match.get("id") if match else None


def _endpoint_ready(name: str, profile: str) -> str:
    """Return a serving endpoint's `state.ready` ('READY' / 'NOT_READY' / 'MISSING')."""
    try:
        d = _databricks(["serving-endpoints", "get", name], profile)
    except subprocess.CalledProcessError:
        return "MISSING"
    return (d.get("state") or {}).get("ready", "?")


def check_serving_endpoints(profile: str, mas_endpoint: str = "", ka_endpoint: str = "") -> tuple[bool, str]:
    """Verify the App's ACTUAL MAS + KA endpoints exist and are READY.

    `mas_endpoint`/`ka_endpoint` are the resolved bundle vars — the exact names render
    writes into app.yaml. When set, check THOSE specific endpoints (unambiguous even when
    the workspace holds multiple mas-/ka- endpoints, e.g. a `_fw_v2` sandbox set). When NOT
    set (ids passed to render as --flags, or env not sourced), fall back to a prefix-
    existence check and WARN that it cannot confirm which endpoint the App points at.
    """
    expected = {"MAS": mas_endpoint, "KA": ka_endpoint}
    if all(expected.values()):
        readiness = {role: (name, _endpoint_ready(name, profile)) for role, name in expected.items()}
        bad = {role: f"{name}={st}" for role, (name, st) in readiness.items() if st != "READY"}
        if bad:
            return False, f"App endpoint(s) not READY: {bad}"
        return True, "App endpoints READY: " + ", ".join(f"{role}={name}" for role, (name, _) in readiness.items())
    # Fallback (vars not set): prefix existence only — ambiguous, so WARN loudly.
    d = _databricks(["serving-endpoints", "list"], profile)
    eps = d.get("endpoints", []) if isinstance(d, dict) else d
    names = [e.get("name", "") for e in eps]
    for prefix in ("mas-", "ka-"):
        if not any(n.startswith(prefix) for n in names):
            return False, f"no endpoint with prefix {prefix!r}; have {names[:5]}…"
    matches = {p: [n for n in names if n.startswith(p)] for p in ("mas-", "ka-")}
    return True, (f"WARN: mas_endpoint/ka_endpoint bundle vars not set — prefix-existence only, "
                  f"cannot confirm the App's actual endpoint. matches={matches}")


def check_genie_space(profile: str, space_id: str = "", expected_name_contains: str = "Glucosphere") -> tuple[bool, str]:
    """Verify the App's ACTUAL Genie space exists. Matches the resolved `genie_space_id`
    when set (unambiguous); else falls back to a display-name substring match and WARNS."""
    d = _databricks_api("GET", "/api/2.0/data-rooms", profile)
    rooms = d.get("data_rooms", [])
    if space_id:
        match = next((r for r in rooms if (r.get("space_id") or r.get("id")) == space_id), None)
        if match is None:
            return False, (f"App's genie_space_id {space_id!r} not found among data-rooms; "
                           f"have {[(r.get('display_name',''), r.get('space_id') or r.get('id')) for r in rooms[:5]]}…")
        return True, f"id={space_id} display_name={match.get('display_name')!r}"
    match = next((r for r in rooms if expected_name_contains.lower() in r.get("display_name", "").lower()), None)
    if match is None:
        return False, f"no Genie space matching '*{expected_name_contains}*'; have {[r.get('display_name','') for r in rooms[:5]]}…"
    return True, (f"WARN: genie_space_id bundle var not set — name-substring match only. "
                  f"display_name={match.get('display_name')!r}, id={match.get('space_id') or match.get('id')!r}")


def check_firmware_variety(catalog: str, schema: str, warehouse_id: str, profile: str,
                            min_distinct: int = 3) -> tuple[bool, str]:
    """Gold table must have >= 3 distinct firmware_version values.

    Catches the regression where `demo_week_start: 'auto'` (sliding 7-day window)
    drifted past the hardcoded Jan 7-9 firmware-event timestamps in
    Create Raw Device Data.ipynb, collapsing 3 firmware values (3.14, 4.0, 4.10)
    down to 2 (3.14, 4.10).
    """
    body = {
        "warehouse_id": warehouse_id,
        "statement": (
            f"SELECT COUNT(DISTINCT firmware_version) AS n "
            f"FROM {catalog}.{schema}.gold_patient_device_readings"
        ),
        "wait_timeout": "30s",
    }
    d = _databricks_api("POST", "/api/2.0/sql/statements", profile, body)
    status = d.get("status", {}).get("state", "?")
    if status != "SUCCEEDED":
        err = d.get("status", {}).get("error", {}).get("message", "")[:200]
        return False, f"status={status}, error={err!r}"
    rows = d.get("result", {}).get("data_array", [])
    if not rows:
        return False, "0 rows in result"
    n = int(rows[0][0])
    return n >= min_distinct, f"distinct firmware_version count = {n} (need >= {min_distinct})"


def check_uc_asset_png(catalog: str, schema: str, profile: str,
                       asset_subpath: str = "incident_inference_assets/distribution_comparison_4panel.png"
                       ) -> tuple[bool, str]:
    """UC Volume PNG asset must exist + be readable by the App SP path.

    Uses the same Files API (`/api/2.0/fs/files/...`) that the App's `/uc-assets/`
    route proxies. Catches the silent `try/except` in 05_incident_inference_bidirectional.py
    that masked a failed PNG save during a fresh-schema deploy — the task showed SUCCESS
    while the PNG was never written into the new schema's `pipeline_data` volume.
    """
    full_path = f"/Volumes/{catalog}/{schema}/pipeline_data/{asset_subpath}"
    # Use curl with the profile's host+token directly. `databricks api get` tries
    # to JSON-decode the response body, which chokes on binary PNG bytes
    # (the `\x89PNG\r\n` header). curl returns raw bytes — same flow the App's
    # Flask /uc-assets/ route uses via Python requests at App/databricks/app.py:554.
    host_cmd = ["databricks", "auth", "describe", "--profile", profile, "-o", "json"]
    token_cmd = ["databricks", "auth", "token", "--profile", profile, "-o", "json"]
    try:
        host = json.loads(subprocess.check_output(host_cmd, text=True, env=_DATABRICKS_ENV))["details"]["host"]
        token = json.loads(subprocess.check_output(token_cmd, text=True, env=_DATABRICKS_ENV))["access_token"]
    except Exception as e:
        return False, f"could not resolve host+token from profile {profile!r}: {e}"
    url = f"{host}/api/2.0/fs/files{full_path}"
    curl_cmd = ["curl", "-s", "-o", "-", "-w", "%{http_code}",
                "-H", f"Authorization: Bearer {token}", url]
    try:
        out = subprocess.check_output(curl_cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        return False, f"curl failed: {e.output.decode('utf-8', errors='replace')[:200]}"
    # curl with -w "%{http_code}" appends HTTP status code at the end
    status_code = out[-3:].decode("ascii", errors="replace")
    body = out[:-3]
    if status_code != "200":
        return False, f"Files API returned HTTP {status_code} for {full_path}"
    if len(body) < 8 or body[:8] != b"\x89PNG\r\n\x1a\n":
        return False, f"path={full_path}: HTTP 200 but {len(body)} bytes is not a valid PNG"
    return True, f"path={full_path}: HTTP 200, {len(body)} bytes, valid PNG header"


def check_lakebase(profile: str, project_id: str, app_name: str) -> tuple[bool, str]:
    """Lakebase (only when the target sets `lakebase_project_id`): the
    bundle-managed Autoscaling project exists AND the App carries the postgres
    resource binding pointing at it (the binding auto-creates the App SP's PG
    role + injects the PG* env). The triage schema itself is app-runtime
    bootstrap — its health shows up as the app serving /api/alerts, not here.
    Also the drift detector: a CLI/UI-deleted project makes this FAIL while
    `bundle deploy` stays silent (no state refresh) — recovery is
    `POST /api/2.0/postgres/projects/<id>/undelete` + app restart."""
    proj_path = f"projects/{project_id}"
    proj = _databricks(["postgres", "get-project", proj_path], profile)
    if proj.get("name") != proj_path:
        return False, f"project {proj_path} not found"
    app = _databricks_api("GET", f"/api/2.0/apps/{app_name}", profile)
    bindings = [r for r in (app.get("resources") or [])
                if (r.get("postgres") or {}).get("branch", "").startswith(proj_path + "/")]
    if not bindings:
        return False, f"project {proj_path} OK but App has no postgres binding to it"
    return True, f"project {proj_path} + App postgres binding present"


def _resolved_vars(target: str, profile: str) -> dict[str, str]:
    out = subprocess.check_output(
        ["databricks", "bundle", "validate", "-t", target, "--profile", profile, "-o", "json"],
        text=True, env=_DATABRICKS_ENV,
    )
    d = json.loads(out)
    v = d.get("variables", {})
    g = lambda k: (v.get(k, {}) or {}).get("value", "")
    # app_name + existing_warehouse_id resolved so `smoke_test --target dais` works without
    # extra flags (dais reuses an existing warehouse + a non-default app name). mas/ka/genie
    # ids resolved so checks 5+6 assert the App's ACTUAL endpoints/space (what render writes
    # into app.yaml), not a fuzzy prefix/name match. Each is "" when the target supplies it to
    # render as a --flag instead of BUNDLE_VAR_* (or isn't sourced) — checks 5/6 then fall back.
    return {
        "catalog": g("catalog"), "schema": g("schema"), "app_name": g("app_name"),
        "existing_warehouse_id": g("existing_warehouse_id"),
        "mas_endpoint": g("mas_endpoint"), "ka_endpoint": g("ka_endpoint"),
        "genie_space_id": g("genie_space_id"),
        # empty on non-Lakebase targets → check 9 is skipped (not failed)
        "lakebase_project_id": g("lakebase_project_id"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, help="Bundle target (e.g. gsphere)")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE"),
                   help="Databricks CLI profile (default: $DATABRICKS_CONFIG_PROFILE)")
    p.add_argument("--app-name", default=None, help="App resource name (default: resolved app_name bundle var)")
    p.add_argument("--catalog", help="Catalog (default: resolved from bundle validate)")
    p.add_argument("--schema", help="Schema (default: resolved from bundle validate)")
    p.add_argument("--warehouse-id", default=None,
                   help="Reused warehouse id for targets that don't create their own (e.g. dais). "
                        "Default: resolved existing_warehouse_id bundle var; else discover by name.")
    args = p.parse_args()

    if not args.profile:
        print("ERROR: --profile required (or set DATABRICKS_CONFIG_PROFILE)", file=sys.stderr)
        return 2

    # Resolve bundle vars once (catalog/schema/app_name/existing_warehouse_id + mas/ka/genie
    # ids for checks 5/6); explicit flags win.
    rv = _resolved_vars(args.target, args.profile)
    args.catalog = args.catalog or rv["catalog"]
    args.schema = args.schema or rv["schema"]
    args.app_name = args.app_name or rv["app_name"] or "glucosphere-app"
    args.warehouse_id = args.warehouse_id or rv["existing_warehouse_id"] or None

    print(f"Smoke test: target={args.target} catalog={args.catalog} schema={args.schema}")
    print(f"           profile={args.profile} app={args.app_name} "
          f"warehouse={'(reused) ' + args.warehouse_id if args.warehouse_id else '(bundle-managed)'}")
    print()

    fails = 0

    def run(label: str, fn) -> None:
        nonlocal fails
        try:
            ok, detail = fn()
        except subprocess.CalledProcessError as e:
            ok, detail = False, f"CLI error: {e.output.strip()[:200]}"
        except Exception as e:
            ok, detail = False, f"exception: {e}"
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {label}: {detail}")
        if not ok:
            fails += 1

    run("1. App state",         lambda: check_app_state(args.app_name, args.profile))
    run("2. App URL serving",   lambda: check_app_serving(args.app_name, args.profile))
    run("3. Bundle warehouse",  lambda: check_warehouse(args.target, args.profile, args.warehouse_id))

    wh_id = _warehouse_id(args.target, args.profile, args.warehouse_id)
    if wh_id:
        run("4. Gold table data",       lambda: check_gold_table(args.catalog, args.schema, wh_id, args.profile))
    else:
        print("  [SKIP] 4. Gold table data: no warehouse_id (check 3 must pass first)")
        fails += 1

    run("5. Serving endpoints",     lambda: check_serving_endpoints(args.profile, rv["mas_endpoint"], rv["ka_endpoint"]))
    run("6. Genie space",           lambda: check_genie_space(args.profile, rv["genie_space_id"]))

    if wh_id:
        run("7. Firmware variety",  lambda: check_firmware_variety(args.catalog, args.schema, wh_id, args.profile))
    else:
        print("  [SKIP] 7. Firmware variety: no warehouse_id (check 3 must pass first)")
        fails += 1

    run("8. UC asset PNG",          lambda: check_uc_asset_png(args.catalog, args.schema, args.profile))

    # 9 — Lakebase (Alert Triage OLTP): only on targets that set lakebase_project_id;
    # others skip without failing (the feature is deliberately absent there).
    n_checks = 8
    if rv["lakebase_project_id"]:
        n_checks = 9
        run("9. Lakebase project + binding",
            lambda: check_lakebase(args.profile, rv["lakebase_project_id"], args.app_name))
    else:
        print("  [SKIP] 9. Lakebase project + binding: lakebase_project_id not set for this target")

    print()
    if fails:
        print(f"FAIL — {fails}/{n_checks} smoke-test checks failed")
        return 1
    print(f"PASS — all {n_checks} smoke-test checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
