# 📁 Project Structure

This document describes the organization of the GlucoStream Intelligence Dashboard project.

---

## 🏗️ Directory Layout

```
glucosphere-cursor/
├── 📱 src/                          # React application source code
│   ├── pages/                       # Dashboard pages
│   │   ├── GlucoseLandingDashboard.jsx
│   │   ├── CareManagementDashboard.jsx
│   │   ├── ClinicianDashboard.jsx
│   │   └── DeviceSupportDashboard.jsx
│   ├── components/                  # Reusable React components
│   │   └── AgentChatInterface.jsx
│   ├── api/                         # API clients
│   │   └── databricksAgent.js
│   ├── App.jsx                      # Main app with routing
│   ├── main.jsx                     # React entry point
│   └── index.css                    # Global styles
│
├── 🔧 scripts/                      # Python deployment scripts
│   ├── deploy.py                    # Multi-workspace deployment wrapper
│   ├── databricks_deploy.py         # Core deployment logic
│   ├── manage_apps.py               # App management utility
│   └── ... (other utility scripts)
│
├── ⚙️ config/                       # Configuration files
│   ├── databricks_config.json       # Active workspace config (gitignored)
│   ├── databricks_config_buildathon.json
│   ├── databricks_config_field-eng.json
│   └── databricks_config.example.json
│
├── 🚀 databricks/                   # Databricks deployment files
│   ├── app.py                       # Flask server for Databricks
│   ├── app.yaml                     # Databricks App configuration
│   └── Dockerfile                   # Container configuration
│
├── 📚 docs/                         # Documentation
│   ├── DATABRICKS_QUICK_DEPLOY.md
│   ├── MULTI_WORKSPACE_GUIDE.md
│   ├── AGENT_INTEGRATION_GUIDE.md
│   └── ... (other documentation)
│
├── 📦 files/                        # Original JSX files
│   ├── glucose-landing.jsx
│   ├── care-management-dashboard.jsx
│   ├── clinician-dashboard.jsx
│   └── device-support-dashboard.jsx
│
├── 🏗️ dist/                         # Build output (generated)
│   └── ... (compiled files)
│
├── 📄 Root Files                    # Essential configs
│   ├── README.md                    # Main documentation
│   ├── package.json                 # npm dependencies
│   ├── vite.config.js               # Vite build config
│   ├── tailwind.config.js           # Tailwind CSS config
│   ├── postcss.config.js            # PostCSS config
│   ├── index.html                   # HTML entry point
│   ├── .gitignore                   # Git ignore rules
│   ├── .env.local                   # Local env vars (gitignored)
│   └── .env.example                 # Example env vars
│
└── 📦 node_modules/                 # npm dependencies (gitignored)
```

---

## 🎯 Key Directories Explained

### `/src/` - Application Source Code
Contains all React components, pages, API clients, and styles. This is where you develop the frontend.

### `/scripts/` - Deployment & Utilities
All Python scripts for deploying and managing the app across different Databricks workspaces.

**Main scripts:**
- `deploy.py` - Deploy to specific workspaces
- `databricks_deploy.py` - Core deployment logic
- `manage_apps.py` - Start/stop/delete apps

### `/config/` - Configuration Files
Workspace-specific Databricks configurations (host, token, app name).

**Key files:**
- `databricks_config.json` - Active workspace (auto-generated)
- `databricks_config_buildathon.json` - Buildathon workspace
- `databricks_config_field-eng.json` - Field Engineering workspace
- `databricks_config.example.json` - Template for new workspaces

### `/databricks/` - Databricks Deployment Files
Files specifically needed for Databricks Apps deployment.

- `app.py` - Flask server that serves the React app
- `app.yaml` - Databricks App configuration
- `Dockerfile` - Container configuration (if needed)

### `/docs/` - Documentation
Comprehensive guides and documentation for deployment, configuration, and features.

### `/files/` - Original Files
Original JSX files provided at project start (kept for reference).

---

## 🚀 Quick Command Reference

### Local Development
```bash
npm install          # Install dependencies
npm run dev          # Start dev server
npm run build        # Build for production
```

### Deployment
```bash
# Deploy to specific workspace
python3 scripts/deploy.py buildathon
python3 scripts/deploy.py field-eng

# Show available workspaces
python3 scripts/deploy.py

# Manage apps
python3 scripts/manage_apps.py status buildathon
python3 scripts/manage_apps.py list buildathon
```

### Configuration
```bash
# Create new workspace config
cp config/databricks_config.example.json config/databricks_config_myworkspace.json

# Edit the config
nano config/databricks_config_myworkspace.json
```

---

## 📝 File Naming Conventions

### Configuration Files
- `databricks_config_<workspace-name>.json` - Workspace-specific config
- `databricks_config.json` - Active workspace (auto-generated)

### Scripts
- `*_deploy.py` - Deployment-related scripts
- `manage_*.py` - Management utilities

### Documentation
- `*_GUIDE.md` - Step-by-step guides
- `*_README.md` - Overview documentation
- `*_STATUS.md` - Status tracking

---

## 🔒 Gitignored Files

The following files/directories are NOT committed to Git:

```
node_modules/                       # npm dependencies
dist/                               # Build output
config/databricks_config.json       # Active config with tokens
config/databricks_config_*.json     # Workspace configs with tokens
.env.local                          # Local environment variables
*.log                               # Log files
```

**Important:** Never commit files containing Databricks tokens!

---

## 🎨 Organization Benefits

✅ **Clean Root** - Only essential config files in the root
✅ **Logical Grouping** - Related files organized together
✅ **Easy Navigation** - Find files quickly by category
✅ **Scalability** - Easy to add new workspaces/scripts/docs
✅ **Professional** - Industry-standard project structure

---

## 📖 Related Documentation

- [README.md](../README.md) - Main project documentation
- [docs/DATABRICKS_QUICK_DEPLOY.md](docs/DATABRICKS_QUICK_DEPLOY.md) - Deployment guide
- [docs/MULTI_WORKSPACE_GUIDE.md](docs/MULTI_WORKSPACE_GUIDE.md) - Multi-workspace setup
- [docs/AGENT_INTEGRATION_GUIDE.md](docs/AGENT_INTEGRATION_GUIDE.md) - AI chat integration

---

**Last Updated:** January 2026

