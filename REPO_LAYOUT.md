# Repository navigation guide

> **Audience**: new contributors / operators trying to figure out which files do what, what gets pushed in a PR vs lives locally, and how the pipeline is wired.

For deployment instructions, see [`DEPLOY.md`](DEPLOY.md). For project overview, see [`README.md`](README.md). For dated change history, see [`CHANGELOG.md`](CHANGELOG.md).

## At a glance

Glucosphere is a Databricks Asset Bundle (DAB)–deployed CGM intelligence demo. On `databricks bundle deploy`, the bundle provisions:

- a **SDP (Spark Declarative Pipeline)** for bronze → silver → gold CGM tables
- a **multi-stage workflow job** (`glucosphere_full_setup`) that runs ingest → forecast modeling → incident inference → endpoint deploy → agent setup → grant chain
- a **Databricks App** (Flask backend + React frontend)
- a **Lakebase OLTP** instance, **SQL warehouse**, and **ML serving endpoints**
- optional **MAS / KA / Genie** agent endpoints + AI/BI dashboards

The entire deployable surface is described by a single file: [`databricks.yml`](databricks.yml).

---

## I want to…

### …deploy this to a new workspace

| Read | What it does |
|---|---|
| [`DEPLOY.md`](DEPLOY.md) | step-by-step first-time deploy guide with troubleshooting |
| [`.env.bundle.example`](.env.bundle.example) | template you `cp` to local `.env.bundle` (operator-owned) and fill in 3 tokens |
| [`databricks.yml`](databricks.yml) | the bundle definition — `targets`, `variables`, `resources` (all of them) |
| [`scripts/render_app_yaml.py`](scripts/render_app_yaml.py) | rewrites `App/databricks/app.yaml` per target (discovers bundle-managed warehouse by name) |

Quick deploy sequence (after `source .env.bundle`):
```
databricks bundle deploy -t <target>                  # pass 1 — creates warehouse
python scripts/render_app_yaml.py --target <target>   # writes WAREHOUSE_ID into app.yaml
databricks bundle deploy -t <target>                  # pass 2 — picks up rendered app.yaml
databricks bundle run glucosphere_full_setup -t <target>   # ~45 min pipeline
```

### …understand the data + modeling pipeline

The numbered notebooks in [`Data_DataGen_ModelForecast/`](Data_DataGen_ModelForecast/) implement the workflow stages. The `glucosphere_full_setup` job orchestrates them via a condition_task that dispatches on `baseline_source` (`synthetic` / `from_source` / `from_table`).

| File | Role |
|---|---|
| [`01_synthetic_baseline.py`](Data_DataGen_ModelForecast/01_synthetic_baseline.py) | inline synthetic CGM generator — used by `baseline_source=synthetic` |
| [`02_ingest_real_baseline.py`](Data_DataGen_ModelForecast/02_ingest_real_baseline.py) | downloads HUPA-UCM real CGM dataset — used by `from_source` |
| [`03_compare_baseline_modes.py`](Data_DataGen_ModelForecast/03_compare_baseline_modes.py) | side-by-side baseline-mode statistical comparison (not in main DAG; runs via the standalone `glucosphere_distribution_comparison` job) |
| [`04_pseudo_data_forecast_modeling.py`](Data_DataGen_ModelForecast/04_pseudo_data_forecast_modeling.py) | XGBoost forecast model training (15-min + 30-min horizons) — writes to UC Models |
| [`05_incident_inference_bidirectional.py`](Data_DataGen_ModelForecast/05_incident_inference_bidirectional.py) | **active** incident-simulation notebook — two-incident mirror, bidirectional cohort split |
| [`06_incident_inference_single.py`](Data_DataGen_ModelForecast/06_incident_inference_single.py) | **reference-only** sibling — unidirectional single-incident variant. Not wired into the main DAG; swap `databricks.yml` `incident_inference.notebook_path` to use it. |
| [`07_deploy_serving_endpoints.py`](Data_DataGen_ModelForecast/07_deploy_serving_endpoints.py) | promotes UC Models to serving endpoints |
| [`08_genie_ka_mas.py`](Data_DataGen_ModelForecast/08_genie_ka_mas.py) | provisions MAS / KA / Genie agent endpoints |
| [`09_grant_app_permissions.py`](Data_DataGen_ModelForecast/09_grant_app_permissions.py) | grants warehouse + UC + endpoint perms to the App SP |
| [`utils/validate_baseline_source.py`](Data_DataGen_ModelForecast/utils/validate_baseline_source.py) | first job task — enum validation + provenance row write |
| [`utils/check_pre_baseline_grants.py`](Data_DataGen_ModelForecast/utils/check_pre_baseline_grants.py) | precondition grant verification before ingest |
| [`utils/sanity_summary.py`](Data_DataGen_ModelForecast/utils/sanity_summary.py) | post-ingest summary metrics |
| [`utils/check_post_endpoint_grants.py`](Data_DataGen_ModelForecast/utils/check_post_endpoint_grants.py) | post-deploy grant verification on endpoints |
| [`utils/validate_diabetes_data.py`](Data_DataGen_ModelForecast/utils/validate_diabetes_data.py) | data-quality assertions (used by sanity_summary + standalone) |
| [`utils/additional_patient_info/transformations.sql`](Data_DataGen_ModelForecast/utils/additional_patient_info/transformations.sql) | **SDP / DLT pipeline source** — bronze → silver → gold transforms for `cgm_silver_gold` pipeline |
| [`utils/additional_patient_info/Create *.ipynb`](Data_DataGen_ModelForecast/utils/additional_patient_info/) | 3 setup notebooks: patient registry, raw device data, patient-device link table |
| [`configs/baseline_config.yaml`](Data_DataGen_ModelForecast/configs/baseline_config.yaml) | pipeline hyperparameters (per-env: dev / staging / prod) |

For deeper detail: [`Data_DataGen_ModelForecast/README.md`](Data_DataGen_ModelForecast/README.md) (pipeline guide) and [`Data_DataGen_ModelForecast/README_data.md`](Data_DataGen_ModelForecast/README_data.md) (table schemas).

### …modify the App (frontend or backend)

| Path | Stack | What it does |
|---|---|---|
| [`App/src/`](App/src/) | React (Vite) | frontend root — `App.jsx`, `main.jsx`, `index.css`, `ErrorBoundary.jsx` |
| [`App/src/pages/GlucoseLandingDashboard.jsx`](App/src/pages/GlucoseLandingDashboard.jsx) | React | landing page ("GlucoStream Intelligence") |
| [`App/src/pages/DiabetesCoachDashboard.jsx`](App/src/pages/DiabetesCoachDashboard.jsx) | React | patient-facing coach dashboard |
| [`App/src/pages/CareManagementDashboard.jsx`](App/src/pages/CareManagementDashboard.jsx) | React | clinician dashboard |
| [`App/src/pages/DeviceSupportDashboard.jsx`](App/src/pages/DeviceSupportDashboard.jsx) | React | device-team dashboard |
| [`App/src/pages/MetricsExplained.jsx`](App/src/pages/MetricsExplained.jsx) | React | metrics + simulation framing prose |
| [`App/src/components/AgentChatInterface.jsx`](App/src/components/AgentChatInterface.jsx) | React | MAS / KA / Genie chat UI |
| [`App/src/components/IncidentCharts.jsx`](App/src/components/IncidentCharts.jsx) | React | MAE timeline + incident-impact charts |
| [`App/src/api/`](App/src/api/) | JS | API client (Flask + Statement Execution + agent endpoints) |
| [`App/databricks/app.py`](App/databricks/app.py) | Flask (Python) | backend — proxies SQL via Statement Execution API, MAS / KA / Genie via serving endpoints, provenance lookup |
| [`App/databricks/app.yaml`](App/databricks/app.yaml) | YAML | env vars + resource bindings (**auto-rewritten** by `scripts/render_app_yaml.py`) |
| [`App/databricks/static/`](App/databricks/static/) | static | Vite build output (committed) |
| [`App/run_backend.sh`](App/run_backend.sh) | Bash | local dev launcher |
| [`App/README.md`](App/README.md) | docs | App dev setup |

### …understand the architecture / history

| Resource | Use it when |
|---|---|
| [`README.md`](README.md) | first read — overview, baseline modes, sequencing |
| [`Data_DataGen_ModelForecast/assets/architecture_0.2.png`](Data_DataGen_ModelForecast/assets/architecture_0.2.png) | current MVP system diagram (no Lakebase shown) |
| [`Data_DataGen_ModelForecast/assets/architecture_0.1.png`](Data_DataGen_ModelForecast/assets/architecture_0.1.png) | aspirational v0.1 (Lakebase / Postgres / Lakeflow — on roadmap, not in MVP) |
| [`CHANGELOG.md`](CHANGELOG.md) | dated history of every commit group — load-bearing for "why did we change X?" questions |
| [`Data_DataGen_ModelForecast/README.md`](Data_DataGen_ModelForecast/README.md) | pipeline + modeling guide, methodology references |

---

## By-category file inventory (with PR / local status)

### Deployment glue — **PR-shipped**
- `databricks.yml` — bundle definition (targets, variables, resources)
- `.env.bundle.example` — template for operator's local `.env.bundle`
- `scripts/render_app_yaml.py` — per-target App config rewriter
- `DEPLOY.md` — deploy guide

### SDP / DLT pipeline source — **PR-shipped**
- `databricks.yml` → `resources.pipelines.cgm_silver_gold` — pipeline resource declaration
- `Data_DataGen_ModelForecast/utils/additional_patient_info/transformations.sql` — actual silver/gold transforms

### Workflow job orchestration — **PR-shipped**
- `databricks.yml` → `resources.jobs.glucosphere_full_setup` — main DAG (15+ tasks)
- `databricks.yml` → `resources.jobs.glucosphere_distribution_comparison` — standalone baseline-comparison job
- `Data_DataGen_ModelForecast/01_*` through `09_*` + `utils/*.py` — task implementation notebooks

### App resources — **PR-shipped**
- All of `App/` (React + Flask backend + config + build output)
- `databricks.yml` → `resources.apps.glucosphere_app` + `sql_warehouses.glucosphere_warehouse` + `database_instances.glucosphere_oltp`

### Configuration — **PR-shipped**
- `Data_DataGen_ModelForecast/configs/baseline_config.yaml` — pipeline hyperparameters (dev / staging / prod tiers)

### Assets — **PR-shipped**
- `Data_DataGen_ModelForecast/assets/architecture_0.{1,2}.png` — architecture diagrams
- `Data_DataGen_ModelForecast/assets/comparison_3way_*.png` — baseline-mode comparison plot exports
- `Data_DataGen_ModelForecast/assets/glucose_*.png`, `incident_*.png`, `mae_*.png`, `forecast_*.png` — plot exports surfaced in dashboards or docs
- `Data_DataGen_ModelForecast/assets/who_docs/` — WHO Noncommunicable Diseases reference PDF (referenced by Genie / agents)

### Auto-generated, per-target rendered — **PR-shipped but pinned to last-rendered target**
- `App/databricks/app.yaml` — rewritten by `scripts/render_app_yaml.py` for whichever target was last rendered. Currently pinned to the most recent render target. Switch targets ⇒ re-render before deploy.
- `App/databricks/static/` — Vite build output. Re-build via `npm run build` in `App/`.

### Operator-owned config — **gitignored, never PR-shipped**

| Path | Why gitignored |
|---|---|
| `.env.bundle` | per-operator catalog / schema / profile — workspace-specific, often workspace-internal identifiers. The template `.env.bundle.example` IS committed. |
| `App/.env` | App-local secrets (legacy — was used for backend-tokens-in-env pattern, now generally unused but still gitignored as a safety net) |

### Credentials & secrets — **gitignored, never PR-shipped**

| Pattern | What it would contain |
|---|---|
| `.databrickscfg` | Databricks CLI auth tokens (workspace profiles) |
| `*.token` | any bearer-token file |
| `.env`, `.env.local`, `.env.*.local` | any environment-variable file with secrets |
| `config/databricks_config*.json` | legacy Databricks config files |
| `.npmrc`, `.pip/pip.conf` | internal Databricks npm / pip proxy configs (would leak internal URLs if pushed to a public repo) |

### Build artifacts — **gitignored, regenerated locally**

| Path | Source |
|---|---|
| `App/node_modules/` | `npm install` (~94 MB; never commit) |
| `App/dist/`, `App/dist-ssr/`, `App/.vite/` | Vite build cache |
| `App/*.local` | Vite local-config overrides |
| `**/__pycache__/`, `*.pyc`, `*.pyo` | Python bytecode |
| `build/`, `dist/`, `*.egg-info/`, `wheels/`, `eggs/` | Python packaging artifacts |
| `.pytest_cache/`, `.coverage`, `htmlcov/`, `*.cover`, `.hypothesis/` | test / coverage artifacts |

### Editor / IDE configs — **gitignored**

| Path | Tool |
|---|---|
| `.vscode/*` (except `.vscode/extensions.json` which is allowed) | VS Code |
| `.idea/` | JetBrains IDEs |
| `.claude/` | Claude Code workspace state |
| `.cursor/` | Cursor IDE workspace state |
| `.DS_Store`, `*.suo`, `*.sw?` | OS / Vim swap files |

### Internal working notes — **gitignored, internal-only**

These are the operator's local scratchpads — design docs, session snapshots, test scripts, internal explainers. They never PR-ship but are valuable as institutional memory.

| Path | What lives there |
|---|---|
| `ref_notes/` | **the primary "internal refs" landing pad.** Categories of content found here (see [`ref_notes/`](ref_notes/) for full listing): |
| └─ `*_branch-divergence-snapshot.md` | analysis of what changed between branches |
| └─ `*_session-snapshot.md` / `*_end-of-day-snapshot.md` | dated session-state records (work-in-flight, decisions, open questions) |
| └─ `*_dual-baseline-*.md` | dual-baseline design docs (recap + provenance, comparison plots) |
| └─ `*_lakebase-*.md` | Lakebase design + positioning + auth investigation notes |
| └─ `*_synth_e2e_findings.md` | Phase 1 #68 synth-validation findings doc (team-shareable, but moved here for now) |
| └─ `*_warehouse-bundle-management-verification.md` | Path 2 verification write-up + reproducible test script |
| └─ `*_path_2b_test_script.sh` | reproducible end-to-end test script for the warehouse-bundle pattern |
| └─ `*_deploy-commands-cheatsheet.md` | quick-reference card for `bundle deploy` / `bundle run` invocations |
| └─ `*_notebook-rename-playbook.md` | re-usable 6-step methodology for renaming notebooks safely |
| └─ `*_app-display-and-incident-simulation.md` | App UX + incident simulation design notes |
| └─ `*_live-app-smoke-test.md` | manual smoke-test procedures |
| └─ `*_mae-shift-incident-real-data.md` | MAE-shift results recap (load-bearing for fleet-monitoring pitch) |
| └─ `*_slack-drafts.md` | Slack message drafts before sending |
| └─ `*_asq_*_update.md` | ASQ ticket update drafts |
| └─ `*_lakebase-positioning-for-readme.md` | unmerged copy variants for README |
| └─ `init_lakebase_alerts_schema.py` | Lakebase #42 setup notebook (parked, will be reactivated when #42 resumes) |
| `previous/` | (currently empty) staging area for files about to be deleted — used during the Phase A cleanup pass |
| `resume/` | Claude Code session-resume artifact (just `.claude/` inside) |
| `_dev/`, `.devs/`, `.refs/` | (currently empty / unused) ad-hoc local sandbox paths |

**Promotion path**: when a `ref_notes/` doc matures into something team-shareable (a deploy guide, a finding the team needs to act on, an architectural decision record), promote it by `git mv ref_notes/<file>.md docs/<file>.md` (creating `docs/` if needed) and `git add` it on a dedicated docs branch.

---

## Workflow DAG — `glucosphere_full_setup` job

The main pipeline job in declaration order. Dependencies shown as `↓` (linear) or `├─` (branch). All tasks live in `databricks.yml` `resources.jobs.glucosphere_full_setup.tasks`.

```
validate_baseline_source                    utils/validate_baseline_source.py
  ↓
check_pre_baseline_grants                   utils/check_pre_baseline_grants.py
  ↓
dispatch_baseline_source                    (condition_task — branches on baseline_source)
  ↓ (synthetic)                  ↓ (from_source / from_table)
generate_synthetic_baseline      ingest_real_baseline
  01_synthetic_baseline.py       02_ingest_real_baseline.py
                ↓                                ↓
                          sanity_summary
                          utils/sanity_summary.py
                                ↓
                          datagen_modeling
                          04_pseudo_data_forecast_modeling.py
                                ↓
        ┌───────────────────────┼───────────────────────┐
        ↓                       ↓                       ↓
incident_inference     deploy_model_endpoints   generate_patient_device_data
05_incident_inference  07_deploy_serving        utils/additional_patient_info/
_bidirectional.py      _endpoints.py            Create Raw Patient_Registry Data.ipynb
        ↓                                              ↓
   (downstream uses                         ┌──────────┴──────────┐
    incident tables)                        ↓                     ↓
                                  create_patient_registry  create_device_telemetry
                                  utils/.../Create         utils/.../Create
                                  Patient_Device           Raw Device Data
                                  Table.ipynb              .ipynb
                                                                  ↓
                                                          run_dlt_pipeline
                                                          (invokes cgm_silver_gold SDP)
                                                                  ↓
                                                          provision_agents
                                                          08_genie_ka_mas.py
                                                                  ↓
                                                          check_post_endpoint_grants
                                                          utils/check_post_endpoint_grants.py
                                                                  ↓
                                                          grant_app_permissions
                                                          09_grant_app_permissions.py
```

The exact task names + their `depends_on` are in `databricks.yml`. Above is the conceptual flow.

---

## What ships in a PR vs what stays local

**PR-ed (in git, visible to reviewers)**:
- All numbered notebooks + utils + SDP transform SQL
- `databricks.yml` + `.env.bundle.example` + `scripts/`
- All docs: `README.md`, `DEPLOY.md`, `CHANGELOG.md`, `REPO_LAYOUT.md` (this file), `App/README.md`, `Data_DataGen_ModelForecast/README.md` + `README_data.md`
- All of `App/` (React, Flask, config, static build output)
- `Data_DataGen_ModelForecast/assets/`, `configs/`
- Per-target rendered `App/databricks/app.yaml` (pinned to whichever target was last rendered)

**Local-only (gitignored, never PR-shipped)**:
- `.env.bundle` (operator config)
- `ref_notes/` (working notes)
- `resume/`
- `App/node_modules/`
- Any `*.local` or `.cursor/` artifacts

---

## Common new-operator gotchas

1. **`.env.bundle.example` is the template, `.env.bundle` is what you create.** `.env.bundle` MUST be gitignored (it is, line 110 of `.gitignore`). Verify before committing.
2. **`BUNDLE_VAR_*` lines need `export` prefix.** Without `export`, the variable is shell-local and the `databricks` CLI subprocess doesn't see it — it silently falls back to the `databricks.yml` defaults. (See `.env.bundle.example` NOTE block at top + `DEPLOY.md` Step 2.)
3. **Two-pass deploy on first run.** The bundle-managed `sql_warehouses.glucosphere_warehouse` only exists after the first `bundle deploy`. `scripts/render_app_yaml.py` discovers it by name, so the order is: deploy → render → deploy → run.
4. **`render_app_yaml.py` requires `--profile` OR `DATABRICKS_CONFIG_PROFILE` env var.** CLI v0.297.2's `databricks warehouses list` does not inherit the env var when run from a bundle directory.
5. **`App/databricks/app.yaml` is auto-rewritten.** Do not hand-edit env values or resource IDs — re-run `render_app_yaml.py` instead. Hand-edits will be lost on next render.
6. **Switching targets requires re-render.** The committed `app.yaml` is pinned to the last-rendered target. If you switch to a different target, run `render_app_yaml.py --target <new-target>` before `bundle deploy`.
7. **`06_incident_inference_single.py` is reference-only.** The active inference notebook is `05_incident_inference_bidirectional.py`. To revert, swap `databricks.yml` `incident_inference.notebook_path`.

---

## See also

- [`README.md`](README.md) — project overview
- [`DEPLOY.md`](DEPLOY.md) — deployment guide
- [`CHANGELOG.md`](CHANGELOG.md) — dated change history
- [`Data_DataGen_ModelForecast/README.md`](Data_DataGen_ModelForecast/README.md) — pipeline + modeling guide
- [`Data_DataGen_ModelForecast/README_data.md`](Data_DataGen_ModelForecast/README_data.md) — curated table schemas
- [`App/README.md`](App/README.md) — App dev setup
