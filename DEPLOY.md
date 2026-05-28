# Glucosphere Deployment Guide

This guide walks through deploying the full Glucosphere stack — data pipelines, ML models, and the dashboard app — to any Databricks workspace using the Databricks Asset Bundle (DAB). It is the **canonical deployment doc** for this repo.

> **New to the repo?** Read [`REPO_LAYOUT.md`](REPO_LAYOUT.md) first for a navigation guide: which files do what, the full workflow DAG, what's PR-shipped vs internal-refs.

> **If you're an agent following this guide:** do not skip steps and do not
> assume prior workspace state. Verify each step's output before moving on,
> and capture the KA/MAS/Genie IDs from the Step 7 job logs — they're needed for Step 8.

## Prerequisites

- [Databricks CLI v0.281.0+](https://docs.databricks.com/dev-tools/cli/install.html) installed (v0.281.0 added DAB dashboard support; earlier versions still work for jobs/pipelines/apps)
- Node.js 18+ (for the React frontend build, Step 5)
- [uv](https://docs.astral.sh/uv/) installed (manages the local Python env for `scripts/render_app_yaml.py`). Run `uv sync` from the repo root once — it reads `pyproject.toml` + `.python-version` and creates `.venv` pinned to Python 3.11. After that, prefix Python commands with `uv run` (e.g. `uv run python scripts/render_app_yaml.py …`) — no manual activation needed.
- Unity Catalog enabled on the target workspace
- `CREATE CATALOG` privilege (or a pre-existing catalog you own)
- Model serving enabled on the workspace
- A Multi-Agent Supervisor (MAS) endpoint deployed (see Step 3 below)

---

## Architecture Overview

The pipeline branches early on the `baseline_source` bundle variable
(`synthetic` vs `from_source` vs `from_table`); a `condition_task`
in `databricks.yml` dispatches to the right ingest notebook. Both branches
converge on `diabetes_data` and the downstream modeling spine is shared.

```
baseline_source dispatch (condition_task on var)
  ├─ synthetic → 01_synthetic_baseline.py
  │             (textbook phenotypes + AR(1); writes diabetes_data +
  │              baseline_timeseries + baseline_windows_metadata)
  └─ from_* (from_source | from_table)  → 02_ingest_real_baseline.py
                (HUPA-UCM download OR existing UC table; same three tables)
                              ↓
sanity_summary  (asserts diabetes_data non-empty + plausible)
                              ↓
04_pseudo_data_forecast_modeling.py
  → Tables: pseudo_clean_7d, pseudo_incident_*
  → UC Models: cgm_xgb_15m, cgm_xgb_30m
                              ↓
05_incident_inference_bidirectional.py
  → Tables: pseudo_incident_7d_labeled, fleet_forecast_incident
  (Active sibling for pipeline dispatch; SingleIncident is the simpler
   one-direction variant kept alongside as a reference.)
                              ↓                                  ─────┐
07_deploy_serving_endpoints.py                             │
  → Serving Endpoints (15m/30m forecast)                              │
                                                                      │
utils/additional_patient_info/ notebooks                              │
  → UC Volume: landing_zone/raw_patient_registry/                     │
  → UC Volume: landing_zone/raw_device_telemetry_stream/              │
                                                                      │
DLT Pipeline (transformations.sql)  ◄─────────────────────────────────┘
  → LIVE: silver_patient_registry
  → LIVE: silver_device_telemetry_stream
  → LIVE: silver_patient_readings
  → LIVE: gold_patient_device_readings  ──→ App SQL queries

08_genie_ka_mas.py
  → Genie space (gold_patient_device_readings)    ──→ App /api/genie/query
  → KA endpoint (RAG over assets/who_docs/WHO_NCD_NCS_99.2.pdf, copied to UC Volume landing_zone/who_docs/)
                                                ┐
  → MAS endpoint (Multi-Agent Supervisor)       │ routes clinical-guidance Qs → KA,
                                                │ structured-data Qs → Genie
                                                  ──→ App /api/agent/query

09_grant_app_permissions.py
  → App SP grants on UC + endpoints + warehouse + Genie + KA
```

---

## Step 1: Authenticate

```bash
databricks auth login --host https://<your-workspace>.azuredatabricks.net
```

Or set environment variables:
```bash
export DATABRICKS_HOST=https://<your-workspace>.azuredatabricks.net
export DATABRICKS_TOKEN=<your-token>
```

---

## Step 2: Configure Variables via `.env.bundle`

Per-operator workspace-specific values live in `.env.bundle` (gitignored).
Copy the template and fill in your three required values:

```bash
cp .env.bundle.example .env.bundle
# edit .env.bundle and fill in (note: `export` is REQUIRED — without it the
# variables stay shell-local and the databricks CLI subprocess does not see them):
#   export BUNDLE_VAR_catalog=<your-catalog>
#   export BUNDLE_VAR_schema=<your-schema>
#   export DATABRICKS_CONFIG_PROFILE=<your-profile>
```

Top-level bundle variables (defined in `databricks.yml`):

| Variable | Where set | Default | Notes |
|---|---|---|---|
| `catalog` | `.env.bundle` (`BUNDLE_VAR_catalog`) | `glucosphere_catalog` (placeholder) | Operator's UC catalog |
| `schema` | `.env.bundle` (`BUNDLE_VAR_schema`) | `glucosphere_schema` (placeholder) | UC schema |
| `baseline_source` | `.env.bundle` (optional) | `from_source` | `synthetic` / `from_source` / `from_table` |
| `source_catalog` / `source_schema` / `source_table` | `.env.bundle` (optional) | `""` | Used by `from_table` mode; empty triggers auto-detect |
| `app_name` | `.env.bundle` (optional) | `glucosphere-app` | Databricks App display name |
| `dev_initials` | `.env.bundle` (optional) | `user` | Harness target suffix for collision avoidance when sharing a workspace; ≤7 chars |
| `app_basename` | `.env.bundle` (optional) | `glucosphere` | Harness base name (shorten to fit the 30-char App limit if needed) |

`warehouse_id` is **not** a bundle variable. The bundle declares a
`sql_warehouses.glucosphere_warehouse` resource that creates the warehouse
on first deploy. `scripts/render_app_yaml.py` discovers it by deterministic
name and writes `WAREHOUSE_ID` into `App/databricks/app.yaml`.

> **Adding a new live target**: append a stanza to `databricks.yml:targets`
> with `workspace.host` only — no per-target `variables:` block. Operator's
> `.env.bundle` supplies all data values.

---

## Step 3: Create the Multi-Agent Supervisor Endpoint

The MAS endpoint is a Databricks Model Serving endpoint running a multi-agent supervisor that orchestrates diabetes-coach queries. It is **not** created by this bundle — it must be set up separately.

1. In your target workspace, open **Serving → Create serving endpoint**
2. Deploy the MAS configuration from your agent framework
3. Note the endpoint name (e.g. `glucosphere-mas-endpoint`)
4. Set it in your deployment: `--var endpoint_name=glucosphere-mas-endpoint`

---

## Step 4: Create the Genie Room

1. In your target workspace, open **Genie → New room**
2. Add `{catalog}.{schema}.gold_patient_device_readings` as a data source
3. Configure the room with CGM-specific instructions (refer to the existing room at the buildathon workspace for reference)
4. From the room URL, copy the room ID (the hex string after `/genie/rooms/`)
5. Set it: `--var genie_space_id=<room-id>`

---

## Step 5: Build the React Frontend

```bash
cd App
npm install
npm run build
# This produces App/databricks/dist/ which the Flask app serves
```

---

## Step 6: Deploy the Bundle (two-pass on first deploy)

On a fresh workspace the first deploy creates the bundle-managed
`sql_warehouses.glucosphere_warehouse` resource. `render_app_yaml.py` then
discovers it by name and writes `WAREHOUSE_ID` into `App/databricks/app.yaml`.
The second deploy syncs the updated app.yaml to the workspace.

```bash
# Make sure .env.bundle is filled in (see Step 2), then:
source .env.bundle
databricks bundle deploy -t <target>            # Pass 1: creates warehouse + apps + jobs
uv run python scripts/render_app_yaml.py --target <target>    # Discover warehouse + rewrite app.yaml
databricks bundle deploy -t <target>            # Pass 2: sync updated app.yaml
```

Subsequent deploys are single-pass (warehouse already exists; render still
useful when catalog/schema/etc. change in `.env.bundle`).

`-t <target>` is always required — no `default: true` target exists.

---

## Step 7: Run the Setup Job

```bash
databricks bundle run glucosphere_full_setup -t <target>
```

This runs the end-to-end pipeline below.

### Job DAG

```
validate_baseline_source       (enum check on baseline_source; print run banner)
         ↓
check_pre_baseline_grants      (verify catalog/schema/table/volume/function perms)
         ↓
dispatch_baseline_source       (condition_task: baseline_source == "synthetic"?)
         ↓                ↓
  true  ↙               ↘  false
generate_synthetic_   ingest_real_baseline
  baseline            (HUPA-UCM download OR existing UC table copy;
  (textbook +          writes diabetes_data + baseline_timeseries
   AR(1); writes       + baseline_windows_metadata)
   same three tables)
         ↘                ↙
sanity_summary           (run_if AT_LEAST_ONE_SUCCESS;
                          asserts diabetes_data non-empty + plausible)
         ↓
datagen_modeling         (04_*: pseudo CGM data + XGBoost training)
         ↓
incident_inference       (05_*: device calibration bug simulation + inference)
         ↓                            ↓
deploy_model_endpoints       generate_patient_device_data
         ↓                       ↓                ↓
         ↘            create_patient_registry  create_device_telemetry
          ↘                      ↓
           ↘             run_dlt_pipeline      (silver/gold from landing_zone)
            ↘                    ↓
             ↘          create_genie_ka_mas    (KA + Genie + MAS endpoints)
              ↘                  ↓
               ↘ check_post_endpoint_grants    (verify KA/MAS/Genie exist before grant)
                ↘                ↓
                 ↘    grant_app_permissions    (app SP access on UC + endpoints + warehouse)
```

The validate + sanity tasks (added in C.5) are fail-fast guards: they catch
operator typos and silent baseline-write failures before they cost ~45 min
of downstream modeling compute.

> **Note:** The `generate_patient_device_data` task references the Jupyter notebooks in `Data_DataGen_ModelForecast/utils/additional_patient_info/`. If those notebooks need to be converted to Databricks-native format before running, do so with:
> ```bash
> databricks workspace import --format JUPYTER <notebook.ipynb> <workspace-path>
> ```

---

## Step 8: Re-render App Environment Variables with Real KA/MAS/Genie IDs

The Step 7 setup job ran `08_genie_ka_mas.py` which created (or reused) the KA, MAS, and Genie space. Capture their IDs from the job logs, then re-run `render_app_yaml.py` with the override flags to bake them into `App/databricks/app.yaml`, then redeploy:

```bash
source .env.bundle
uv run python scripts/render_app_yaml.py \
    --target <target> \
    --profile <profile> \
    --mas-endpoint   <mas-endpoint-name> \
    --ka-endpoint    <ka-endpoint-name> \
    --genie-space-id <genie-space-id>
databricks bundle deploy -t <target> --profile <profile>
```

On subsequent runs against the same workspace, `08_genie_ka_mas.py` reuses the existing KA/MAS/Genie by name, so the IDs in `app.yaml` stay valid — Step 8 is only required on the first deploy to a fresh workspace.

---

## Step 9: Deploy and Start the App

**Required.** Apps have an independent lifecycle from Jobs in DABs — the setup job in Step 7 does NOT deploy the App's source code or start its compute. This step uploads `App/` into the App container and starts it.

```bash
source .env.bundle
databricks bundle run glucosphere_app -t <target> --profile <profile>
```

This single command does both `apps deploy` + `apps start` atomically and matches the bundle-managed pattern used by every other step here. Expected output ends with `App started successfully` and the App URL.

Or manage through the UI: **Apps → glucosphere-app → Deploy**. (The UI shows "App is unavailable" until you either run the command above OR click Deploy in the UI.)

---

## Step 10: Smoke-test the deployed app

Before declaring the deployment "done," walk through these checks in the browser. Each catches a specific class of post-deploy issue (UI build, backend wiring, agent endpoints, Genie binding, data access). All should complete in <5 minutes.

Open the app URL from `databricks apps get glucosphere-app --output json | jq -r .url`, then:

- [ ] **Home page loads** — no blank screen, no JS console errors. (If blank: React frontend wasn't built; run `npm run build` in `App/` then re-run `databricks bundle run glucosphere_app -t <target>`.)
- [ ] **Navigate to "Device Support Dashboard"** in the left sidebar. Device table populates with rows. (If empty: gold table `${catalog}.${schema}.gold_patient_device_readings` not populated → DLT pipeline didn't run successfully.)
- [ ] **Click a device row → "Run Clinical Analysis"** — wait ~30-60s. Text analysis appears with device-specific glucose stats. (If 404 ENDPOINT_NOT_FOUND: `app.yaml` references a deleted MAS endpoint — re-render with current `mas-<hash>-endpoint`. If 403 PERMISSION_DENIED: re-run `grant_app_permissions` task.)
- [ ] **Open Genie (or Chat / Ask) panel** and ask a natural-language question like *"How many distinct devices reported in the last hour?"* — response should include a SQL query and a result. (If errors: GENIE_SPACE_ID points at a non-existent space → re-render app.yaml with current Genie space ID.)
- [ ] **Refresh metrics tiles on the home page** — patient count, device count, high-risk alert count should update without errors. (If errors: app SP missing `USE CATALOG` / `SELECT` on gold tables → re-run `grant_app_permissions` or check Catalog Explorer permissions.)
- [ ] **Export to Chart button** (Device Support → Clinical Analysis section) — currently shows "(placeholder)" + disabled; tooltip on hover. Future feature; not a failure.

If all 5 functional checks pass, the deployment is verified end-to-end. Any failure narrows the diagnostic surface significantly (the bracketed hints above name the most common cause for each).

---

## Target-specific notes

Two bundle targets are actively used. Pick the one that matches your workspace; commands below show both.

### Target `mmt_aws_usw2` (workspace `fevm-mmt-aws-usw2`, AWS us-west-2) — current active demo target

```bash
# 1. Render app.yaml for mmt_aws_usw2 (rewrites catalog/schema/warehouse in place)
uv run python scripts/render_app_yaml.py --target mmt_aws_usw2

# 2. Deploy the bundle (job + DLT pipeline + app shell + permission grants)
databricks bundle deploy -t mmt_aws_usw2 --profile fevm-mmt-aws-usw2

# 3. Run the full setup job (data gen → ML training → endpoint deploy → Genie + KA + MAS creation)
databricks bundle run glucosphere_full_setup -t mmt_aws_usw2 --profile fevm-mmt-aws-usw2

# 4. After step 3 completes, re-render with discovered IDs and redeploy the app
uv run python scripts/render_app_yaml.py --target mmt_aws_usw2 \
    --mas-endpoint   <name-from-step-3>  \
    --ka-endpoint    <name-from-step-3>  \
    --genie-space-id <id-from-step-3>
databricks bundle deploy -t mmt_aws_usw2 --profile fevm-mmt-aws-usw2

# 5. Restart the live app so the new bundle + app.yaml take effect
databricks bundle run glucosphere_app -t mmt_aws_usw2 --profile fevm-mmt-aws-usw2
```

### Target `hls_amer` (workspace `fe-vm-hls-amer`, AWS) — historical / blocked

Originally added on `feature/dual-baseline-hls-amer` branch. **Currently blocked by 100/100 app quota** on that workspace (errored apps systemically un-deletable from this workspace alone due to cross-workspace SP entanglement). Re-enable once the parent workspace SP cleanup unblocks the quota.

Same 4-step workflow as `mmt_aws_usw2` above, swap `-t mmt_aws_usw2 --profile fevm-mmt-aws-usw2` for `-t hls_amer --profile <your-hls-amer-profile>`.

### ⚠️ `--var baseline_source` placement (gotcha)

When overriding the baseline mode, `--var` MUST go on `bundle deploy`, **not** on `bundle run`:

```bash
# ✅ Right — --var on deploy (interpolates at deploy time, drives condition_task)
databricks bundle deploy -t <target> --var "baseline_source=from_source" --profile <profile>
databricks bundle run    -t <target> glucosphere_full_setup --profile <profile>

# ❌ Wrong — --var on run is ignored by condition_task interpolation
databricks bundle deploy -t <target> --profile <profile>
databricks bundle run    -t <target> glucosphere_full_setup --var "baseline_source=from_source" --profile <profile>
```

(Burned 2026-05-16 evening when the run was misrouted to synthetic instead of real.)

### `render_app_yaml.py` — what it does

`scripts/render_app_yaml.py` reads the resolved bundle vars and rewrites the 7 per-target fields in `App/databricks/app.yaml` (4 env values + 3 resource block names/IDs). It is idempotent — re-run any time you switch target or discover new endpoint/Genie IDs. As of 2026-05-19, the committed `App/databricks/app.yaml` has `mmt_aws_usw2`-target values from the most recent render — `bundle deploy -t mmt_aws_usw2` works directly without re-rendering, but ANY OTHER target requires `render_app_yaml.py --target <your-target>` first to avoid mismatched catalog/schema/endpoint references in the deployed app.

### Grants preflight — the deployed app's service principal needs

- `USE CATALOG <your-catalog>`
- `USE SCHEMA <your-catalog>.<your-schema>`
- `SELECT` on the silver / gold tables consumed by the Flask app
- `CAN_USE` on the SQL warehouse (handled by the `sql-warehouse` resource block in `app.yaml`)
- `CAN_QUERY` on the MAS and KA serving endpoints (handled by the `mas-endpoint` / `ka-endpoint` resource blocks)
- `CAN_RUN` on the Genie space (not yet declared as a resource block in `app.yaml`; handled by `09_grant_app_permissions.py` during the setup job)

The `glucosphere_full_setup` job's `grant_app_permissions` task wires most of these automatically once the app and the endpoints exist on the target workspace.

---

## Teardown

```bash
databricks bundle destroy
```

This removes the job, DLT pipeline, and app resource from the workspace. It does **not** delete Unity Catalog tables, volumes, or registered models.

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `ENDPOINT_NAME not set` | Set `ENDPOINT_NAME` env var in `app.yaml` or App settings |
| `GENIE_SPACE_ID not set` | Set `GENIE_SPACE_ID` env var in `app.yaml` or App settings |
| `DATABRICKS_TOKEN not set` | Ensure the App is deployed (token is auto-injected by runtime) |
| `CATALOG_NOT_FOUND` during job task | Pre-flight catalog/schema/volume creation was skipped — create them before `bundle run` (see Step 0 framing below) |
| `deploy_model_endpoints` task fails | Ensure model serving is enabled on the workspace |
| `create_genie_ka_mas` task fails | Check Agent Bricks / Genie are available on this workspace tier; KA endpoint must reach `ONLINE` status before MAS is created (10 min timeout) |
| App shows "Not Found" | Frontend build wasn't run (`npm run build` in `App/`) before deploy |
| App shows no data (SQL 500 errors) | Gold table doesn't exist — check `run_dlt_pipeline` task in the Step 7 setup job completed; or app SP missing grants — re-run `grant_app_permissions` task |
| App "Deeper Analysis" returns 404 ENDPOINT_NOT_FOUND | `app.yaml` references a deleted MAS endpoint — re-render with current `mas-<hash>-endpoint` and redeploy |
| App "Deeper Analysis" returns 403 PERMISSION_DENIED | App SP not granted CAN_QUERY on MAS endpoint — re-run `grant_app_permissions` |
| `databricks bundle run` fails with variable error | Pass `--profile <your-profile>` and (if overriding) `--var` flags on `bundle deploy`, not `bundle run` |
| Genie auto-discovery fails | Set `GENIE_SPACE_ID` parameter explicitly in the job task parameters or via `--var genie_space_id=<id>` |
| DLT pipeline fails on `pseudo_incident_7d_labeled` | Run the setup job first; `05_incident_inference_bidirectional.py` creates this table |
| DLT pipeline fails on landing zone paths | Run `generate_patient_device_data` task first |
| SQL queries return no data | Verify DLT pipeline ran successfully and gold table exists |
| Catalog creation permission error | Request `CREATE CATALOG` privilege or use an existing catalog |

### Pre-flight: catalog / schema / volume creation

The bundle assumes the catalog already exists. If you're deploying to a brand-new workspace with no catalog yet, run this once before `bundle deploy` (replace `<your-catalog>` / `<your-schema>` / `<your-warehouse-id>`):

```bash
databricks statement-execution execute-statement \
  --profile <your-profile> --warehouse-id <your-warehouse-id> \
  --statement "CREATE CATALOG IF NOT EXISTS <your-catalog>"

databricks statement-execution execute-statement \
  --profile <your-profile> --warehouse-id <your-warehouse-id> \
  --statement "CREATE SCHEMA IF NOT EXISTS <your-catalog>.<your-schema>"

databricks statement-execution execute-statement \
  --profile <your-profile> --warehouse-id <your-warehouse-id> \
  --statement "CREATE VOLUME IF NOT EXISTS <your-catalog>.<your-schema>.landing_zone"
```

If there's no SQL warehouse yet, create a Serverless SQL warehouse from the UI: **SQL Warehouses → Create warehouse → Serverless**.

---

## Verification checklist

End-state checks after a successful end-to-end deploy:

- [ ] Catalog `<your-catalog>` and schema `<your-schema>` exist
- [ ] All `glucosphere_full_setup` job tasks completed successfully (green in Workflows UI)
- [ ] Gold table exists: `<your-catalog>.<your-schema>.gold_patient_device_readings`
- [ ] Incident table exists: `<your-catalog>.<your-schema>.pseudo_incident_7d_labeled`
- [ ] MAS serving endpoint is in `READY` state
- [ ] KA serving endpoint is in `ONLINE` state
- [ ] App resource status is `RUNNING`
- [ ] All Step 10 smoke-test checks pass in the browser

---

## Agent-assisted deployment

If you're using Claude Code (or another AI agent) to help drive this deployment, the following accelerators will save time.

### Skills to activate at session start

(Available via the Skill tool; install via plugin marketplaces if missing — see Glucosphere plugin personas memory for canonical install sets.)

- `databricks-config` — authenticate the CLI and set the profile
- `databricks-asset-bundles` — DAB schema reference, common commands, troubleshooting
- `databricks-genie` — when reaching Step 4 (create Genie room)
- `databricks-model-serving` — when reaching Step 3 (MAS endpoint setup)
- `databricks-app-python` / `databricks-app-apx` — Flask/React app patterns
- `salesforce-asq` — if you want to post a milestone update to an ASQ after deploy

### Memory + ref_notes to pre-load for Glucosphere context

If working on the Glucosphere repo specifically, invoke the `glucosphere-resume` skill at session start, or read these manually:

- `~/.claude/projects/-Users-…-glucosphere/memory/MEMORY.md` — index
- Latest `project_glucosphere_session_state_*.md` — current branch state
- `reference_glucosphere_deploy_commands.md` — verified CLI patterns
- ⚠️ `feedback_var_placement_at_deploy_time.md` — `--var` MUST go on `bundle deploy`, NOT `bundle run` (see gotcha section above)
- ⚠️ `feedback_always_verify.md` — never cite current-state defaults (like `baseline_source`) from memory; always grep `databricks.yml` first
- `ref_notes/<latest-date>_end-of-day-snapshot.md` — most recent handoff state

### Long-running operations

The `glucosphere_full_setup` job runs ~45-60 minutes end-to-end. Don't block on it synchronously — submit via:

```bash
databricks bundle run -t <target> glucosphere_full_setup --profile <profile> --no-wait
```

Capture the `run_id` from the output, then poll until terminal:

```bash
until [ "$(databricks jobs get-run <RUN_ID> --profile <profile> 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("state",{}).get("life_cycle_state",""))')" = "TERMINATED" ]; \
do sleep 90; done && \
databricks jobs get-run <RUN_ID> --profile <profile> \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); s=d.get("state",{}); print("FINAL:", s.get("result_state"), s.get("state_message","")[:200])'
```

### Verification discipline (don't claim "done" without these)

- After Step 6 (`bundle deploy`): `bundle validate` exits 0; resources appear in workspace
- After Step 7 (`glucosphere_full_setup` run): polling returns `TERMINATED` with `result_state=SUCCESS`, not just "submitted"
- After Step 9 (`bundle run glucosphere_app`): `databricks apps get <name>` returns `compute_status.state == ACTIVE` and `app_status.state == RUNNING` with a non-empty `active_deployment.deployment_id`
- Step 10 smoke-test checks (above) are mandatory before declaring the deploy verified end-to-end

### Common agent lapses to avoid

- **Don't assume catalog state from memory.** "The catalog already exists" might be true for an old workspace but not the current target. Either run the pre-flight catalog/schema/volume creation snippet (above) to create-if-not-exists, or query the catalog list first.
- **Don't cite default values from memory.** `baseline_source`, `catalog`, `warehouse_id` etc. can flip between snapshot date and now. Always grep `databricks.yml` for the current value before stating it as fact. (2026-05-19 lapse logged in `feedback_always_verify.md`.)
- **Don't conflate `committed locally` / `pushed to origin` / `deployed to workspace` / `app restarted`.** These are four different state transitions. State exactly which one you did.
- **App resources don't return a job `run_id`** when you run `bundle run <app-name>` — they're synchronous. Other resources (jobs, pipelines) do return a `run_id` that needs polling.

---

## Key file locations

```
glucosphere/
├── databricks.yml                          ← Bundle manifest (jobs, pipelines, app)
├── DEPLOY.md                               ← This file (canonical deployment guide)
├── CHANGELOG.md                            ← Keep-a-Changelog format
├── App/
│   ├── databricks/
│   │   ├── app.py                          ← Flask backend
│   │   ├── app.yaml                        ← App config (rendered by scripts/render_app_yaml.py)
│   │   └── static/                         ← React build output (generated by npm run build)
│   ├── src/                                ← React source
│   └── vite.config.js
├── Data_DataGen_ModelForecast/
│   ├── 01_synthetic_baseline.py
│   ├── 02_ingest_real_baseline.py
│   ├── 03_compare_baseline_modes.py
│   ├── 04_pseudo_data_forecast_modeling.py
│   ├── 05_incident_inference_bidirectional.py   ← active inference (pipeline dispatch)
│   ├── 06_incident_inference_single.py  ← sibling reference
│   ├── 07_deploy_serving_endpoints.py
│   ├── 08_genie_ka_mas.py
│   ├── 09_grant_app_permissions.py
│   ├── utils/additional_patient_info/      ← Patient/device data generators
│   └── configs/baseline_config.yaml
└── scripts/
    ├── render_app_yaml.py                  ← Rewrites App/databricks/app.yaml per target
    └── grant_app_permissions.py            ← Local fallback permissions script
```
