#!/usr/bin/env python3
"""
render_app_yaml.py — Rewrite App/databricks/app.yaml for a given DABs target.

Reads resolved bundle variables (catalog / schema) from
`databricks bundle validate -t <target> -o json`, discovers the bundle-managed
warehouse by deterministic name (`glucosphere-warehouse-<target>`), and
optionally overrides MAS/KA/Genie IDs. Rewrites App/databricks/app.yaml
in place via regex.

Run sequence:
    # First deploy creates the warehouse:
    databricks bundle deploy -t <target>
    # Then discover warehouse + rewrite app.yaml:
    uv run python scripts/render_app_yaml.py --target <target>
    # Second deploy syncs updated app.yaml:
    databricks bundle deploy -t <target>

Usage:
    # Render for gsphere with auto-discovered warehouse_id
    uv run python scripts/render_app_yaml.py --target gsphere

    # Full render after setup job created the endpoints + genie space —
    # auto-discover the KA/MAS/Genie IDs by name (no hand-copied hex IDs):
    uv run python scripts/render_app_yaml.py --target gsphere --discover-agents

    # ...or pass them explicitly (overrides discovery):
    uv run python scripts/render_app_yaml.py \\
        --target gsphere \\
        --mas-endpoint   glucosphere-mas-endpoint \\
        --ka-endpoint    glucosphere-ka-endpoint \\
        --genie-space-id 01a2b3c4d5e6...

    # Override profile (default: $DATABRICKS_CONFIG_PROFILE env var if set, e.g. via `source .env.bundle`)
    uv run python scripts/render_app_yaml.py --target gsphere
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_YAML = REPO_ROOT / "App" / "databricks" / "app.yaml"


def get_bundle_vars(target: str, profile: str | None) -> dict[str, str]:
    cmd = ["databricks", "bundle", "validate", "-t", target, "-o", "json"]
    if profile:
        cmd += ["-p", profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[FATAL] `databricks bundle validate` failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(result.returncode)
    bundle = json.loads(result.stdout)
    return {k: v.get("value", "") for k, v in bundle.get("variables", {}).items()}


def patch(content: str, pattern: str, replacement: str, label: str) -> str:
    new_content, n = re.subn(pattern, replacement, content)
    if n == 0:
        print(f"  [skip] {label}: pattern not found", file=sys.stderr)
    else:
        print(f"  [ok]   {label}: replaced ({n})")
    return new_content


def discover_bundle_warehouse_id(target: str, profile: str | None) -> str:
    """Query the workspace for the bundle-managed sql_warehouses resource by
    deterministic name pattern `glucosphere-warehouse-<target>`.

    Pattern matches the `name:` field of `resources.sql_warehouses.glucosphere_warehouse`
    in databricks.yml. Uses `endswith` to handle `mode: development` targets which
    auto-prefix the name with `[dev USER]`.

    Profile resolution: explicit `--profile` flag wins; otherwise falls back to
    the `DATABRICKS_CONFIG_PROFILE` env var (the SSOT-pattern source via
    `.env.bundle`). CLI v0.297.2's `warehouses list` does NOT inherit the env
    var when run from a bundle directory — it requires explicit `-p <profile>`
    or fails with "please specify target".

    Fails hard (sys.exit(1)) if the warehouses list call errors OR if no
    warehouse with the expected name suffix is found. Precondition: a successful
    `databricks bundle deploy -t <target>` must have run first to create the
    sql_warehouses resource.
    """
    cmd = ["databricks", "warehouses", "list", "-o", "json"]
    effective_profile = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
    if effective_profile:
        cmd += ["-p", effective_profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[FATAL] `databricks warehouses list` failed:\n{result.stderr}", file=sys.stderr)
        print(f"[FATAL] Cannot discover bundle-managed warehouse for target={target}.", file=sys.stderr)
        print(f"[FATAL] Hint: pass --profile <name> or set DATABRICKS_CONFIG_PROFILE in .env.bundle (with `export` prefix).", file=sys.stderr)
        sys.exit(1)
    warehouses = json.loads(result.stdout)
    expected_suffix = f"glucosphere-warehouse-{target}"
    for w in warehouses:
        if w.get("name", "").endswith(expected_suffix):
            return w.get("id", "")
    print(f"[FATAL] No warehouse found with name ending in `{expected_suffix}`.", file=sys.stderr)
    print(f"[FATAL] Precondition: `databricks bundle deploy -t {target}` must succeed before render.", file=sys.stderr)
    sys.exit(1)


def discover_setup_job_id(target: str, profile: str | None) -> str:
    """Query the workspace for the bundle-managed `glucosphere_full_setup`
    job by deterministic name pattern `glucosphere-full-setup-<target>`.

    Pattern matches the `name:` field of `resources.jobs.glucosphere_full_setup`
    in databricks.yml. Uses `endswith` to handle `mode: development` targets
    which auto-prefix the name with `[dev USER]`.

    Returns the job_id (string) used to build the App's Metrics-Explained
    deep-link at runtime. Same profile-resolution rules as
    `discover_bundle_warehouse_id`.

    Returns empty string (not sys.exit) if no matching job is found — the
    setup-job-link is optional UX; the App's JSX falls back to the workspace
    `/jobs` listing when SETUP_JOB_ID is empty. This makes render safe to
    run before the first `bundle deploy` (e.g. between deploy passes).
    """
    cmd = ["databricks", "jobs", "list", "-o", "json"]
    effective_profile = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
    if effective_profile:
        cmd += ["-p", effective_profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[warn]  `databricks jobs list` failed; SETUP_JOB_ID will be empty (link falls back to /jobs listing):\n{result.stderr}", file=sys.stderr)
        return ""
    jobs = json.loads(result.stdout)
    expected_suffix = f"glucosphere-full-setup-{target}"
    for j in jobs:
        name = j.get("settings", {}).get("name", "")
        if name.endswith(expected_suffix):
            return str(j.get("job_id", ""))
    print(f"[warn]  No job found with name ending in `{expected_suffix}` — SETUP_JOB_ID will be empty (link falls back to /jobs listing). This is expected on first-pass render before bundle deploy.", file=sys.stderr)
    return ""


def _api_get(path: str, profile: str | None) -> dict:
    """GET a workspace REST path via the CLI; return parsed JSON ({} on error)."""
    cmd = ["databricks", "api", "get", path]
    effective_profile = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
    if effective_profile:
        cmd += ["-p", effective_profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[warn]  `databricks api get {path}` failed:\n{result.stderr}", file=sys.stderr)
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}


def discover_agents(profile: str | None, suffix: str) -> dict[str, str]:
    """Look up the KA + MAS serving-endpoint names and the Genie space id by
    their deterministic display names — `Glucosphere_KA<suffix>` /
    `Glucosphere_Supervisor<suffix>` / `Glucosphere_Intelligence<suffix>` —
    which match the KA_NAME / MAS_NAME / GENIE_NAME base_parameters in
    databricks.yml. Lets a caller wire the freshly-created agents into app.yaml
    without hand-copying hex IDs from the setup-job logs.

    Verified JSON paths (2026-06-01): the auto-generated `ka-<hex>-endpoint` /
    `mas-<hex>-endpoint` serving-endpoint name lives at
    `.<wrapper>.tile.serving_endpoint_name` on the tile-detail GET; the Genie
    space id is the `id` field of the matching `/api/2.0/data-rooms` entry.

    Returns a dict {ka_endpoint, mas_endpoint, genie_space_id}; any value not
    found is "" (caller leaves that field unchanged).
    """
    ka_name = f"Glucosphere_KA{suffix}"
    mas_name = f"Glucosphere_Supervisor{suffix}"
    genie_name = f"Glucosphere_Intelligence{suffix}"
    out = {"ka_endpoint": "", "mas_endpoint": "", "genie_space_id": ""}

    ka_tiles = _api_get("/api/2.0/tiles?tile_type=KNOWLEDGE_ASSISTANT", profile).get("tiles", [])
    ka_id = next((t.get("tile_id") for t in ka_tiles if t.get("name") == ka_name), None)
    if ka_id:
        det = _api_get(f"/api/2.0/knowledge-assistants/{ka_id}", profile)
        out["ka_endpoint"] = det.get("knowledge_assistant", det).get("tile", {}).get("serving_endpoint_name", "")

    mas_tiles = _api_get("/api/2.0/tiles?tile_type=MULTI_AGENT_SUPERVISOR", profile).get("tiles", [])
    mas_id = next((t.get("tile_id") for t in mas_tiles if t.get("name") == mas_name), None)
    if mas_id:
        det = _api_get(f"/api/2.0/multi-agent-supervisors/{mas_id}", profile)
        out["mas_endpoint"] = det.get("multi_agent_supervisor", det).get("tile", {}).get("serving_endpoint_name", "")

    rooms = _api_get("/api/2.0/data-rooms?page_size=200", profile).get("data_rooms", [])
    out["genie_space_id"] = next(
        (r.get("id") or r.get("space_id") for r in rooms if r.get("display_name") == genie_name), "")

    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, help="DABs target name (e.g. gsphere)")
    p.add_argument("--profile", default=None, help="databricks CLI profile (default: $DATABRICKS_CONFIG_PROFILE env var if set, e.g. via `source .env.bundle`)")
    p.add_argument("--mas-endpoint", default=None, help="MAS serving endpoint name (overrides env + resource block)")
    p.add_argument("--ka-endpoint", default=None, help="KA serving endpoint name (overrides resource block)")
    p.add_argument("--genie-space-id", default=None, help="Genie space ID (overrides env)")
    p.add_argument("--discover-agents", action="store_true",
                   help="Auto-discover the KA/MAS endpoint names + Genie space id by deterministic "
                        "name (Glucosphere_*<harness_suffix>) and wire them in — run AFTER the setup "
                        "job created them, instead of passing --ka-endpoint/--mas-endpoint/--genie-space-id by hand.")
    args = p.parse_args()

    vars_ = get_bundle_vars(args.target, args.profile)
    catalog = vars_.get("catalog")
    schema = vars_.get("schema")
    # warehouse_id is NOT a bundle variable anymore — it comes from the
    # bundle-managed sql_warehouses resource (discovered by deterministic name).
    # This requires the bundle to have been deployed at least once.
    warehouse_id = discover_bundle_warehouse_id(args.target, args.profile)
    setup_job_id = discover_setup_job_id(args.target, args.profile)

    # --discover-agents: look up the KA/MAS endpoint names + Genie space id by
    # their deterministic names (Glucosphere_*<harness_suffix>) so the caller
    # need not paste hex IDs from the setup-job logs. Explicit --ka-endpoint /
    # --mas-endpoint / --genie-space-id still win if also passed.
    if args.discover_agents:
        suffix = vars_.get("harness_suffix", "")
        found = discover_agents(args.profile, suffix)
        args.ka_endpoint = args.ka_endpoint or (found["ka_endpoint"] or None)
        args.mas_endpoint = args.mas_endpoint or (found["mas_endpoint"] or None)
        args.genie_space_id = args.genie_space_id or (found["genie_space_id"] or None)
        print(f"  discover-agents (harness_suffix={suffix!r}): "
              f"ka={args.ka_endpoint or '(not found)'} "
              f"mas={args.mas_endpoint or '(not found)'} "
              f"genie={args.genie_space_id or '(not found)'}")

    print(f"Rendering {APP_YAML.relative_to(REPO_ROOT)} for target={args.target}:")
    print(f"  catalog        = {catalog}")
    print(f"  schema         = {schema}")
    print(f"  warehouse_id   = {warehouse_id}")
    print(f"  setup_job_id   = {setup_job_id or '(not found — link will fall back to /jobs listing)'}")
    print(f"  mas-endpoint   = {args.mas_endpoint or '(unchanged)'}")
    print(f"  ka-endpoint    = {args.ka_endpoint or '(unchanged)'}")
    print(f"  genie-space-id = {args.genie_space_id or '(unchanged)'}")

    if not APP_YAML.exists():
        print(f"[FATAL] {APP_YAML} not found", file=sys.stderr)
        return 1

    content = APP_YAML.read_text()

    if catalog:
        content = patch(content,
            r'(- name: CATALOG_NAME\s+value: ")[^"]*(")',
            rf'\g<1>{catalog}\g<2>', "env CATALOG_NAME")
    if schema:
        content = patch(content,
            r'(- name: SCHEMA_NAME\s+value: ")[^"]*(")',
            rf'\g<1>{schema}\g<2>', "env SCHEMA_NAME")
    # SETUP_JOB_ID — discovered above via Jobs API by name match. Empty
    # string is valid (and written) — JSX falls back to /jobs listing.
    content = patch(content,
        r'(- name: SETUP_JOB_ID\s+value: ")[^"]*(")',
        rf'\g<1>{setup_job_id}\g<2>', "env SETUP_JOB_ID")
    if warehouse_id:
        # Update BOTH the WAREHOUSE_ID env var (consumed by app.py's
        # /api/sql/query Statement Execution API call) AND the resource
        # binding (app SP needs CAN_USE permission, granted via 09).
        content = patch(content,
            r'(- name: WAREHOUSE_ID\s+value: ")[^"]*(")',
            rf'\g<1>{warehouse_id}\g<2>', "env WAREHOUSE_ID")
        content = patch(content,
            r'(- name: sql-warehouse\b[\s\S]*?sql_warehouse:\s+id: )\S+',
            rf'\g<1>{warehouse_id}', "resource sql-warehouse.id")
    # ENDPOINT_NAME and GENIE_SPACE_ID env vars use plain `value:` because
    # `valueFrom:` did not resolve at runtime (app object's `resources` field
    # came back empty after deploy, so valueFrom references came up empty).
    # Rewrite BOTH the env var `value:` field AND the
    # resource block so the resource bindings stay declared for SP permissions
    # even though we no longer rely on valueFrom to populate the env value.
    if args.mas_endpoint:
        content = patch(content,
            r'(- name: ENDPOINT_NAME\s+value: ")[^"]*(")',
            rf'\g<1>{args.mas_endpoint}\g<2>', "env ENDPOINT_NAME")
        content = patch(content,
            r'(- name: mas-endpoint\b[\s\S]*?serving_endpoint:\s+name: )\S+',
            rf'\g<1>{args.mas_endpoint}', "resource mas-endpoint.name")
    if args.ka_endpoint:
        content = patch(content,
            r'(- name: ka-endpoint\b[\s\S]*?serving_endpoint:\s+name: )\S+',
            rf'\g<1>{args.ka_endpoint}', "resource ka-endpoint.name")
    if args.genie_space_id:
        content = patch(content,
            r'(- name: GENIE_SPACE_ID\s+value: ")[^"]*(")',
            rf'\g<1>{args.genie_space_id}\g<2>', "env GENIE_SPACE_ID")
        content = patch(content,
            r'(- name: genie-space\b[\s\S]*?genie_space:\s+id: )\S+',
            rf'\g<1>{args.genie_space_id}', "resource genie-space.id")

    APP_YAML.write_text(content)
    print(f"Wrote {APP_YAML.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
