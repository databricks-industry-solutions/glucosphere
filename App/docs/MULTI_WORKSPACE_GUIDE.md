# 🚀 Multi-Workspace Deployment Guide

Deploy your app to multiple Databricks workspaces with a single command!

---

## 📋 Available Workspaces

### **field-eng** (Field Engineering)
- URL: https://adb-984752964297111.11.azuredatabricks.net
- Config: `config/databricks_config_field-eng.json`

### **buildathon** (Buildathon)
- URL: https://fe-vm-industry-solutions-buildathon.cloud.databricks.com
- Config: `config/databricks_config_buildathon.json`

---

## 🎯 Quick Deploy Commands

### Deploy to Field Engineering:
```bash
npm run build
python3 scripts/deploy.py field-eng
```

### Deploy to Buildathon:
```bash
npm run build
python3 scripts/deploy.py buildathon
```

### Show Available Workspaces:
```bash
python3 scripts/deploy.py
```

---

## 📝 How It Works

1. **Workspace Configs** - Each workspace has its own config file:
   - `config/databricks_config_field-eng.json`
   - `config/databricks_config_buildathon.json`

2. **Smart Switcher** - `scripts/deploy.py` automatically:
   - Switches to the requested workspace
   - Copies the workspace config to `config/databricks_config.json`
   - Runs the deployment

3. **One Command** - Just specify the workspace name:
   ```bash
   python3 scripts/deploy.py <workspace-name>
   ```

---

## ✨ Simple Usage

Just tell me (or run):

**"Deploy to field-eng"** →
```bash
python3 scripts/deploy.py field-eng
```

**"Deploy to buildathon"** →
```bash
python3 scripts/deploy.py buildathon
```

That's it! The script handles everything else.

---

## 🔄 Adding New Workspaces

### 1. Create Config File:
```bash
cp databricks_config.example.json databricks_config_myworkspace.json
# Edit with your workspace details
```

### 2. Add to deploy.py:
Edit `deploy.py` and add to the `WORKSPACES` dictionary:
```python
'myworkspace': {
    'config_file': 'databricks_config_myworkspace.json',
    'description': 'My Workspace Description',
    'url': 'https://your-workspace.databricks.com'
}
```

### 3. Deploy:
```bash
python3 deploy.py myworkspace
```

---

## 🏢 Current Workspace Status

### Field-Eng:
- ✅ Configured and tested
- 🌐 https://glucostream-dashboard-984752964297111.11.azure.databricksapps.com
- 📊 Status: Running

### Buildathon:
- ✅ Configured and ready
- ⏳ Pending first deployment

---

## 📂 File Structure

```
your-project/
├── deploy.py                          ⭐ Multi-workspace deployment script
├── databricks_deploy.py               🔧 Core deployment logic
├── databricks_config.json             📝 Active workspace (auto-generated)
├── databricks_config_field-eng.json   🏢 Field Engineering config
├── databricks_config_buildathon.json  🏢 Buildathon config
└── databricks_config.example.json     📋 Template for new workspaces
```

---

## 🔐 Security Notes

**Gitignored files (contain tokens):**
- `databricks_config.json`
- `databricks_config_*.json`

**Safe to commit:**
- `deploy.py`
- `databricks_deploy.py`
- `databricks_config.example.json`

---

## 💡 Pro Tips

### Quick Switch & Deploy:
```bash
# One-liner to build and deploy to specific workspace
npm run build && python3 deploy.py buildathon
```

### Check Which Workspace:
```bash
python3 -c "import json; print(json.load(open('databricks_config.json'))['workspace_name'])"
```

### Deploy to Both:
```bash
npm run build
python3 deploy.py field-eng
python3 deploy.py buildathon
```

---

## 🎊 Ready to Use!

Your multi-workspace setup is complete! Just run:

```bash
python3 deploy.py buildathon
```

to deploy to the buildathon workspace right now!

