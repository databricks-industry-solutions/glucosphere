# Databricks Apps - Quick Deploy Guide

## 🚀 Quick Start

Deploy your app in 3 steps:

```bash
# 1. Build your app
npm run build

# 2. Configure credentials
cp config/databricks_config.example.json config/databricks_config.json
# Edit config/databricks_config.json with your details

# 3. Deploy
python3 scripts/databricks_deploy.py
```

---

## 📋 Prerequisites

### Required Files:
- `databricks/app.py` - Flask/Python server to serve your app
- `databricks/app.yaml` - Databricks App configuration
- `dist/` - Your built React/static files
- `config/databricks_config.json` - Workspace credentials

### Python Dependencies:
```bash
pip3 install requests
```

---

## ⚙️ Configuration

### 1. Create Config File

```bash
cp config/databricks_config.example.json config/databricks_config.json
```

### 2. Edit `config/databricks_config.json`

```json
{
  "databricks_host": "https://your-workspace.cloud.databricks.com",
  "databricks_token": "dapi...",
  "app_name": "your-app-name",
  "app_description": "Your app description",
  "username": "your.email@company.com",
  "workspace_path": "/Workspace/Users/your.email@company.com/.bundle/your-app-name/files",
  "build_dir": "dist"
}
```

### Get Your Token:
1. Go to your Databricks workspace
2. Click User Settings → Access Tokens
3. Generate new token
4. Copy to config file

---

## 📝 Required Files

### `app.py` (Flask Server)

```python
from flask import Flask, send_from_directory, send_file

app = Flask(__name__, static_folder='dist')

@app.route('/')
def index():
    return send_file('dist/index.html')

@app.route('/<path:path>')
def serve(path):
    if path.startswith('assets/'):
        return send_from_directory('dist', path)
    return send_file('dist/index.html')  # For React Router

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

### `app.yaml` (App Config)

```yaml
command: ["python", "app.py"]
```

---

## 🚀 Deployment Commands

### Full Deployment:
```bash
python3 databricks_deploy.py
```

### Check App Status:
```bash
curl -X GET \
  "https://your-workspace.databricks.com/api/2.0/apps/your-app-name" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  | python3 -m json.tool
```

### Update Existing App:
```bash
# Just run deployment again - it will update
npm run build
python3 databricks_deploy.py
```

### Stop App:
```bash
curl -X POST \
  "https://your-workspace.databricks.com/api/2.0/apps/your-app-name/stop" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Start App:
```bash
curl -X POST \
  "https://your-workspace.databricks.com/api/2.0/apps/your-app-name/start" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Delete App:
```bash
curl -X DELETE \
  "https://your-workspace.databricks.com/api/2.0/apps/your-app-name" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📂 Project Structure

```
your-project/
├── databricks_deploy.py          # Deployment script
├── databricks_config.json         # Your credentials (gitignored)
├── databricks_config.example.json # Template
├── app.py                         # Flask server
├── app.yaml                       # Databricks config
├── package.json                   # NPM config
├── dist/                          # Built app (from npm run build)
│   ├── index.html
│   └── assets/
├── src/                           # Source code
└── README.md
```

---

## 🔄 Typical Workflow

### Initial Deployment:
```bash
# 1. Setup
npm install
cp databricks_config.example.json databricks_config.json
# Edit databricks_config.json

# 2. Build and deploy
npm run build
python3 databricks_deploy.py
```

### Making Updates:
```bash
# 1. Make your changes to src/

# 2. Rebuild and redeploy
npm run build
python3 databricks_deploy.py
```

---

## 🐛 Troubleshooting

### "App already exists"
- Script will automatically update existing app
- Or delete it first using curl DELETE command

### "Compute not ACTIVE"
- Script waits automatically (up to 10 minutes)
- Check Databricks UI for errors

### "Upload failed"
- Check token permissions
- Verify workspace path exists
- Ensure files are built (dist/ folder exists)

### "App shows error"
- Check app.py is correct
- Verify build directory matches app.yaml
- Check app logs in Databricks UI

---

## 🔒 Security

### Never Commit Tokens!

Add to `.gitignore`:
```
databricks_config.json
*.token
.env
```

Keep in repo:
```
databricks_config.example.json  # Template only
databricks_deploy.py            # Deployment script
app.py                          # Server code
app.yaml                        # App config
```

---

## 📊 What Gets Deployed

1. **App Infrastructure**
   - Databricks App container
   - Service principal
   - Compute resources
   - Public URL

2. **Your Code**
   - app.py (Flask server)
   - app.yaml (configuration)
   - dist/ (built React app)
   - All assets and files

3. **Result**
   - Live web app at: `https://your-app-name-{workspace-id}.databricksapps.com`
   - Integrated with workspace auth
   - Auto-scaling compute

---

## ✅ Success Checklist

Before deploying:
- [ ] Build is successful (`npm run build`)
- [ ] `dist/` folder exists with files
- [ ] `app.py` is present
- [ ] `app.yaml` is present
- [ ] `databricks_config.json` is configured
- [ ] Token has proper permissions
- [ ] Workspace supports Databricks Apps

---

## 🎯 GlucoStream Dashboard - Current Config

Your current successful deployment:

```json
{
  "databricks_host": "https://adb-984752964297111.11.azuredatabricks.net",
  "app_name": "glucostream-dashboard",
  "app_url": "https://glucostream-dashboard-984752964297111.11.azure.databricksapps.com",
  "deployment_id": "01f0d6ea1db71c928f241131fa5d5f2b"
}
```

To redeploy:
```bash
npm run build
python3 databricks_deploy.py
```

---

## 📞 Support

- **Databricks Docs**: https://docs.databricks.com/en/dev-tools/databricks-apps/
- **Apps API**: https://docs.databricks.com/api/workspace/apps
- **Check workspace**: Go to workspace URL → Apps section

---

*Last Updated: December 11, 2025*

