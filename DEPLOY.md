# Glucosphere Deployment Guide

This guide walks through deploying the full Glucosphere stack — data pipelines, ML models, and the dashboard app — to any Databricks workspace using the Databricks Asset Bundle (DAB).

## Prerequisites

- [Databricks CLI v0.220+](https://docs.databricks.com/dev-tools/cli/install.html) installed and authenticated
- Unity Catalog enabled on the target workspace
- `CREATE CATALOG` privilege (or a pre-existing catalog you own)
- Model serving enabled on the workspace
- A Multi-Agent Supervisor (MAS) endpoint deployed (see Step 3 below)

---

## Architecture Overview

```
01_download_data          → UC Volume: {catalog}.{schema}.data/
02_parseNcombine          → Delta Table: {catalog}.{schema}.diabetes_data
03_extract_baseline       → Delta Tables: baseline time-series
04_datagen_modeling       → Tables: pseudo_clean_7d, pseudo_incident_*
                            UC Models: cgm_xgb_15m, cgm_xgb_30m
05_incident_inference     → Table: pseudo_incident_7d_labeled  ─────┐
                            Table: fleet_forecast_incident           │
06_deploy_endpoints       → Serving Endpoints (15m/30m forecast)     │
                                                                      │
additional_patient_info/ notebooks                                    │
  → UC Volume: landing_zone/raw_patient_registry/                    │
  → UC Volume: landing_zone/raw_device_telemetry_stream/             │
                                                                      │
DLT Pipeline (transformations.sql)  ◄────────────────────────────────┘
  → LIVE: silver_patient_registry
  → LIVE: silver_device_telemetry_stream
  → LIVE: silver_patient_readings
  → LIVE: gold_patient_device_readings  ──→ App SQL queries

Multi-Agent Supervisor Endpoint  ──→ App /api/agent/query
Genie Room (gold_patient_device_readings)  ──→ App /api/genie/query
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

## Step 2: Configure Variables

Edit `databricks.yml` or override at deploy time. At minimum you need:

| Variable | Description | Required |
|---|---|---|
| `catalog` | UC catalog name | Yes (default: `hls_glucosphere`) |
| `schema` | Schema name | Yes (default: `cgm`) |
| `endpoint_name` | MAS serving endpoint name | Yes (after Step 3) |
| `genie_space_id` | Genie room ID | Yes (after Step 4) |
| `app_name` | Databricks App name | Yes (default: `glucosphere-dashboard`) |

---

## Step 3: Create the Multi-Agent Supervisor Endpoint

The MAS endpoint is a Databricks Model Serving endpoint running a multi-agent supervisor that orchestrates clinician queries. It is **not** created by this bundle — it must be set up separately.

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

## Step 6: Deploy the Bundle

```bash
# From repo root
databricks bundle deploy \
  --var catalog=hls_glucosphere \
  --var schema=cgm \
  --var endpoint_name=<your-mas-endpoint> \
  --var genie_space_id=<your-genie-room-id> \
  --var app_name=glucosphere-dashboard
```

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
                 ↘    grant_app_permissions    (app SP access on UC + endpoints)
```

The validate + sanity tasks (added in C.5) are fail-fast guards: they catch
operator typos and silent baseline-write failures before they cost ~45 min
of downstream modeling compute.

> **Note:** The `generate_patient_device_data` task references the Jupyter notebooks in `Data_DataGen_ModelForecast/utils/additional_patient_info/`. If those notebooks need to be converted to Databricks-native format before running, do so with:
> ```bash
> databricks workspace import --format JUPYTER <notebook.ipynb> <workspace-path>
> ```

---

## Step 8: Run the DLT Pipeline

After the setup job completes, trigger the DLT pipeline to build silver and gold tables:

```bash
databricks bundle run cgm_silver_gold
```

Or in the Databricks UI: **Pipelines → glucosphere-cgm-silver-gold-${bundle.target} → Start**

---

## Step 9: Update App Environment Variables

After creating your MAS endpoint and Genie room, update `App/databricks/app.yaml`:

```yaml
command: ["python", "app.py"]
env:
  - name: ENDPOINT_NAME
    value: "your-mas-endpoint-name"
  - name: GENIE_SPACE_ID
    value: "your-genie-room-id"
```

Then redeploy:
```bash
databricks bundle deploy
```

---

## Step 10: Deploy and Start the App

```bash
databricks apps deploy ${var.app_name} --source-code-path App/databricks
databricks apps start ${var.app_name}
```

Or manage through the UI: **Apps → glucosphere-dashboard**

---

## Step 11: Smoke-test the deployed app

Before declaring the deployment "done," walk through these checks in the browser. Each catches a specific class of post-deploy issue (UI build, backend wiring, agent endpoints, Genie binding, data access). All should complete in <5 minutes.

Open the app URL from `databricks apps get glucosphere-dashboard --output json | jq -r .url`, then:

- [ ] **Home page loads** — no blank screen, no JS console errors. (If blank: React frontend wasn't built; run `npm run build` in `App/` and re-do `apps deploy`.)
- [ ] **Navigate to "Device Support Dashboard"** in the left sidebar. Device table populates with rows. (If empty: gold table `${catalog}.${schema}.gold_patient_device_readings` not populated → DLT pipeline didn't run successfully.)
- [ ] **Click a device row → "Run Clinical Analysis"** — wait ~30-60s. Text analysis appears with device-specific glucose stats. (If 404 ENDPOINT_NOT_FOUND: `app.yaml` references a deleted MAS endpoint — re-render with current `mas-<hash>-endpoint`. If 403 PERMISSION_DENIED: re-run `grant_app_permissions` task.)
- [ ] **Open Genie (or Chat / Ask) panel** and ask a natural-language question like *"How many distinct devices reported in the last hour?"* — response should include a SQL query and a result. (If errors: GENIE_SPACE_ID points at a non-existent space → re-render app.yaml with current Genie space ID.)
- [ ] **Refresh metrics tiles on the home page** — patient count, device count, high-risk alert count should update without errors. (If errors: app SP missing `USE CATALOG` / `SELECT` on gold tables → re-run `grant_app_permissions` or check Catalog Explorer permissions.)
- [ ] **Export to Chart button** (Device Support → Clinical Analysis section) — currently shows "(placeholder)" + disabled; tooltip on hover. Future feature; not a failure.

If all 5 functional checks pass, the deployment is verified end-to-end. Any failure narrows the diagnostic surface significantly (the bracketed hints above name the most common cause for each).

---

## Target: `hls_amer` (fe-vm-hls-amer workspace)

Added on `feature/dual-baseline-hls-amer` branch for HLS-AMER buildathon work. Backbone is the cleanup branch; only differences are a new bundle target and a render script for `app.yaml` templating.

**Variables (`targets.hls_amer` in `databricks.yml`):**

| Variable | Value |
|---|---|
| `catalog` | `hls_amer_catalog` |
| `schema` | `glucosphere_dev` |
| `warehouse_id` | `d9af05523dafe3a6` (HLS AMER SQL Warehouse) |
| `baseline_source` | `synthetic` (default — set to anything else to run the real-baseline branch via `01_ingest_real_baseline.py`) |
| host | `fe-vm-hls-amer.cloud.databricks.com` |

**Workflow:**

```bash
# 1. Render app.yaml for hls_amer (rewrites catalog/schema/warehouse in place)
python scripts/render_app_yaml.py --target hls_amer

# 2. Deploy the bundle (job + DLT pipeline + app shell + permission grants)
databricks bundle deploy -t hls_amer

# 3. Run the full setup job (data gen → ML training → endpoint deploy → Genie + KA + MAS creation)
databricks bundle run glucosphere_full_setup -t hls_amer

# 4. After step 3 completes, re-render with discovered IDs and redeploy the app
python scripts/render_app_yaml.py --target hls_amer \
    --mas-endpoint   <name-from-step-3>  \
    --ka-endpoint    <name-from-step-3>  \
    --genie-space-id <id-from-step-3>
databricks bundle deploy -t hls_amer
```

`render_app_yaml.py` reads the resolved bundle vars and rewrites the 7 per-target fields in `App/databricks/app.yaml` (4 env values + 3 resource block names/IDs). It is idempotent — re-run any time you switch target or discover new endpoint/Genie IDs. The committed `app.yaml` keeps the `azure`-target values as the default fallback, so deployments to `ward_consolidated` / `azure` / `azure2` don't strictly require the render step (catalog/schema/warehouse will differ from what `app.yaml` declares, but the resource blocks still match `azure`).

**Grants preflight — the deployed app's service principal needs:**

- `USE CATALOG hls_amer_catalog`
- `USE SCHEMA hls_amer_catalog.glucosphere_dev`
- `SELECT` on the silver / gold tables consumed by the Flask app
- `CAN_USE` on warehouse `d9af05523dafe3a6` (handled by the `sql-warehouse` resource block in `app.yaml`)
- `CAN_QUERY` on the MAS and KA serving endpoints (handled by the `mas-endpoint` / `ka-endpoint` resource blocks)
- `CAN_RUN` on the Genie space (not yet declared as a resource block in `app.yaml`; handled by `10_Grant_App_Permissions.py` during the setup job)

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
| DLT pipeline fails on `pseudo_incident_7d_labeled` | Run the setup job first; notebook 05 creates this table |
| DLT pipeline fails on landing zone paths | Run `generate_patient_device_data` task first |
| SQL queries return no data | Verify DLT pipeline ran successfully and gold table exists |
| Catalog creation permission error | Request `CREATE CATALOG` privilege or use an existing catalog |
