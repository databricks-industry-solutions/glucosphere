#!/usr/bin/env python3
"""
smoke_test.py — Pre-PR automated smoke test for the deployed glucosphere App.

Validates the deployed state of the live target end-to-end (deploy + data + agent
endpoints + Genie space). Run after `databricks bundle run glucosphere_app …`
completes (DEPLOY.md Step 9). Catches the backend failure modes that the manual
browser-driven checks in DEPLOY.md Step 10 also catch, without needing SSO auth.

What's automated (8 checks):
    1. App state: `databricks api get /api/2.0/apps/<name>` → compute_status.state == ACTIVE
       and app_status.state == RUNNING.
    2. App URL: HEAD request to the App URL → non-5xx response (auth redirect is fine —
       proves the App is serving HTTP).
    3. Warehouse: `databricks warehouses list` contains `glucosphere-warehouse-<target>`
       (create-own targets), OR the reused warehouse id exists (reuse targets that set
       `existing_warehouse_id`, e.g. the DAIS booth — pass `--warehouse-id` or let it resolve).
    4. Gold table: `SELECT COUNT(*) FROM <catalog>.<schema>.gold_patient_device_readings`
       returns > 0 (proves DLT silver/gold pipeline succeeded + SP can read).
    5. KA + MAS serving endpoints: `databricks serving-endpoints list` contains
       endpoint names matching the App's `app.yaml` references.
    6. Genie space: `databricks api get /api/2.0/data-rooms` contains a room with the
       configured display name.
    7. Firmware variety: gold table has >= 3 distinct firmware_version values
       (catches the demo_week_start vs firmware-event-timestamp drift regression —
       2026-05-28 cycle 2 silently dropped from 3 → 2 firmware values).
    8. MetricsExplained PNG: UC Files API GET of
       `/Volumes/<catalog>/<schema>/pipeline_data/incident_inference_assets/distribution_comparison_4panel.png`
       returns 200 + image/png bytes (catches the silent try/except in
       05_incident_inference_bidirectional.py PNG-save block — cycle 2 incident_inference
       task showed SUCCESS while the PNG was never written).

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


def check_serving_endpoints(profile: str, expected_prefixes: tuple[str, ...] = ("mas-", "ka-")) -> tuple[bool, str]:
    d = _databricks(["serving-endpoints", "list"], profile)
    eps = d.get("endpoints", []) if isinstance(d, dict) else d
    names = [e.get("name", "") for e in eps]
    missing = [p for p in expected_prefixes if not any(n.startswith(p) for n in names)]
    if missing:
        return False, f"missing endpoints with prefix(es): {missing}; have {names[:5]}…"
    matched = {p: next(n for n in names if n.startswith(p)) for p in expected_prefixes}
    return True, f"found {matched}"


def check_genie_space(profile: str, expected_name_contains: str = "Glucosphere") -> tuple[bool, str]:
    d = _databricks_api("GET", "/api/2.0/data-rooms", profile)
    rooms = d.get("data_rooms", [])
    match = next((r for r in rooms if expected_name_contains.lower() in r.get("display_name", "").lower()), None)
    if match is None:
        return False, f"no Genie space matching '*{expected_name_contains}*'; have {[r.get('display_name','') for r in rooms[:5]]}…"
    return True, f"display_name={match.get('display_name')!r}, id={match.get('space_id') or match.get('id')!r}"


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


def _resolved_vars(target: str, profile: str) -> tuple[str, str, str, str]:
    out = subprocess.check_output(
        ["databricks", "bundle", "validate", "-t", target, "--profile", profile, "-o", "json"],
        text=True, env=_DATABRICKS_ENV,
    )
    d = json.loads(out)
    v = d.get("variables", {})
    g = lambda k: (v.get(k, {}) or {}).get("value", "")
    # app_name + existing_warehouse_id resolved too so `smoke_test --target dais` works
    # without extra flags (dais reuses an existing warehouse + a non-default app name).
    return g("catalog"), g("schema"), g("app_name"), g("existing_warehouse_id")


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

    # Resolve bundle vars once (catalog/schema/app_name/existing_warehouse_id); explicit flags win.
    r_cat, r_sch, r_app, r_wh = _resolved_vars(args.target, args.profile)
    args.catalog = args.catalog or r_cat
    args.schema = args.schema or r_sch
    args.app_name = args.app_name or r_app or "glucosphere-app"
    args.warehouse_id = args.warehouse_id or r_wh or None

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

    run("5. Serving endpoints",     lambda: check_serving_endpoints(args.profile))
    run("6. Genie space",           lambda: check_genie_space(args.profile))

    if wh_id:
        run("7. Firmware variety",  lambda: check_firmware_variety(args.catalog, args.schema, wh_id, args.profile))
    else:
        print("  [SKIP] 7. Firmware variety: no warehouse_id (check 3 must pass first)")
        fails += 1

    run("8. UC asset PNG",          lambda: check_uc_asset_png(args.catalog, args.schema, args.profile))

    print()
    if fails:
        print(f"FAIL — {fails}/8 smoke-test checks failed")
        return 1
    print("PASS — all 8 smoke-test checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
