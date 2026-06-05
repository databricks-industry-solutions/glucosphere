# Glucosphere

## Overview

This repo contains two main parts that work together:

- **`Data_DataGen_ModelForecast/`**: Databricks notebooks/scripts to ingest Continuous Glucose Monitoring (CGM) data, generate pseudo-patients, train forecasting models, simulate incidents, and deploy models to serving.
- **`App/`**: The **control-tower** front-end (Databricks App) — a persistent nav rail, a command-center landing framed as **detect → diagnose → act**, live **Firmware Lifecycle** (device-error by firmware) and **Population Risk** (clinical blast radius) views, a real per-patient **Diabetes Coach** (search + 24h profile + near-term forecast), and a **unified assistant** folding **Genie** (NL→SQL) and a **Multi-Agent Supervisor** into one surface. It reads curated **bronze/silver/gold** tables derived from patient **CGM/IoT** signals (see [`Data_DataGen_ModelForecast/README_data.md`](Data_DataGen_ModelForecast/README_data.md)).

**glucosphere concept**: a monitoring "engine/sphere" on the Databricks platform that turns CGM + context data into curated signals, forecasts, and incident monitoring, then surfaces **actionable insights** via dashboards and agentic workflows (Genie / multi-agent tools) for multiple personas (e.g., physicians, caregivers, patients, device/MedTech teams, and regulators such as FDA review boards).

## Power of this solution

- **End-to-end monitoring sphere**: one coherent loop from CGM + context data → curated tables → forecasting/incident analytics → dashboards + agentic workflows.
- **Actionable, not just descriptive**: produces KPIs, alerts, and explanations teams can act on (e.g., calibration-bug detection via performance + distribution shifts).
- **Multi‑persona leverage**: supports physicians/caregivers, device/MedTech teams, patients, and regulators with views tailored to their needs—backed by the same governed data/model layer.
- **Flexible integration**: exposes both **inference tables** (easy DBSQL consumption) and **serving endpoints** (for real-time use when needed).
- **Governance + auditability**: Unity Catalog + MLflow provide lineage/traceability from data → curated tables/inference outputs → models → downstream metrics, improving trust, operations, and compliance. Feature tables can be incorporated later if/when needed.

## Architecture

![Architecture](Data_DataGen_ModelForecast/assets/architecture.png)

The App's natural-language query experience is powered by **Agent Bricks** — **Knowledge Assistant** (RAG over WHO clinical guidelines PDF) and a **Multi-Agent Supervisor (MAS)** — together with **AI/BI Genie** (NL→SQL over gold CGM tables), a separate Databricks capability the MAS orchestrates. The Device-support assistant runs through `/api/assist` with a **live engine switch** (⚡ Fast / 🤖 MAS): the default **fast router** makes one direct call to the right specialist (KA for clinical questions, a foundation model for device reasoning) — robust under load — while the MAS supervisor is one toggle away for live A/B. Genie (CGM-data mode) is always called directly. Full routing detail, the switch, and the latency rationale in [`App/README.md`](App/README.md).

## Data fidelity & forecast model performance

Three baseline source modes selectable at deploy time via `baseline_source`: **`from_source`** (real HUPA-UCM CGM, default), **`synthetic`** (in-cluster generator, for CI / restricted-egress), **`from_table`** (CTAS from an existing UC table). Real-mode pairs real CGM signal dynamics with synthetic patient identities — pseudo-patients with real clinical waveforms.

Mode-by-mode model performance (clean ~5 mg/dL MAE → +631% incident-period degradation), column-level provenance, and synthetic-vs-real distribution comparison all live in [`Data_DataGen_ModelForecast/README_data_fidelity_baseline.md`](Data_DataGen_ModelForecast/README_data_fidelity_baseline.md).

## Repository structure

```text
/
├── databricks.yml                    # Bundle config (targets, resources)
├── databricks.yml.example            # Template for external deployers
├── .env.bundle.example               # Template → cp to .env.bundle.<target> (one per deploy target)
├── DEPLOY.md                         # Step-by-step deploy guide
├── REPO_LAYOUT.md                    # Full navigation guide (what file does what)
├── App/                              # React + Flask Databricks App
├── Data_DataGen_ModelForecast/       # Notebooks: ingest, modeling, agents, grants
├── scripts/                          # render_app_yaml.py · smoke_test.py · grant_app_sp.py
└── docs/                             # Maintainer-specific notes
```

Full file-by-file inventory + "I want to…" task index in [`REPO_LAYOUT.md`](REPO_LAYOUT.md).

## How the two parts work together

- **Data → App**:
  - `Data_DataGen_ModelForecast/` produces curated UC tables, **inference / fleet-forecast tables**, and (optionally) **model serving endpoints**.
  - The app **queries tables** (e.g., via DBSQL) to render **forecast metrics**, **incident monitoring**, and **fleet-level KPIs**.
  - In the future, the app could call **model serving endpoints** and/or integrate the **inference tables** and incoming patient/IoT data to incorporate predictions directly into the UI.
- **Agents / Genie**:
  - The app can hook into **multi-agent systems** and use **Genie Space** as a tool to provide a comprehensive, Databricks-native UI experience.
- **Assets**:
  - `Data_DataGen_ModelForecast/assets/` contains analysis figures for documentation and stakeholder storytelling.
  - The `App/` folder may include its own UI assets (icons/images) for the frontend (separate from analysis figures).

## Getting started

Prerequisites: Databricks CLI configured for your target workspace, a UC catalog you can write to, and [uv](https://docs.astral.sh/uv/) installed locally (run `uv sync` once in the repo root). External deployers should add a target stanza per [`databricks.yml.example`](databricks.yml.example) and create a per-target config file (`.env.bundle.<target>`, one per target you deploy) from [`.env.bundle.example`](.env.bundle.example).

Canonical deploy sequence (full 8-step walkthrough with explanations + troubleshooting in [`DEPLOY.md`](DEPLOY.md)):

```bash
# load BUNDLE_VAR_* + DATABRICKS_CONFIG_PROFILE (one file per target — name = target key)
source .env.bundle.<target>                                       

# pass 1 — creates the warehouse
databricks bundle deploy -t <target> --profile <profile>          
uv run python scripts/render_app_yaml.py --target <target> --profile <profile>

# pass 2 — picks up rendered app.yaml
databricks bundle deploy -t <target> --profile <profile>
databricks bundle run glucosphere_full_setup -t <target> --profile <profile>    # ~45 min

# first-deploy-only
uv run python scripts/render_app_yaml.py --target <target> --profile <profile> \
    --mas-endpoint <name> --ka-endpoint <name> --genie-space-id <id>           

databricks bundle deploy -t <target> --profile <profile>
databricks bundle run glucosphere_app -t <target> --profile <profile>

# 8-check gate
uv run python scripts/smoke_test.py --target <target> --profile <profile>      
```

End-to-end wall clock: **~48 min subsequent / ~51 min first deploy**. For deploy variants (`baseline_source=synthetic` for CI / restricted-egress, `DEMO_WEEK_START` override for reproducible runs, distribution-comparison job), see [`DEPLOY.md`](DEPLOY.md).

## See also

- **[REPO_LAYOUT.md](REPO_LAYOUT.md)** — repository navigation guide + "I want to…" task index + workflow DAG
- **[DEPLOY.md](DEPLOY.md)** — step-by-step first-time deploy guide with troubleshooting
- **[Data_DataGen_ModelForecast/README.md](Data_DataGen_ModelForecast/README.md)** — pipeline + modeling guide
- **[Data_DataGen_ModelForecast/README_data_fidelity_baseline.md](Data_DataGen_ModelForecast/README_data_fidelity_baseline.md)** — data fidelity + baseline modes deep dive
- **[Data_DataGen_ModelForecast/README_data.md](Data_DataGen_ModelForecast/README_data.md)** — schema documentation for curated tables
- **[App/README.md](App/README.md)** — frontend + backend dev setup + agent endpoint detail
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — branch + commit conventions, dependency-table convention, CHANGELOG-update convention
- **[CHANGELOG.md](CHANGELOG.md)** — dated history of every commit group

## For maintainers — optional Claude Code plugins

If you use [Claude Code](https://docs.claude.com/en/docs/claude-code/overview) (Anthropic CLI) as your AI coding assistant, this project's `CLAUDE.md` (when present) auto-loads project-specific guidance. **No plugins required to deploy or run Glucosphere** — they only help when authoring, extending, or debugging the codebase.

### Public Claude Code plugins (anyone)

Useful general dev plugins from the public Anthropic marketplace — install via `/plugin install <name>` in Claude Code:

| Plugin | Why |
|---|---|
| `code-review` | PR code review automation |
| `pr-review-toolkit` | Deeper PR review patterns |
| `commit-commands` | `/commit` and `/commit-push-pr` shortcuts |
| `feature-dev` | Feature development scaffolding |
| `claude-md-management` | CLAUDE.md improver — keeps project context current |
| `skill-creator` | Create your own Claude Code skills |
| `github` | GitHub integration |
| `security-guidance` | Security review patterns |
| `playwright` | Browser automation for end-to-end testing |
| `claude-notify` | macOS desktop notifications for Claude completion events |

After each install, Claude Code prompts you to run `/reload-plugins` to apply. Plugins persist across sessions, re-logins, and Claude Code updates (one-time setup per machine).

### Databricks employees — internal plugin marketplace

Databricks Field Engineering maintains an internal `fe-vibe` plugin marketplace with Databricks-specific plugins (Lakebase, Apps, bundles, jobs, Genie, MAS, SDK). These are not accessible outside the Databricks corp network.

**If you're a Databricks employee**, see [`docs/internal-setup.md`](docs/internal-setup.md) for the marketplace setup (git HTTPS rewrite, install flow, recommended Persona A/B plugin sets, known issues).

## Contributors

Glucosphere came together in phases.

**Origins.** Two pre-Buildathon threads. The **MedTech Q4 QBR Hackathon (Nov 4, 2025, Denver)** — Jon Van Hofwegen, Sabrina Wang, Sumanth Ghanta, May Merkle-Tan — produced the data/ML foundations: May coined "Glucosphere" and built the real CGM data source + forecast-monitoring ML + statistical online-monitoring approach; Jon and Sabrina developed the MVP App with Multi-Agent Supervisor (MAS) agentic layer. In parallel, Morgan Williams's prior customer-driven **faulty-firmware device alert demo** became the incident-simulation scaffolding (originally synthetic, non-biological data).

**Buildathon FY26Q4 — Team 11 (HLS), "Real-time Digital Health Apps for Connected Devices"** (Justin Ward, Morgan Williams, May Merkle-Tan, Nikita Kamraj, Sabrina Wang). The two threads merged here: **May Merkle-Tan** integrated her prior CGM-data + forecast-monitoring ML work, grounded the device story in real-life FDA recall context, and simulated incident events modeled after those recalls. **Morgan Williams** integrated his prior work's ingest of the device generator output + patient attributes into a pseudo-online DLT pipeline, with device firmware versions tracking the incident timeline (baseline → transient fault → fix) to mirror real recall sequences. **Justin Ward** led appification: introduced the [ai-dev-kit](https://github.com/databricks-solutions/ai-dev-kit), turned the notebooks into a Databricks App + React frontend, scaffolded the bundle.

**Post-buildathon hardening + future feature work.** Led by May Merkle-Tan, Justin Ward, Morgan Williams — MVP tidy-up + future feature adds. **Interested contributors welcome** — see [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to get started, branch + commit conventions, and the pre-PR smoke-test checklist.
