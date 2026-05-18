#!/usr/bin/env python3
"""
render_app_yaml.py — Rewrite App/databricks/app.yaml for a given DABs target.

Reads the resolved bundle variables (catalog / schema / warehouse_id) from
`databricks bundle validate -t <target> -o json`, optionally overrides the
runtime-discovered IDs (MAS endpoint name, KA endpoint name, Genie space ID),
and rewrites App/databricks/app.yaml in place via regex.

Matches the in-place rewrite pattern from deploy.py:step_wire_and_deploy(),
extended to cover catalog / schema / warehouse / KA endpoint too. Intended to
run BEFORE `databricks bundle deploy -t <target>`.

Usage:
    # Render for hls_amer using only bundle vars (leaves endpoint/genie placeholders alone)
    python scripts/render_app_yaml.py --target hls_amer

    # Full render after setup job created the endpoints + genie space
    python scripts/render_app_yaml.py \\
        --target hls_amer \\
        --mas-endpoint   glucosphere-mas-endpoint \\
        --ka-endpoint    glucosphere-ka-endpoint \\
        --genie-space-id 01a2b3c4d5e6...

    # Override profile (default: auto-resolved by databricks CLI from host)
    python scripts/render_app_yaml.py --target hls_amer --profile fe-vm-hls-amer
"""

from __future__ import annotations

import argparse
import json
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--target", required=True, help="DABs target name (e.g. hls_amer)")
    p.add_argument("--profile", default=None, help="databricks CLI profile (default: auto-resolved by host)")
    p.add_argument("--mas-endpoint", default=None, help="MAS serving endpoint name (overrides env + resource block)")
    p.add_argument("--ka-endpoint", default=None, help="KA serving endpoint name (overrides resource block)")
    p.add_argument("--genie-space-id", default=None, help="Genie space ID (overrides env)")
    args = p.parse_args()

    vars_ = get_bundle_vars(args.target, args.profile)
    catalog = vars_.get("catalog")
    schema = vars_.get("schema")
    warehouse_id = vars_.get("warehouse_id")

    print(f"Rendering {APP_YAML.relative_to(REPO_ROOT)} for target={args.target}:")
    print(f"  catalog        = {catalog}")
    print(f"  schema         = {schema}")
    print(f"  warehouse_id   = {warehouse_id}")
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
    if warehouse_id:
        content = patch(content,
            r'(- name: sql-warehouse\b[\s\S]*?sql_warehouse:\s+id: )\S+',
            rf'\g<1>{warehouse_id}', "resource sql-warehouse.id")
    # ENDPOINT_NAME and GENIE_SPACE_ID env vars reverted to plain `value:` on
    # 2026-05-18 — `valueFrom:` did not resolve at runtime (app object's
    # `resources` field came back empty after deploy, so valueFrom references
    # came up empty). Rewrite BOTH the env var `value:` field AND the
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
