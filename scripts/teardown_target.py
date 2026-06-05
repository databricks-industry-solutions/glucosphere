#!/usr/bin/env python3
"""Tear down the workspace-global resources that `databricks bundle destroy` leaves behind.

`bundle destroy -t <target>` removes the bundle-managed resources (jobs, pipeline, SQL
warehouse, app). It does NOT remove the resources created at *runtime* by the setup-job
notebooks, nor the UC schema:

  - Agent Bricks tiles      (KA + MAS) created by 08_genie_ka_mas.py  → /api/2.0/tiles/{id}
  - Their serving endpoints (ka-<hex> / mas-<hex>)                    → auto-removed with the tile
  - Forecast serving endpoints Glucosphere_Forecast_{15,30}min<sfx>   → 07_deploy_serving_endpoints.py
  - Genie space  Glucosphere_Intelligence<sfx>                        → /api/2.0/data-rooms/{id}
  - The UC schema + its tables                                        → DROP SCHEMA … CASCADE

This script deletes the first four (the part with no existing tooling). It DOES NOT run
`bundle destroy` or `DROP SCHEMA` — those are one-liners you run around it (printed at the end),
because they need a sourced bundle env / a SQL warehouse respectively.

Resources are matched by the deploy's `harness_suffix` (e.g. `_from_source_e2e`) so the LIVE
(empty-suffix) and other targets' resources are never touched. Every resource is GET-verified
before deletion, and the script is DRY-RUN by default — pass --apply to actually delete.

Endpoints used (all verified against fevm-mmt-aws-usw2, 2026-06-05):
  GET  /api/2.0/tiles                  → list tiles (the tile_type query param is ignored; filter by name)
  GET  /api/2.0/tiles/{tile_id}        → tile detail (name, serving_endpoint_name, tile_type)
  DELETE /api/2.0/tiles/{tile_id}      → delete KA/MAS tile (+ its serving endpoint) — per agent-bricks gotcha
  GET  /api/2.0/data-rooms             → list Genie spaces (data-rooms)
  DELETE /api/2.0/data-rooms/{id}      → delete Genie space
  databricks serving-endpoints {list,delete}  → forecast endpoints

Usage:
  # Harness/sandbox deploy — match by its non-empty harness_suffix:
  python scripts/teardown_target.py --suffix _from_source_e2e --profile <profile>            # dry-run
  python scripts/teardown_target.py --suffix _from_source_e2e --profile <profile> --apply    # execute

  # LIVE deploy (empty suffix) — match by EXACT names (suffix-matching is unsafe with ""):
  python scripts/teardown_target.py --profile <profile> \
      --names Glucosphere_KA,Glucosphere_Supervisor,Glucosphere_Intelligence,Glucosphere_Forecast_15min,Glucosphere_Forecast_30min
  #   add --apply to execute. Pair with: bundle destroy -t <target> + DROP SCHEMA <catalog>.<schema> CASCADE.
"""
import argparse
import json
import subprocess
import sys


def db(args, profile, parse_json=True):
    """Run a `databricks` CLI command; return parsed JSON (or raw text)."""
    cmd = ["databricks", *args, "-p", profile]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"`{' '.join(cmd)}` failed:\n{r.stderr.strip()}")
    out = r.stdout.strip()
    if not parse_json:
        return out
    return json.loads(out) if out else {}


def api(method, path, profile, body=None):
    args = ["api", method, path]
    if body is not None:
        args += ["--json", json.dumps(body)]
    return db(args, profile)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suffix", default=None,
                    help="match workspace-global resources whose name ENDS WITH this harness_suffix (e.g. _from_source_e2e). "
                         "MUST be non-empty — an empty suffix would match EVERY resource. Use --names for the live/empty-suffix deploy.")
    ap.add_argument("--names", default=None,
                    help="comma-separated EXACT resource names to delete — use for the LIVE deploy (empty suffix), e.g. "
                         "Glucosphere_KA,Glucosphere_Supervisor,Glucosphere_Intelligence,Glucosphere_Forecast_15min,Glucosphere_Forecast_30min")
    ap.add_argument("--profile", required=True, help="databricks CLI profile (e.g. fevm-mmt-aws-usw2)")
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry-run, deletes nothing)")
    args = ap.parse_args()
    profile, apply = args.profile, args.apply
    sfx = args.suffix
    names = set(n.strip() for n in args.names.split(",") if n.strip()) if args.names else None
    # Safety: exactly ONE selector, and NEVER an empty suffix (endswith('') matches everything).
    if bool(sfx) == bool(names):
        ap.error("provide exactly ONE of --suffix or --names")
    if sfx is not None and sfx.strip() == "":
        ap.error("--suffix must be non-empty (empty would match every resource); use --names for the live deploy")

    def match(name):
        return (name in names) if names is not None else name.endswith(sfx)

    sel = f"names={sorted(names)}" if names else f"suffix '{sfx}'"
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"=== teardown ({mode}) — {sel} on profile '{profile}' ===\n")

    planned = []  # (kind, label, delete_fn)

    # 1. Agent Bricks tiles (KA + MAS) whose name ends with the suffix.
    tiles = api("get", "/api/2.0/tiles", profile)
    tile_list = tiles.get("tiles") or tiles.get("items") or []
    for t in tile_list:
        name = t.get("name") or t.get("display_name") or ""
        if not match(name):
            continue
        tid = t.get("tile_id") or t.get("id")
        ep = t.get("serving_endpoint_name")
        planned.append(("tile", f"{name}  (tile_id={tid}, endpoint={ep}, type={t.get('tile_type')})",
                        lambda tid=tid: api("delete", f"/api/2.0/tiles/{tid}", profile)))

    # 2. Forecast serving endpoints Glucosphere_Forecast_*<suffix> (NOT tied to a tile).
    eps = db(["serving-endpoints", "list", "-o", "json"], profile)
    for e in eps:
        n = e.get("name", "")
        if match(n) and (names is not None or n.startswith("Glucosphere_Forecast_")):
            planned.append(("endpoint", n,
                            lambda n=n: db(["serving-endpoints", "delete", n], profile, parse_json=False)))

    # 3. Genie space (data-room) whose title ends with the suffix.
    rooms = api("get", "/api/2.0/data-rooms", profile)
    room_list = rooms.get("data_rooms") or rooms.get("dataRooms") or rooms.get("items") or []
    for r in room_list:
        title = r.get("display_name") or r.get("title") or ""
        if match(title):
            rid = r.get("id") or r.get("space_id")
            planned.append(("genie", f"{title}  (id={rid})",
                            lambda rid=rid: api("delete", f"/api/2.0/data-rooms/{rid}", profile)))

    if not planned:
        print(f"  No workspace-global resources found with suffix '{sfx}'. Nothing to delete.")
    for kind, label, _ in planned:
        print(f"  [{kind:8s}] {label}")

    if not apply:
        print(f"\n  DRY-RUN — nothing deleted. Re-run with --apply to delete the {len(planned)} resource(s) above.")
    else:
        print()
        for kind, label, fn in planned:
            try:
                fn()
                print(f"  ✓ deleted [{kind}] {label.split('  ')[0]}")
            except Exception as e:
                print(f"  ✗ FAILED  [{kind}] {label.split('  ')[0]}: {e}")

    # Surrounding steps this script intentionally does NOT do:
    print("\n--- run these around this script (not handled here) ---")
    print("  # bundle-managed resources (jobs/pipeline/warehouse/app):")
    print("  source .env.bundle.<target> && databricks bundle destroy -t <target> --auto-approve")
    print("  # UC schema + tables (needs a SQL warehouse):")
    print("  DROP SCHEMA <catalog>.<schema> CASCADE;")


if __name__ == "__main__":
    main()
