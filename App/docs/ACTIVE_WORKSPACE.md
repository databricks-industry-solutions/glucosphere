# 🎯 Active Workspace: BUILDATHON

Your GlucoStream Dashboard is deployed to the **Buildathon** workspace only.

---

## 🌐 **Live App**

**URL:** https://glucostream-dashboard-237438879023004.aws.databricksapps.com

**Workspace:** https://fe-vm-industry-solutions-buildathon.cloud.databricks.com

**Status:** ✅ Running

---

## 🚀 **Quick Deploy**

```bash
# Build and deploy
npm run build
python3 deploy.py buildathon
```

Or just tell me **"Deploy to buildathon"** and I'll do it!

---

## 📊 **Workspace Status**

| Workspace | Status | Notes |
|-----------|--------|-------|
| **buildathon** | ✅ **ACTIVE** | Primary deployment |
| **field-eng** | ❌ Deleted | Removed to avoid costs |

---

## 🔄 **Available Commands**

### Deploy to Buildathon:
```bash
python3 deploy.py buildathon
```

### Check app status:
```bash
curl -s https://fe-vm-industry-solutions-buildathon.cloud.databricks.com/api/2.0/apps/glucostream-dashboard \
  -H "Authorization: Bearer [REDACTED_TOKEN]" \
  | python3 -m json.tool
```

### Delete app (if needed):
```bash
python3 manage_apps.py delete buildathon
```

---

## 📂 **Configuration Files**

**Active Config:** `databricks_config_buildathon.json`

```json
{
  "workspace_name": "buildathon",
  "databricks_host": "https://fe-vm-industry-solutions-buildathon.cloud.databricks.com",
  "app_name": "glucostream-dashboard",
  ...
}
```

---

## 💡 **If You Need Field-Eng Again**

The config is still saved at `databricks_config_field-eng.json`. To redeploy:

```bash
python3 deploy.py field-eng
```

This will recreate the app in that workspace.

---

## 🎊 **Current Setup**

- ✅ **One active deployment** (buildathon)
- ✅ **Cost optimized** (no unnecessary workspaces)
- ✅ **Easy redeployment** (configs saved)
- ✅ **Simple updates** (one command)

---

**Your app is live at:**
### https://glucostream-dashboard-237438879023004.aws.databricksapps.com

🚀 **Ready to use!**

