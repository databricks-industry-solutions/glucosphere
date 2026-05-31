# Glucosphere App

Glucosphere is a CGM (Continuous Glucose Monitoring) Device Intelligence & Analytics Platform built with React and Flask, deployed on Databricks.

## Overview

This application provides:
- **Real-time Device Monitoring**: Track device health, out-of-range events, and anomalies
- **Landing Page Metrics**: Active patients, devices online, high-risk alerts
- **Incident Analysis**: Visualize CGM device calibration incidents and their impact
- **Switchable AI assistant**: a fast app-side router (Genie / Knowledge Assistant / foundation model) with a live ⚡ Fast / 🤖 MAS toggle to the Multi-Agent Supervisor — device troubleshooting + clinical Q&A
- **Heatmap Analytics**: Device performance by model and firmware version

## Architecture

- **Frontend**: React + Vite + Tailwind CSS
- **Backend**: Flask (proxy server for Databricks APIs)
- **Data Source**: Databricks Unity Catalog (`${CATALOG_NAME}.${SCHEMA_NAME}` — set per-deployment via `BUNDLE_VAR_catalog` + `BUNDLE_VAR_schema` in `.env.bundle`; see repo-root `.env.bundle.example`)
- **AI assistant**: switchable — a fast app-side **router** (Genie / Knowledge Assistant / foundation model, called directly; default) or the Databricks **Multi-Agent Supervisor** (toggle). See *Assistant engine switch* below.

### Agent endpoints — Genie / KA / MAS (often confused)

The App's natural-language query experience is powered by **three native Databricks Agent Bricks endpoints** that work together. They are NOT interchangeable — each has a distinct data source and purpose:

| Endpoint | Data source | Purpose |
|---|---|---|
| **Genie** | Gold table `<catalog>.<schema>.gold_patient_device_readings` | Natural-language → SQL over **structured CGM data** (patient readings, device incidents, fleet stats, trends) |
| **Knowledge Assistant (KA)** | UC Volume `/Volumes/<catalog>/<schema>/pipeline_data/who_docs/` — WHO diabetes guidelines PDF | **RAG** over WHO **clinical definitions, classification, and diagnosis criteria** |
| **MAS (Multi-Agent Supervisor)** | Routes between the two above based on question type (5–7 serial LLM calls) | Available as the **🤖 MAS** engine toggle. Branded "GlucoScope" in `08_genie_ka_mas.py`. **Not** the default — the app's **default fast router calls Genie / KA / a foundation model directly** (see *Assistant engine switch* below). |

The MAS routing logic (per `Data_DataGen_ModelForecast/08_genie_ka_mas.py:325-331`, "GlucoScope" supervisor instructions):

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart LR
    U[User asks question<br/>via App chat UI]
    M[MAS endpoint<br/>'GlucoScope' supervisor]
    R1[SQL / data questions:<br/>patient glucose, device incidents,<br/>fleet stats, trends]
    R2[Clinical guideline questions:<br/>WHO diagnostic criteria,<br/>diabetes classification]
    G[Genie space<br/>NL → SQL]
    K[Knowledge Assistant<br/>RAG over WHO PDF]
    DB[(gold_patient_device_readings<br/>structured CGM data)]
    PDF[(WHO diabetes PDF<br/>clinical guidelines)]

    U --> M
    M --> R1
    M --> R2
    R1 --> G
    R2 --> K
    G --> DB
    K --> PDF

    classDef routing fill:#ffffff,stroke:#666,stroke-width:1.5px;
    class R1,R2 routing;
```

Examples of the routing in practice:

- *"How many patients had hypoglycemia events last week?"* → MAS routes to **Genie** → SQL over gold table
- *"What's the WHO diagnostic threshold for type-2 diabetes?"* → MAS routes to **KA** → RAG over WHO PDF
- *"Which device firmware has the highest out-of-range rate?"* → MAS routes to **Genie** → SQL aggregation
- *"What does the WHO say about gestational diabetes screening?"* → MAS routes to **KA** → RAG over PDF

### Assistant engine switch — Fast router vs Multi-Agent Supervisor

The Device-support assistant + the per-device "Clinical Analysis" both flow through one
backend route, `POST /api/assist`, with a **switchable engine** (live UI toggle in the
assistant header, ⚡ Fast / 🤖 MAS; persisted in `localStorage`, default from the
`ASSIST_ENGINE` env in `app.yaml`):

| Engine | Path | Latency | Notes |
|---|---|---|---|
| **`direct`** (default, ⚡ Fast) | App-side router → calls **one** specialist directly: keyword-route to **KA** (WHO/clinical terms) else a **foundation model** (`databricks-claude-sonnet-4-6`) for device reasoning; `mode:'analysis'` adds fleet-stats enrichment | ~6–15s, reliable | One decision → one direct call |
| **`mas`** (🤖) | The **Multi-Agent Supervisor** above (Genie + KA) | erratic 17s → >300s under load | Kept for live A/B; preserved/reversible |

**Why the switch exists.** The Agent-Bricks MAS runs 5–7 sequential LLM calls
(supervisor + sub-agents + their FMs); under shared-endpoint contention the per-call queue
delay multiplies and the chain blows past the **~300s Databricks Apps gateway timeout** →
`504 upstream request timeout`. The direct router makes one call (or two for routing), so it
stays fast even under load — matching Databricks' own guidance that deterministic
chains/routers have "typically lower latency (fewer LLM calls for orchestration)." The CGM-data
(Genie) mode is unchanged and always calls Genie directly. Full root-cause analysis:
[`ref_notes/2026-05-31_mas-latency-troubleshooting.md`](../ref_notes/2026-05-31_mas-latency-troubleshooting.md).

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart LR
    U[Device-support question<br/>/api/assist]
    SW{engine?}
    KW{clinical / WHO<br/>keyword?}
    FM[Foundation model<br/>databricks-claude-sonnet-4-6]
    KA2[Knowledge Assistant<br/>RAG over WHO PDF]
    MAS2[Multi-Agent Supervisor<br/>Genie + KA, 5–7 serial calls]
    U --> SW
    SW -->|direct ⚡| KW
    SW -->|mas 🤖| MAS2
    KW -->|yes| KA2
    KW -->|no| FM
    classDef sw fill:#ffffff,stroke:#666,stroke-width:1.5px;
    class SW,KW sw;
```

## Project Structure

```
App/
├── config/               # Databricks workspace configurations
├── databricks/          # Flask backend (app.py, app.yaml, requirements.txt)
├── docs/                # Documentation and technical notes
├── scripts/             # Deployment scripts
├── src/                 # React frontend source code
│   ├── api/            # API clients (Databricks SQL, Agent)
│   ├── components/     # React components
│   └── pages/          # Page components
├── deploy_glucosphere.py # Deployment script for Databricks Apps
├── package.json         # NPM dependencies
├── vite.config.js       # Frontend build configuration
└── run_backend.sh       # Local backend startup script
```

## Local Development

### Prerequisites
- Node.js 16+
- Python 3.9+
- Databricks workspace access
- Personal Access Token (PAT)

### Setup

1. **Install dependencies**:
```bash
cd App
npm install
```

2. **Configure environment**:
Create `.env.local` with:
```
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=dapi...your_token_here
VITE_DATABRICKS_TOKEN=dapi...your_token_here
PORT=8000
```

3. **Start backend** (Terminal 1):
```bash
cd App
./run_backend.sh
```

4. **Start frontend** (Terminal 2):
```bash
cd App
npm run dev
```

5. **Access**: http://localhost:5173

## Deployment to Databricks

### Deploy to Databricks Apps

```bash
cd App
npm run build
python3 deploy_glucosphere.py
```

This will:
- Build the production frontend
- Upload all files to Databricks workspace
- Create/update the Databricks App
- Deploy to: `https://glucosphere-{workspace-id}.databricksapps.com`

## Key Features

### Landing Page
- **Active Patients**: Real-time count from gold table
- **Devices Online**: Devices with recent readings
- **High-Risk Alerts**: Out-of-range glucose readings
- **Recent Incident Analysis**: 7-day calibration incident visualization

### Device Support Dashboard
- **Heatmap**: Out-of-range events by device type and firmware
- **Device Details**: Expandable table with device information
- **Pattern Alerts**: Emerging anomalies across device cohorts
- **AI Troubleshooting**: switchable assistant (fast router by default; Multi-Agent Supervisor on toggle) for device analysis

### Assistant (fast router · MAS toggle)
- Chat interface for device troubleshooting (`/api/assist`)
- Deeper per-device Clinical Analysis (fast FM + fleet-stats enrichment by default)
- Integration with CGM analytics (Genie) and clinical knowledge (KA) — called directly by the router, or via the MAS supervisor when toggled. See *Assistant engine switch* above.

## Data Schema

Primary table: `${CATALOG_NAME}.${SCHEMA_NAME}.gold_patient_device_readings` (e.g. `<your-catalog>.<your-schema>.gold_patient_device_readings`).

The React app fetches catalog/schema from the Flask `GET /api/config` endpoint at startup (helper in `App/src/api/config.js`), then constructs queries via template literals `${catalog}.${schema}.<table>`. CATALOG_NAME + SCHEMA_NAME are sourced from `App/databricks/app.yaml` env vars per target — no inline hardcoding anywhere in `App/src/`.

Key columns:
- `device_id`, `patient_id`, `time`
- `glucose`, `glucose_out_of_range`
- `device_model`, `firmware_version`
- `region`, `diabetes_type`

Incident table: `${CATALOG_NAME}.${SCHEMA_NAME}.pseudo_incident_7d_labeled`

## Configuration

- **`databricks/app.yaml`** — Databricks App deployment config (env vars + resource bindings; regenerated per-target via `scripts/render_app_yaml.py`).

## Dependencies used and their corresponding license information

### Frontend (`package.json`)

| Dependency | Where used | Why it's used | License |
| --- | --- | --- | --- |
| [**react**](https://github.com/facebook/react) | `App/src/*.jsx` | UI framework | MIT |
| [**react-dom**](https://github.com/facebook/react) | `App/src/main.jsx` | React renderer for browser DOM | MIT |
| [**react-router-dom**](https://github.com/remix-run/react-router) | `App/src/App.jsx`, `App/src/pages/*` | Client-side routing | MIT |
| [**lucide-react**](https://github.com/lucide-icons/lucide) | Icons across pages | Icon set | ISC |
| [**react-markdown**](https://github.com/remarkjs/react-markdown) | MetricsExplained + MAS reply rendering | Markdown → React component | MIT |
| [**vite**](https://github.com/vitejs/vite) | Build tool (`npm run build`) | Frontend bundler | MIT |
| [**@vitejs/plugin-react**](https://github.com/vitejs/vite-plugin-react) | `vite.config.js` | React fast-refresh + JSX support | MIT |
| [**tailwindcss**](https://github.com/tailwindlabs/tailwindcss) | `tailwind.config.js` + all components | Utility-first CSS | MIT |
| [**postcss**](https://github.com/postcss/postcss) | `postcss.config.js` | CSS transform pipeline (Tailwind processor) | MIT |
| [**autoprefixer**](https://github.com/postcss/autoprefixer) | `postcss.config.js` | Vendor-prefix automation | MIT |

### Backend (`App/databricks/requirements.txt`)

| Dependency | Where used | Why it's used | License |
| --- | --- | --- | --- |
| [**flask**](https://github.com/pallets/flask) | `App/databricks/app.py` | HTTP server framework (routes for `/api/sql/query`, `/api/config`, `/uc-assets/`, `/api/clinician-summary`) | BSD-3-Clause |
| [**requests**](https://github.com/psf/requests) | `App/databricks/app.py` | Outbound HTTP to Databricks Statement Execution API, KA/MAS serving endpoints, UC Files API | Apache-2.0 |

**Note on package URLs.** GitHub source repos linked on names above. If your Databricks workspace or corporate network blocks direct PyPI / npm egress, see the [note on package URLs and network reachability](../Data_DataGen_ModelForecast/README.md#note-on-package-urls-and-network-reachability) under the Data_DataGen dep table for context and Databricks egress-policy pointers.

Python runtime is provided by the Databricks Apps platform — no local Python pin in `App/`. (Repo-root `scripts/` use Python 3.11 via `uv`; see [`DEPLOY.md`](../DEPLOY.md).)

### Platform services (consumed at runtime, not bundled deps)

| Service | Where used | Why it's used |
| --- | --- | --- |
| **Databricks Statement Execution API** | `App/databricks/app.py` `/api/sql/query` | Routes SQL queries to the bundle-managed serverless warehouse |
| **Foundation model** (`databricks-claude-sonnet-4-6`) | `app.py` `/api/assist` (engine=direct) | Device reasoning / Clinical-Analysis — the default fast router's reasoning path |
| **Knowledge Assistant (KA) serving endpoint** | `app.py` `/api/assist` (called directly by the router for clinical Qs; or via MAS) | RAG over WHO clinical-guidelines PDF |
| **Genie space** | `app.py` `/api/genie/query` (CGM-data mode, direct) and via the router/MAS | NL-to-SQL over gold device tables |
| **Multi-Agent Supervisor (MAS) serving endpoint** | `app.py` `/api/assist` (engine=mas — the 🤖 toggle, not default) | Agentic multi-agent orchestration (Beta; slower) |
| **Databricks Apps Platform** | Deployment target | Hosts Flask + React static build |

## License + support

This project is provided AS-IS under the included [`LICENSE.md`](../LICENSE.md) at the repo root, with no warranty or support obligation. For bug reports or feature suggestions, file a [GitHub Issue](https://github.com/databricks-industry-solutions/glucosphere/issues) on the repo.
