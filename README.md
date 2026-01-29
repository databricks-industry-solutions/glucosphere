# hls-glucosphere

## Overview

This repo contains two main parts that work together:

- **`Data_DataGen_ModelForecast/`**: Databricks notebooks/scripts to ingest Continuous Glucose Monitoring (CGM) data, generate pseudo-patients, train forecasting models, simulate incidents, and deploy models to serving.
- **`App/`**: The dashboard “front-end” (Databricks App) that integrates **Genie Space** and **Agents**. It reads curated **bronze/silver/gold** tables derived from patient **CGM/IoT** signals (see [`Data_DataGen_ModelForecast/README_data.md`](Data_DataGen_ModelForecast/README_data.md)).

**glucosphere concept**: a monitoring “engine/sphere” on the Databricks platform that turns CGM + context data into curated signals, forecasts, and incident monitoring, then surfaces **actionable insights** via dashboards and agentic workflows (Genie / multi-agent tools) for multiple personas (e.g., physicians, caregivers, patients, device/MedTech teams, and regulators such as FDA review boards).

## Power of this solution

- **End-to-end monitoring sphere**: one coherent loop from CGM + context data → curated tables → forecasting/incident analytics → dashboards + agentic workflows.
- **Actionable, not just descriptive**: produces KPIs, alerts, and explanations teams can act on (e.g., calibration-bug detection via performance + distribution shifts).
- **Multi‑persona leverage**: supports physicians/caregivers, device/MedTech teams, patients, and regulators with views tailored to their needs—backed by the same governed data/model layer.
- **Flexible integration**: exposes both **inference tables** (easy DBSQL consumption) and **serving endpoints** (for real-time use when needed).
- **Governance + auditability**: Unity Catalog + MLflow provide lineage/traceability from data → curated tables/inference outputs → models → downstream metrics, improving trust, operations, and compliance. Feature tables can be incorporated later if/when needed.

## Architecture

![Architecture](Data_DataGen_ModelForecast/assets/architecture_0.1.png)

## Repository structure

High-level layout:

```text
/
├── App/
│   ├── src/                 # React UI (pages/components/api)
│   ├── scripts/             # Deployment & workspace utilities
│   ├── databricks/          # Databricks App runtime/config (app.yaml, Dockerfile, etc.)
│   ├── config/              # Workspace config templates (do not commit secrets)
│   ├── docs/                # Deployment + ops docs
│   ├── package.json         # Frontend deps
│   └── README.md
├── Data_DataGen_ModelForecast/
│   ├── assets/
│   ├── configs/
│   ├── dev/
│   ├── utils/
│   ├── 01_download_data.ipynb
│   ├── 02_parseNcombine_processed_data.ipynb
│   ├── 03_extract_baselineTS_EDAcheck.py
│   ├── 04_CGM_PseudoGeneration_CleanData_Modeling.py
│   ├── 05_CGM_Incident_Inference_DeviceCalibrationBug.py
│   ├── 06_DeployModel_as_ServingEndpoint.py
│   ├── README.md
│   └── README_data.md
└── README.md
```

### `Data_DataGen_ModelForecast/` (data + models)

- **What it does**: Ingest → baseline windows → pseudo-patient generation → clean-model training → incident simulation → model serving.
- **Key outputs**:
  - Unity Catalog **Delta tables** (bronze/silver/gold-style progression)
  - MLflow-tracked **forecast models** (e.g., 15m/30m horizons)
  - Incident-labeled tables and “fleet forecast” demo tables
- **Assets**:
  - `Data_DataGen_ModelForecast/assets/`: generated figures used in documentation (forecast accuracy, incident impact, distribution shifts).
  - `Data_DataGen_ModelForecast/configs/baseline_config.yaml`: environment-specific pipeline parameters.

### `App/`

Databricks App code (UI + dashboards + **Genie/Agent** experiences). The app reads curated bronze/silver/gold tables (and inference outputs) produced by `Data_DataGen_ModelForecast/`.

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

---

## Contributors

### Buildathon FY26Q4

Team 11 (HLS) — Real-time Digital Health Apps for Connected Devices

Justin Ward | Morgan Williams | May Merkle-Tan | Nikita Kamraj | Sabrina Wang
