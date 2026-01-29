# Databricks Apps Deployment Files

This directory contains everything needed to deploy your React app to Databricks Apps.

## 🎯 Core Deployment Files

### **databricks_deploy.py** ⭐
Main deployment script - run this to deploy to Databricks

```bash
python3 databricks_deploy.py
```

### **databricks_config.json** 🔒
Your workspace credentials (NEVER commit this!)

```json
{
  "databricks_host": "https://your-workspace.databricks.com",
  "databricks_token": "dapi...",
  "app_name": "your-app-name",
  ...
}
```

### **databricks_config.example.json** 📋
Template for credentials - commit this, copy and edit for your setup

### **app.py**
Flask server that serves your React application

### **app.yaml**
Databricks Apps configuration file

---

## 📚 Documentation

### **DATABRICKS_QUICK_DEPLOY.md** ⚡
Quick reference guide for deployment commands and troubleshooting

### **DATABRICKS_DEPLOYMENT.md**
Detailed deployment guide with options and explanations

### **DEPLOYMENT_SUCCESS.md**
Record of successful deployment with URLs and IDs

---

## 🚀 Quick Deploy

```bash
# 1. First time setup
cp databricks_config.example.json databricks_config.json
# Edit databricks_config.json with your credentials

# 2. Build your app
npm run build

# 3. Deploy to Databricks
python3 databricks_deploy.py
```

---

## 🔐 Security

**NEVER commit these files:**
- `databricks_config.json` (contains your token)
- `*.token` files
- `.env` files with credentials

**Safe to commit:**
- `databricks_config.example.json` (template only)
- `databricks_deploy.py` (deployment script)
- `app.py` and `app.yaml` (app code)
- All documentation files

---

## ✅ Current Deployment

**App Name:** glucostream-dashboard  
**URL:** https://glucostream-dashboard-984752964297111.11.azure.databricksapps.com  
**Status:** ✅ Running  

To redeploy after changes:
```bash
npm run build
python3 databricks_deploy.py
```

---

## 📖 More Info

See `DATABRICKS_QUICK_DEPLOY.md` for complete documentation.

