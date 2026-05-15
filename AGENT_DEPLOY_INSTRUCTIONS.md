# Glucosphere — Agent Deployment Instructions
## Target: ws-ward-demo (fresh workspace, no catalog)

You are deploying the Glucosphere CGM Intelligence Dashboard to a brand-new Databricks workspace.
This is a fully automated deployment — do not skip steps or assume prior state.

---

## Target Workspace

| Field | Value |
|---|---|
| Workspace URL | `https://adb-7405619937790736.16.azuredatabricks.net` |
| Workspace name | `ws-ward-demo` |
| Cloud | Azure |
| Catalog | Does not exist yet — you must create it |
| Suggested catalog name | `glucosphere_catalog` |
| Suggested schema name | `glucosphere` |

---

## Source Code

```bash
git clone https://github.com/databricks-field-eng/hls-glucosphere.git
cd hls-glucosphere
git checkout feature/ward-app-cleanup
```

---

## Prerequisites to Verify

- Databricks CLI v0.220+ installed (`databricks --version`)
- Node.js 18+ installed (`node --version`)
- Python 3.10+ installed (`python3 --version`)
- Authenticated to the target workspace (see Step 1)

---

## Step 1: Authenticate Databricks CLI

```bash
databricks auth login --host https://adb-7405619937790736.16.azuredatabricks.net
```

Set a profile name when prompted (e.g. `ward-demo`). All subsequent commands use `--profile ward-demo`.

Verify:
```bash
databricks auth describe --profile ward-demo
```

---

## Step 2: Create Catalog and Schema (PRE-FLIGHT — required before bundle)

The bundle job assumes the catalog already exists. You must create it first.
Run this in a Databricks notebook or via the CLI SQL interface:

```sql
CREATE CATALOG IF NOT EXISTS glucosphere_catalog;
USE CATALOG glucosphere_catalog;
CREATE SCHEMA IF NOT EXISTS glucosphere;
CREATE VOLUME IF NOT EXISTS glucosphere_catalog.glucosphere.data;
CREATE VOLUME IF NOT EXISTS glucosphere_catalog.glucosphere.landing_zone;
```

Via CLI (replace `<warehouse-id>` with any available SQL warehouse ID in the workspace):

```bash
databricks statement-execution execute-statement \
  --profile ward-demo \
  --warehouse-id <warehouse-id> \
  --statement "CREATE CATALOG IF NOT EXISTS glucosphere_catalog"

databricks statement-execution execute-statement \
  --profile ward-demo \
  --warehouse-id <warehouse-id> \
  --statement "CREATE SCHEMA IF NOT EXISTS glucosphere_catalog.glucosphere"

databricks statement-execution execute-statement \
  --profile ward-demo \
  --warehouse-id <warehouse-id> \
  --statement "CREATE VOLUME IF NOT EXISTS glucosphere_catalog.glucosphere.data"

databricks statement-execution execute-statement \
  --profile ward-demo \
  --warehouse-id <warehouse-id> \
  --statement "CREATE VOLUME IF NOT EXISTS glucosphere_catalog.glucosphere.landing_zone"
```

> **Note:** If there is no SQL warehouse yet, create a Serverless SQL warehouse from the
> Databricks UI: **SQL Warehouses → Create warehouse → Serverless**. Note the warehouse ID.

---

## Step 3: Get Required IDs

You need two IDs before deploying. Note them down — you'll need them later.

**SQL Warehouse ID:**
```bash
databricks warehouses list --profile ward-demo --output json | python3 -c "
import json, sys
ws = json.load(sys.stdin)
for w in ws.get('warehouses', []):
    print(w['id'], w['name'], w.get('state',''))
"
```
Pick a running warehouse and copy its ID (e.g. `abc123def456`).

**Your current user/SP name** (for granting yourself catalog permissions if needed):
```bash
databricks auth describe --profile ward-demo
```

---

## Step 4: Configure the Bundle

Add a `ward-demo` target to `databricks.yml`, or deploy using `--var` overrides.
The simplest approach — deploy with variable overrides directly (Step 6).

Key variables:
| Variable | Value for this deployment |
|---|---|
| `catalog` | `glucosphere_catalog` |
| `schema` | `glucosphere` |
| `app_name` | `glucosphere-dashboard` |
| `warehouse_id` | `<your-warehouse-id-from-step-3>` |

---

## Step 5: Build the React Frontend

```bash
cd App
npm install
npm run build
cd ..
```

This produces `App/databricks/static/` — the Flask backend serves these files.
Verify the output exists:
```bash
ls App/databricks/static/
# Should show: index.html, assets/
```

---

## Step 6: Deploy the Bundle

```bash
databricks bundle deploy \
  --profile ward-demo \
  --var catalog=glucosphere_catalog \
  --var schema=glucosphere \
  --var app_name=glucosphere-dashboard \
  --var warehouse_id=<your-warehouse-id>
```

This deploys to the workspace:
- Notebooks (all `Data_DataGen_ModelForecast/*.py` + utils)
- DLT pipeline (`glucosphere-cgm-silver-gold-<target>`)
- Job (`glucosphere-full-setup-<target>`)
- App (`glucosphere-dashboard`)

Verify deployment:
```bash
databricks bundle validate --profile ward-demo --var catalog=glucosphere_catalog --var schema=glucosphere
```

---

## Step 7: Run the End-to-End Setup Job

```bash
databricks bundle run glucosphere_full_setup \
  --profile ward-demo \
  --var catalog=glucosphere_catalog \
  --var schema=glucosphere \
  --var warehouse_id=<your-warehouse-id>
```

This single job runs in order:

| # | Task | What it does |
|---|------|-------------|
| 1a | `dispatch_baseline_source` | Branches on `${var.baseline_source}` ("synthetic" vs anything else) |
| 1b | `generate_synthetic_baseline` | Runs if baseline_source == "synthetic" — textbook phenotypes + AR(1) → `diabetes_data` |
| 1c | `ingest_real_baseline` | Runs if baseline_source != "synthetic" — HUPA-UCM download OR existing UC table → `diabetes_data` (stub until Commit C) |
| 2 | `datagen_modeling` | CGM pseudo data generation + XGBoost model training (depends on 1b OR 1c via `run_if: AT_LEAST_ONE_SUCCESS`) |
| 3 | `incident_inference` | Simulate calibration bug, produce incident table |
| 4 | `deploy_model_endpoints` | Deploy 15m + 30m forecast serving endpoints |
| 5 | `create_patient_registry` | Patient registry parquet → landing_zone volume |
| 6 | `create_device_telemetry` | Device telemetry parquet → landing_zone volume |
| 7 | `generate_patient_device_data` | Join patient/device data → landing_zone |
| 8 | `run_dlt_pipeline` | DLT: landing_zone → silver → gold tables |
| 9 | `create_genie_ka_mas` | Create KA + Genie room + MAS supervisor endpoint |
| 10 | `grant_app_permissions` | Grant app SP access to all resources |

**Expected runtime: ~45-60 minutes**

Monitor progress:
```bash
# Get the run ID from the output of the run command, then:
databricks runs get --run-id <run-id> --profile ward-demo
```
Or watch in the UI: **Workflows → glucosphere-full-setup-`<target>`**

---

## Step 8: Capture MAS Endpoint Name and Genie Space ID

After the job completes (specifically after task 9 `create_genie_ka_mas`), retrieve:

**MAS endpoint name:**
```bash
databricks serving-endpoints list --profile ward-demo --output json | python3 -c "
import json, sys
eps = json.load(sys.stdin)
for ep in eps.get('endpoints', []):
    if 'mas' in ep['name'].lower() or 'supervisor' in ep['name'].lower():
        print('MAS:', ep['name'])
    if 'ka' in ep['name'].lower() or 'knowledge' in ep['name'].lower():
        print('KA: ', ep['name'])
"
```

**Genie space ID:**
```bash
databricks api get /api/2.0/data-rooms/ --profile ward-demo | python3 -c "
import json, sys
rooms = json.load(sys.stdin)
for r in rooms.get('data_rooms', []):
    if 'glucosphere' in r.get('name','').lower() or 'cgm' in r.get('name','').lower():
        print(r['name'], '->', r['id'])
"
```

---

## Step 9: Update App Environment Variables

Edit `App/databricks/app.yaml` with the values from Step 8:

```yaml
env:
  - name: ENDPOINT_NAME
    value: "<mas-endpoint-name-from-step-8>"
  - name: GENIE_SPACE_ID
    value: "<genie-space-id-from-step-8>"
  - name: CATALOG_NAME
    value: "glucosphere_catalog"
  - name: SCHEMA_NAME
    value: "glucosphere"
```

Then rebuild the frontend and redeploy:
```bash
cd App && npm run build && cd ..
databricks bundle deploy \
  --profile ward-demo \
  --var catalog=glucosphere_catalog \
  --var schema=glucosphere \
  --var warehouse_id=<your-warehouse-id>
```

---

## Step 10: Start the App

```bash
databricks apps start glucosphere-dashboard --profile ward-demo
```

Get the app URL:
```bash
databricks apps get glucosphere-dashboard --profile ward-demo --output json | python3 -c "
import json, sys
app = json.load(sys.stdin)
print(app.get('url', 'URL not yet available'))
"
```

The app may take 2-3 minutes to start. Refresh until you see the Glucosphere dashboard.

---

## Verification Checklist

- [ ] Catalog `glucosphere_catalog` and schema `glucosphere` exist
- [ ] All job tasks completed successfully (green in Workflows UI)
- [ ] Gold table exists: `glucosphere_catalog.glucosphere.gold_patient_device_readings`
- [ ] Incident table exists: `glucosphere_catalog.glucosphere.pseudo_incident_7d_labeled`
- [ ] MAS serving endpoint is in `READY` state
- [ ] KA serving endpoint is in `READY` state
- [ ] App status is `RUNNING`
- [ ] App loads in browser — dashboard shows patient counts, device data
- [ ] "Deeper Analysis" button returns AI response (not a planning step)

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Job task fails with `CATALOG_NOT_FOUND` | Step 2 was skipped — create catalog first |
| Task 4 `deploy_model_endpoints` fails | Ensure model serving is enabled on the workspace |
| Task 9 `create_genie_ka_mas` fails | Check that Agent Bricks / Genie are available on this workspace tier |
| App shows "Not Found" | Frontend build wasn't run (`npm run build`) before deploy |
| App shows no data (SQL 500 errors) | Gold table doesn't exist — check DLT pipeline (task 8) completed |
| App "Deeper Analysis" returns empty | App SP not granted CAN_QUERY — re-run task 10 or run `scripts/grant_app_permissions.py` |
| `databricks bundle run` fails with variable error | Pass all 4 `--var` flags (catalog, schema, app_name, warehouse_id) |
| Genie space auto-discovery fails in task 10 | Set `GENIE_SPACE_ID` parameter explicitly in the job task parameters |

---

## Key File Locations

```
hls-glucosphere/
├── databricks.yml                          ← Bundle manifest (jobs, pipelines, app)
├── App/
│   ├── databricks/
│   │   ├── app.py                          ← Flask backend (UPDATE app.yaml after job)
│   │   ├── app.yaml                        ← App config (UPDATE with MAS+Genie IDs)
│   │   └── static/                         ← React build output (generated by npm run build)
│   ├── src/                                ← React source
│   └── vite.config.js
├── Data_DataGen_ModelForecast/
│   ├── dual_01_generate_synthetic_baseline.py      ← cloned from cleanup branch + dual-baseline checks
│   ├── dual_01_ingest_real_baseline.py             ← real-data ingest (stub; implemented in plan's Commit C.2/C.3)
│   ├── 04_CGM_PseudoGeneration_CleanData_Modeling.py
│   ├── 05_CGM_Incident_Inference_DeviceCalibrationBug.py
│   ├── 06_DeployModel_as_ServingEndpoint.py
│   ├── dual_09_Create_Genie_KA_MAS.py     ← Creates KA + Genie + MAS (with KA-ready wait + fail-fast)
│   ├── 10_Grant_App_Permissions.py         ← Grants SP access to all resources
│   └── utils/additional_patient_info/      ← Patient/device data generators
└── scripts/
    └── grant_app_permissions.py            ← Local fallback permissions script
```
