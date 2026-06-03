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

    # Full render after setup job created the endpoints + genie space
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


def discover_pipeline_id(target: str, profile: str | None) -> str:
    """Query the workspace for the bundle-managed `cgm_silver_gold` DLT pipeline
    by deterministic name pattern `glucosphere-cgm-silver-gold-<target>`.

    Pattern matches the `name:` field of `resources.pipelines.cgm_silver_gold`
    in databricks.yml. Uses `endswith` to handle `mode: development` targets
    which auto-prefix the name with `[dev USER]` (same as the setup job).

    Returns the pipeline_id (string) used to build the About page's "under the
    hood" platform-plumbing deep-link at runtime. Same profile-resolution rules
    as `discover_setup_job_id`.

    Returns empty string (not sys.exit) if no matching pipeline is found — the
    pipeline link is optional UX; the App's JSX falls back to the workspace
    `/pipelines` listing when PIPELINE_ID is empty. Safe to run before the first
    `bundle deploy` (e.g. between deploy passes).
    """
    cmd = ["databricks", "pipelines", "list-pipelines", "-o", "json"]
    effective_profile = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
    if effective_profile:
        cmd += ["-p", effective_profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[warn]  `databricks pipelines list-pipelines` failed; PIPELINE_ID will be empty (link falls back to /pipelines listing):\n{result.stderr}", file=sys.stderr)
        return ""
    pipelines = json.loads(result.stdout)
    expected_suffix = f"glucosphere-cgm-silver-gold-{target}"
    for pl in pipelines:
        if str(pl.get("name", "")).endswith(expected_suffix):
            return str(pl.get("pipeline_id", ""))
    print(f"[warn]  No pipeline found with name ending in `{expected_suffix}` — PIPELINE_ID will be empty (link falls back to /pipelines listing). This is expected on first-pass render before bundle deploy.", file=sys.stderr)
    return ""


def discover_forecast_endpoint(harness_suffix: str, profile: str | None) -> str:
    """Find the Glucosphere forecast Model Serving endpoint for this deploy.

    The 15-minute forecast endpoint is named `Glucosphere_Forecast_15min` +
    `harness_suffix` (07_*.py); the suffix isolates harness deploys (e.g.
    `_fw_v2`) and is empty for the production `gsphere` target. Used to deep-link
    the About panel's Model Serving node straight to the endpoint detail page —
    the serving-endpoints LIST page has no URL search param, so a direct link is
    the only way to land on a specific glucosphere endpoint.

    Returns the endpoint name (string), or empty string if not found — the link
    is optional UX; JSX falls back to the `/ml/endpoints` listing. Safe to run
    before the endpoint exists (e.g. first-pass render).
    """
    expected = f"Glucosphere_Forecast_15min{harness_suffix or ''}"
    cmd = ["databricks", "serving-endpoints", "list", "-o", "json"]
    effective_profile = profile or os.environ.get("DATABRICKS_CONFIG_PROFILE")
    if effective_profile:
        cmd += ["-p", effective_profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[warn]  `databricks serving-endpoints list` failed; FORECAST_ENDPOINT_NAME will be empty (link falls back to /ml/endpoints listing):\n{result.stderr}", file=sys.stderr)
        return ""
    endpoints = json.loads(result.stdout)
    for ep in endpoints:
        if ep.get("name", "") == expected:
            return expected
    print(f"[warn]  No serving endpoint named `{expected}` — FORECAST_ENDPOINT_NAME will be empty (link falls back to /ml/endpoints listing). This is expected on first-pass render before bundle deploy.", file=sys.stderr)
    return ""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, help="DABs target name (e.g. gsphere)")
    p.add_argument("--profile", default=None, help="databricks CLI profile (default: $DATABRICKS_CONFIG_PROFILE env var if set, e.g. via `source .env.bundle`)")
    p.add_argument("--mas-endpoint", default=None, help="MAS serving endpoint name (overrides env + resource block)")
    p.add_argument("--ka-endpoint", default=None, help="KA serving endpoint name (overrides resource block)")
    p.add_argument("--genie-space-id", default=None, help="Genie space ID (overrides env)")
    args = p.parse_args()

    vars_ = get_bundle_vars(args.target, args.profile)
    catalog = vars_.get("catalog")
    schema = vars_.get("schema")
    # warehouse_id is NOT a bundle variable anymore — it comes from the
    # bundle-managed sql_warehouses resource (discovered by deterministic name).
    # This requires the bundle to have been deployed at least once.
    warehouse_id = discover_bundle_warehouse_id(args.target, args.profile)
    setup_job_id = discover_setup_job_id(args.target, args.profile)
    pipeline_id = discover_pipeline_id(args.target, args.profile)
    forecast_endpoint = discover_forecast_endpoint(vars_.get("harness_suffix", ""), args.profile)

    print(f"Rendering {APP_YAML.relative_to(REPO_ROOT)} for target={args.target}:")
    print(f"  catalog        = {catalog}")
    print(f"  schema         = {schema}")
    print(f"  warehouse_id   = {warehouse_id}")
    print(f"  setup_job_id   = {setup_job_id or '(not found — link will fall back to /jobs listing)'}")
    print(f"  pipeline_id    = {pipeline_id or '(not found — link will fall back to /pipelines listing)'}")
    print(f"  forecast_endpt = {forecast_endpoint or '(not found — link will fall back to /ml/endpoints listing)'}")
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
    # PIPELINE_ID — discovered above via Pipelines API by name match. Empty
    # string is valid (and written) — JSX falls back to /pipelines listing.
    content = patch(content,
        r'(- name: PIPELINE_ID\s+value: ")[^"]*(")',
        rf'\g<1>{pipeline_id}\g<2>', "env PIPELINE_ID")
    # FORECAST_ENDPOINT_NAME — discovered above via Serving Endpoints API by name.
    # Empty string is valid (and written) — JSX falls back to /ml/endpoints listing.
    content = patch(content,
        r'(- name: FORECAST_ENDPOINT_NAME\s+value: ")[^"]*(")',
        rf'\g<1>{forecast_endpoint}\g<2>', "env FORECAST_ENDPOINT_NAME")
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
        # Patch BOTH the KA_ENDPOINT_NAME env var (consumed by app.py's assist
        # router) and the ka-endpoint resource binding — mirrors --mas-endpoint.
        content = patch(content,
            r'(- name: KA_ENDPOINT_NAME\s+value: ")[^"]*(")',
            rf'\g<1>{args.ka_endpoint}\g<2>', "env KA_ENDPOINT_NAME")
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
