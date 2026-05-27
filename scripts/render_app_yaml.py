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
    python scripts/render_app_yaml.py --target <target>
    # Second deploy syncs updated app.yaml:
    databricks bundle deploy -t <target>

Usage:
    # Render for mmt_aws_usw2 with auto-discovered warehouse_id
    python scripts/render_app_yaml.py --target mmt_aws_usw2

    # Full render after setup job created the endpoints + genie space
    python scripts/render_app_yaml.py \\
        --target mmt_aws_usw2 \\
        --mas-endpoint   glucosphere-mas-endpoint \\
        --ka-endpoint    glucosphere-ka-endpoint \\
        --genie-space-id 01a2b3c4d5e6...

    # Override profile (default: auto-resolved by databricks CLI from host)
    python scripts/render_app_yaml.py --target mmt_aws_usw2 --profile fevm-mmt-aws-usw2
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


def discover_bundle_warehouse_id(target: str, profile: str | None) -> str:
    """Query the workspace for the bundle-managed sql_warehouses resource by
    deterministic name pattern `glucosphere-warehouse-<target>`.

    Pattern matches the `name:` field of `resources.sql_warehouses.glucosphere_warehouse`
    in databricks.yml. Uses `endswith` to handle `mode: development` targets which
    auto-prefix the name with `[dev USER]`.

    Returns the warehouse_id (16-char hex) or empty string if not found.
    """
    cmd = ["databricks", "warehouses", "list", "-o", "json"]
    if profile:
        cmd += ["-p", profile]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=REPO_ROOT)
    if result.returncode != 0:
        print(f"[WARN] warehouses list failed: {result.stderr}", file=sys.stderr)
        return ""
    warehouses = json.loads(result.stdout)
    expected_suffix = f"glucosphere-warehouse-{target}"
    for w in warehouses:
        if w.get("name", "").endswith(expected_suffix):
            return w.get("id", "")
    return ""


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
    # warehouse_id is NOT a bundle variable anymore — it comes from the
    # bundle-managed sql_warehouses resource (discovered by deterministic name).
    # This requires the bundle to have been deployed at least once.
    warehouse_id = discover_bundle_warehouse_id(args.target, args.profile)

    print(f"Rendering {APP_YAML.relative_to(REPO_ROOT)} for target={args.target}:")
    print(f"  catalog        = {catalog}")
    print(f"  schema         = {schema}")
    print(f"  warehouse_id   = {warehouse_id or '(NOT FOUND — run `bundle deploy` first)'}")
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
        # Update BOTH the WAREHOUSE_ID env var (consumed by app.py's
        # /api/sql/query Statement Execution API call) AND the resource
        # binding (app SP needs CAN_USE permission, granted via 09).
        content = patch(content,
            r'(- name: WAREHOUSE_ID\s+value: ")[^"]*(")',
            rf'\g<1>{warehouse_id}\g<2>', "env WAREHOUSE_ID")
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
