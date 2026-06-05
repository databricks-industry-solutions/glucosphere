#!/usr/bin/env python3
"""Grant the demo audience everything they need: CAN_USE on the deployed app itself,
plus VIEW-level access to every workspace object the app's "Under the hood — powered
by Databricks" panel deep-links to — so the app opens and those links resolve (instead
of 403) for the audience.

Sibling to scripts/grant_app_sp.py — that grants the *app service principal* what the
app needs to RUN; this grants the *audience principal* (user, group, or SP) what they
need to OPEN the app + the linked objects + query the agents. Grant a GROUP once
(recommended) rather than per user.

`--revoke` reverses every grant for a principal across all surfaces (UC `REVOKE`; ACL
objects via read-modify-write `set` of direct grants minus the principal — inherited
admin/manage is preserved by inheritance). Use it for post-demo / teardown cleanup, or
after sharing to the `users` group makes individual grants redundant.

Surfaces + levels (all verified via `databricks {permissions,apps} get-permission-levels`):
  apps:                       CAN_USE           (open the deployed app — dedicated
                                                 `apps update-permissions`, NOT the generic enum)
  Unity Catalog (SQL GRANT):  USE CATALOG · USE SCHEMA · SELECT · EXECUTE (models) · READ VOLUME
      NOTE: UC grants need an ACCOUNT-level principal (named user, SP, or account group).
      The workspace-local `users` group CANNOT hold UC grants ("PRINCIPAL_DOES_NOT_EXIST"),
      so for a whole-workspace audience the app + non-UC deep-links open via `users`, but the
      Catalog/data deep-link needs named users or an account-level group.
  pipelines:                  CAN_VIEW          (DLT silver→gold)
  jobs:                       CAN_VIEW          (glucosphere-full-setup)
  experiments / notebooks:    CAN_READ          (MLflow — notebook-backed experiments inherit
                                                 their ACL from the notebook, so granted there)
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
      --target gsphere --catalog mmt_aws_usw2 --schema glucosphere --profile <profile>
  # a user (has '@' → user_name); dry-run is the default, add --apply to grant:
  uv run python scripts/grant_viewers.py --principal user@example.com --target gsphere \
      --catalog mmt_aws_usw2 --schema glucosphere --profile <profile> --apply
  # a sandbox target's resources:
  uv run python scripts/grant_viewers.py --principal user@example.com --target gsphere_fw_v2 \
      --suffix _fw_v2 --catalog mmt_aws_usw2_catalog --schema glucosphere_fw_v2 --profile <p>
  # REVOKE a principal across all surfaces (e.g. after granting the `users` group):
  uv run python scripts/grant_viewers.py --principal user@example.com --revoke --target gsphere \
      --catalog mmt_aws_usw2 --schema glucosphere --profile <profile> --apply
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
    ap.add_argument("--apply", action="store_true", help="actually grant/revoke (default: dry-run)")
    ap.add_argument("--revoke", action="store_true",
                    help="REVOKE the principal's access across every surface instead of granting it "
                         "(reverse of the default grant — for post-demo / teardown cleanup)")
    a = ap.parse_args()
    p, sfx, profile, apply, revoke = a.principal, a.suffix, a.profile, a.apply, a.revoke
    import re
    ptype = a.principal_type
    if ptype == "auto":
        ptype = "service-principal" if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", p) \
            else ("user" if "@" in p else "group")
    acl_key = {"user": "user_name", "group": "group_name", "service-principal": "service_principal_name"}[ptype]
    action = "REVOKE" if revoke else "GRANT"
    print(f"=== grant-viewers ({action} · {'APPLY' if apply else 'DRY-RUN'}) — {acl_key}={p} · target={a.target} · {a.catalog}.{a.schema} ===\n")

    PRINCIPAL_KEYS = ("user_name", "group_name", "service_principal_name")

    def acl_without_principal(acl):
        """Settable ACL body that removes our principal: keep only DIRECT (non-inherited)
        grants of every OTHER principal. Inherited entries (e.g. admins) are intentionally
        dropped — inheritance is recomputed by the platform from the parent object, so a
        `set` (PUT) of direct-only entries preserves admin/manage automatically."""
        out = []
        for entry in acl:
            k = next((kk for kk in PRINCIPAL_KEYS if entry.get(kk)), None)
            if not k or entry[k] == p:                       # skip malformed + the target principal
                continue
            for lvl in sorted({pl["permission_level"] for pl in entry.get("all_permissions", []) if not pl.get("inherited")}):
                out.append({k: entry[k], "permission_level": lvl})
        return out

    def revoke_acl(obj_type, obj_id, label, get_cmd, set_cmd):
        """Read-modify-write removal for an ACL object. No-op (no PUT) if the principal
        isn't on the ACL, so we never needlessly rewrite an ACL we aren't changing."""
        cur = cli_json(get_cmd, profile)
        acl = cur.get("access_control_list", [])
        present = any(e.get(acl_key) == p for e in acl)
        print(f"  {obj_type:22s} {label}: REVOKE  {'(present)' if present else '(not on ACL — noop)'}")
        if apply and present:
            body = json.dumps({"access_control_list": acl_without_principal(acl)})
            _, rc = run_cli(set_cmd + ["--json", body], profile, check=False)
            print(f"      {'✓' if rc == 0 else '✗ FAILED'}")

    def perm(obj_type, obj_id, level, label):
        if revoke:
            revoke_acl(obj_type, obj_id, label,
                       ["permissions", "get", obj_type, str(obj_id)],
                       ["permissions", "set", obj_type, str(obj_id)])
            return
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
    app = (summ.get("apps", {}) or {}).get("glucosphere_app", {})

    # --- 1. the Databricks App itself (CAN_USE — open the deployed app) ----------
    # Apps are NOT in the generic `permissions update` object-type enum, so the grant
    # goes through the dedicated `apps update-permissions` (additive PATCH — preserves
    # the existing CAN_MANAGE/admins ACL). Without this the audience can reach every
    # deep-link target below yet still be blocked from opening the app.
    if app.get("name"):
        if revoke:
            revoke_acl("apps", app["name"], app["name"],
                       ["apps", "get-permissions", app["name"]],
                       ["apps", "set-permissions", app["name"]])
        else:
            body = json.dumps({"access_control_list": [{acl_key: p, "permission_level": "CAN_USE"}]})
            print(f"  {'apps':22s} {app['name']}: CAN_USE")
            if apply:
                _, rc = run_cli(["apps", "update-permissions", app["name"], "--json", body], profile, check=False)
                print(f"      {'✓' if rc == 0 else '✗ FAILED'}")
    elif apply:
        print(f"  {'apps':22s} ✗ no bundle app resolved — check `bundle summary -t <target>`")

    # --- 2. Unity Catalog (SQL GRANT / REVOKE on the bundle warehouse) -----------
    verb, conn = ("REVOKE", "FROM") if revoke else ("GRANT", "TO")
    stmts = [
        f"{verb} USE CATALOG ON CATALOG {a.catalog} {conn} `{p}`",
        f"{verb} USE SCHEMA ON SCHEMA {a.catalog}.{a.schema} {conn} `{p}`",
        f"{verb} SELECT ON SCHEMA {a.catalog}.{a.schema} {conn} `{p}`",
        f"{verb} EXECUTE ON SCHEMA {a.catalog}.{a.schema} {conn} `{p}`",          # registered models
        f"{verb} READ VOLUME ON VOLUME {a.catalog}.{a.schema}.pipeline_data {conn} `{p}`",
    ]
    print(f"  unity-catalog          (SQL {verb}): USE CATALOG / USE SCHEMA / SELECT / EXECUTE / READ VOLUME")
    if apply and wh.get("id"):
        for stmt in stmts:
            body = json.dumps({"warehouse_id": wh["id"], "statement": stmt, "wait_timeout": "30s"})
            out, rc = run_cli(["api", "post", "/api/2.0/sql/statements", "--json", body], profile, check=False)
            # The SQL-statements API returns HTTP 200 even when the statement FAILS, so check
            # the response `status.state` — not just the exit code — or failures look like ✓.
            state, err = "", ""
            try:
                st = (json.loads(out) if out else {}).get("status", {})
                state, err = st.get("state", ""), (st.get("error") or {}).get("message", "")
            except (ValueError, AttributeError):
                pass
            ok = rc == 0 and state == "SUCCEEDED"
            print(f"      {'✓' if ok else '✗'} {stmt.split(' ON ')[0]}" + ("" if ok else f"  [{state or 'HTTP %d' % rc}]"))
            if not ok and "PRINCIPAL_DOES_NOT_EXIST" in err and ptype == "group":
                print(f"        ↳ '{p}' is not a Unity Catalog principal — workspace-local groups "
                      f"(e.g. `users`) can't hold UC grants. Use named users or an ACCOUNT-level "
                      f"group for the Catalog/data deep-link. (app + other deep-links still work.)")
    elif apply:
        print("      ✗ no bundle warehouse id resolved — run a deploy first, or change UC manually")

    # --- 3. pipeline + job + MLflow experiments ----------------------------------
    if pipe.get("id"):
        perm("pipelines", pipe["id"], "CAN_VIEW", "cgm_silver_gold")
    if job.get("id"):
        perm("jobs", job["id"], "CAN_VIEW", "glucosphere_full_setup")
    exps = cli_json(["experiments", "search-experiments", "-o", "json"], profile)
    exps = exps if isinstance(exps, list) else exps.get("experiments", [])
    # Scope to THIS target's deploy path (experiment names are the notebook paths
    # `…/.bundle/glucosphere/<target>/files/…`) so we don't grant on other targets' experiments.
    for e in [x for x in exps if f"/glucosphere/{a.target}/files/" in (x.get("name", "") or "")]:
        name = e.get("name", "") or ""
        # Notebook-backed experiments (name = a workspace notebook path) inherit their ACL
        # from the notebook object — `permissions update experiments` rejects them with
        # "not a experiment". Resolve the backing object and grant on the right type.
        out, rc = run_cli(["workspace", "get-status", name, "-o", "json"], profile, check=False) if name.startswith("/") else ("", 1)
        st = json.loads(out) if rc == 0 and out else {}
        if st.get("object_type") == "NOTEBOOK":
            perm("notebooks", st["object_id"], "CAN_READ", name)
        else:
            perm("experiments", e["experiment_id"], "CAN_READ", name)

    # --- 4. workspace-global agents (by name; suffix-aware) ----------------------
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

    # --- 5. Genie space (data-room) ----------------------------------------------
    rooms = cli_json(["api", "get", "/api/2.0/data-rooms"], profile)
    rooms = rooms.get("data_rooms") or rooms.get("dataRooms") or rooms.get("items") or []
    for r in rooms:
        if (r.get("display_name") or r.get("title") or "") == f"Glucosphere_Intelligence{sfx}":
            gid = r.get("id") or r.get("space_id")
            label = f"Glucosphere_Intelligence{sfx} ({gid})"
            if revoke:
                revoke_acl("genie", gid, label,
                           ["api", "get", f"/api/2.0/permissions/genie/{gid}"],
                           ["api", "put", f"/api/2.0/permissions/genie/{gid}"])
            else:
                body = json.dumps({"access_control_list": [{acl_key: p, "permission_level": "CAN_RUN"}]})
                print(f"  genie                  {label}: CAN_RUN")
                if apply:
                    _, rc = run_cli(["api", "patch", f"/api/2.0/permissions/genie/{gid}", "--json", body], profile, check=False)
                    print(f"      {'✓' if rc == 0 else '✗ FAILED'}")

    if not apply:
        print(f"\n  DRY-RUN — nothing {'revoked' if revoke else 'granted'}. Re-run with --apply.")


if __name__ == "__main__":
    main()
