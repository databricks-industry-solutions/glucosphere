#!/usr/bin/env python3
"""Grant a user or group VIEW-level access to every workspace object the app's
"Under the hood — powered by Databricks" panel deep-links to, so those links open
(instead of 403) for the demo audience.

Sibling to scripts/grant_app_sp.py — that grants the *app service principal* what the
app needs to RUN; this grants a *human principal* (user or group) what they need to
OPEN the linked objects + query the agents. Grant a GROUP once (recommended) rather
than per user.

Surfaces + levels (all verified 2026-06-05 via `databricks permissions get-permission-levels`):
  Unity Catalog (SQL GRANT):  USE CATALOG · USE SCHEMA · SELECT · EXECUTE (models) · READ VOLUME
  pipelines:                  CAN_VIEW          (DLT silver→gold)
  jobs:                       CAN_VIEW          (glucosphere-full-setup)
  experiments:                CAN_READ          (MLflow)
  serving-endpoints:          CAN_QUERY         (Glucosphere_Forecast_15min/30min)
  knowledge-assistants:       CAN_QUERY         (KA tile — Agent Bricks)
  supervisor-agents:          CAN_QUERY         (MAS tile — Agent Bricks)
  genie:                      CAN_RUN           (AI/BI Genie space, /api/2.0/permissions/genie/{id})

Resource discovery:
  - pipeline + job + warehouse come from `databricks bundle summary -t <target>`
  - workspace-global agents (KA/MAS tiles, Genie space, forecast endpoints) are matched by
    NAME: exact `Glucosphere_*` for the live deploy (empty suffix), or with `--suffix` appended
    for a sandbox. (As in teardown_target.py, an empty `--suffix` would over-match — so for the
    live deploy pass nothing and it uses the bare names.)

Usage:
  # live deploy, grant a group (no '@' → treated as a group):
  uv run python scripts/grant_viewers.py --principal glucosphere-viewers \
      --target gsphere --catalog mmt_aws_usw2 --schema glucosphere --profile fevm-mmt-aws-usw2
  # a user (has '@' → user_name); dry-run is the default, add --apply to grant:
  uv run python scripts/grant_viewers.py --principal alice@databricks.com --target gsphere \
      --catalog mmt_aws_usw2 --schema glucosphere --profile fevm-mmt-aws-usw2 --apply
  # a sandbox target's resources:
  uv run python scripts/grant_viewers.py --principal me@databricks.com --target gsphere_fw_v2 \
      --suffix _fw_v2 --catalog mmt_aws_usw2_catalog --schema glucosphere_fw_v2 --profile <p>
"""
import argparse
import json
import subprocess
import sys

REPO_ROOT = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."


def run_cli(args, profile, check=True):
    cmd = ["databricks", *args] + (["-p", profile] if profile else [])
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if check and r.returncode != 0:
        raise RuntimeError(f"`{' '.join(cmd)}` failed:\n{r.stderr.strip()}")
    return r.stdout.strip(), r.returncode


def cli_json(args, profile):
    out, _ = run_cli(args, profile)
    return json.loads(out) if out else {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--principal", required=True, help="user email, group name, or service-principal application-id")
    ap.add_argument("--principal-type", choices=["auto", "user", "group", "service-principal"], default="auto",
                    help="auto (default): '@'→user, 36-char UUID→service-principal, else group. "
                         "On the DAIS workspace the audience is fronted by a service principal — pass that "
                         "SP's application-id (auto-detected as service-principal, or force with this flag).")
    ap.add_argument("--target", required=True, help="bundle target (e.g. gsphere) — resolves pipeline/job/warehouse")
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--suffix", default="", help="harness_suffix on workspace-global agent names (default '' = live)")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--apply", action="store_true", help="actually grant (default: dry-run)")
    a = ap.parse_args()
    p, sfx, profile, apply = a.principal, a.suffix, a.profile, a.apply
    import re
    ptype = a.principal_type
    if ptype == "auto":
        ptype = "service-principal" if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", p) \
            else ("user" if "@" in p else "group")
    acl_key = {"user": "user_name", "group": "group_name", "service-principal": "service_principal_name"}[ptype]
    print(f"=== grant-viewers ({'APPLY' if apply else 'DRY-RUN'}) — {acl_key}={p} · target={a.target} · {a.catalog}.{a.schema} ===\n")

    def perm(obj_type, obj_id, level, label):
        body = json.dumps({"access_control_list": [{acl_key: p, "permission_level": level}]})
        print(f"  {obj_type:22s} {label}: {level}")
        if apply:
            _, rc = run_cli(["permissions", "update", obj_type, str(obj_id), "--json", body], profile, check=False)
            print(f"      {'✓' if rc == 0 else '✗ FAILED'}")

    # --- resolve bundle resources (pipeline / job / warehouse) -------------------
    summ = cli_json(["bundle", "summary", "-t", a.target, "-o", "json"], profile).get("resources", {})
    pipe = (summ.get("pipelines", {}) or {}).get("cgm_silver_gold", {})
    job = (summ.get("jobs", {}) or {}).get("glucosphere_full_setup", {})
    wh = (summ.get("sql_warehouses", {}) or {}).get("glucosphere_warehouse", {})

    # --- 1. Unity Catalog grants (SQL on the bundle warehouse) -------------------
    grants = [
        f"GRANT USE CATALOG ON CATALOG {a.catalog} TO `{p}`",
        f"GRANT USE SCHEMA ON SCHEMA {a.catalog}.{a.schema} TO `{p}`",
        f"GRANT SELECT ON SCHEMA {a.catalog}.{a.schema} TO `{p}`",
        f"GRANT EXECUTE ON SCHEMA {a.catalog}.{a.schema} TO `{p}`",          # registered models
        f"GRANT READ VOLUME ON VOLUME {a.catalog}.{a.schema}.pipeline_data TO `{p}`",
    ]
    print("  unity-catalog          (SQL GRANT): USE CATALOG / USE SCHEMA / SELECT / EXECUTE / READ VOLUME")
    if apply and wh.get("id"):
        for stmt in grants:
            body = json.dumps({"warehouse_id": wh["id"], "statement": stmt, "wait_timeout": "30s"})
            _, rc = run_cli(["api", "post", "/api/2.0/sql/statements", "--json", body], profile, check=False)
            print(f"      {'✓' if rc == 0 else '✗'} {stmt.split(' ON ')[0]}")
    elif apply:
        print("      ✗ no bundle warehouse id resolved — run a deploy first, or grant UC manually")

    # --- 2. pipeline + job + MLflow experiments ----------------------------------
    if pipe.get("id"):
        perm("pipelines", pipe["id"], "CAN_VIEW", "cgm_silver_gold")
    if job.get("id"):
        perm("jobs", job["id"], "CAN_VIEW", "glucosphere_full_setup")
    exps = cli_json(["experiments", "search-experiments", "-o", "json"], profile)
    exps = exps if isinstance(exps, list) else exps.get("experiments", [])
    # Scope to THIS target's deploy path (experiment names are the notebook paths
    # `…/.bundle/glucosphere/<target>/files/…`) so we don't grant on other targets' experiments.
    for e in [x for x in exps if f"/glucosphere/{a.target}/files/" in (x.get("name", "") or "")]:
        perm("experiments", e["experiment_id"], "CAN_READ", e.get("name", ""))

    # --- 3. workspace-global agents (by name; suffix-aware) ----------------------
    fc = [f"Glucosphere_Forecast_15min{sfx}", f"Glucosphere_Forecast_30min{sfx}"]
    eps = cli_json(["serving-endpoints", "list", "-o", "json"], profile)
    eps = eps if isinstance(eps, list) else eps.get("endpoints", [])
    for e in eps:
        if e.get("name") in fc:
            perm("serving-endpoints", e.get("id"), "CAN_QUERY", e["name"])

    tiles = cli_json(["api", "get", "/api/2.0/tiles"], profile)
    tiles = tiles.get("tiles") or tiles.get("items") or []
    for t in tiles:
        nm = t.get("name") or t.get("display_name") or ""
        tid = t.get("tile_id") or t.get("id")
        if nm == f"Glucosphere_KA{sfx}":
            perm("knowledge-assistants", tid, "CAN_QUERY", nm)
        elif nm == f"Glucosphere_Supervisor{sfx}":
            perm("supervisor-agents", tid, "CAN_QUERY", nm)

    # --- 4. Genie space (data-room) ----------------------------------------------
    rooms = cli_json(["api", "get", "/api/2.0/data-rooms"], profile)
    rooms = rooms.get("data_rooms") or rooms.get("dataRooms") or rooms.get("items") or []
    for r in rooms:
        if (r.get("display_name") or r.get("title") or "") == f"Glucosphere_Intelligence{sfx}":
            gid = r.get("id") or r.get("space_id")
            body = json.dumps({"access_control_list": [{acl_key: p, "permission_level": "CAN_RUN"}]})
            print(f"  genie                  Glucosphere_Intelligence{sfx} ({gid}): CAN_RUN")
            if apply:
                _, rc = run_cli(["api", "patch", f"/api/2.0/permissions/genie/{gid}", "--json", body], profile, check=False)
                print(f"      {'✓' if rc == 0 else '✗ FAILED'}")

    if not apply:
        print("\n  DRY-RUN — nothing granted. Re-run with --apply.")


if __name__ == "__main__":
    main()
