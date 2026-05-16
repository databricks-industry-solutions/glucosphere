# Glucosphere App

Glucosphere is a CGM (Continuous Glucose Monitoring) Device Intelligence & Analytics Platform built with React and Flask, deployed on Databricks.

## Overview

This application provides:
- **Real-time Device Monitoring**: Track device health, out-of-range events, and anomalies
- **Landing Page Metrics**: Active patients, devices online, high-risk alerts
- **Incident Analysis**: Visualize CGM device calibration incidents and their impact
- **Multi-Agent Supervisor**: AI-powered device troubleshooting and analysis
- **Heatmap Analytics**: Device performance by model and firmware version

## Architecture

**Frontend**: React + Vite + Tailwind CSS
**Backend**: Flask (proxy server for Databricks APIs)
**Data Source**: Databricks Unity Catalog (`${CATALOG_NAME}.${SCHEMA_NAME}` schema — set per-target via the bundle's `catalog` + `schema` variables; current `mmt_aws_usw2` target writes to `mmt_aws_usw2_catalog.glucosphere_dev`)
**AI Agent**: Databricks Multi-Agent Supervisor

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
- **AI Troubleshooting**: Multi-agent supervisor for device analysis

### Multi-Agent Supervisor
- Chat interface for device troubleshooting
- Deeper analysis for specific devices
- Integration with CGM analytics and clinical knowledge

## Data Schema

Primary table: `hls_glucosphere.cgm.gold_patient_device_readings`

Key columns:
- `device_id`, `patient_id`, `time`
- `glucose`, `glucose_out_of_range`
- `device_model`, `firmware_version`
- `region`, `diabetes_type`

Incident table: `hls_glucosphere.cgm.pseudo_incident_7d_labeled_v20260105`

## Configuration Files

- **config/databricks_config_buildathon.json**: Buildathon workspace config
- **config/databricks_config_field-eng.json**: Field Engineering workspace config
- **databricks/app.yaml**: Databricks App deployment config

## Documentation

See `docs/` folder for detailed documentation:
- Deployment guides
- Agent integration
- Data migration notes
- Troubleshooting

## Tech Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons
- **Backend**: Flask, Requests
- **APIs**: Databricks SQL MCP Server, Multi-Agent Supervisor
- **Deployment**: Databricks Apps Platform

## Support

For issues or questions, contact the HLS Glucosphere team.
