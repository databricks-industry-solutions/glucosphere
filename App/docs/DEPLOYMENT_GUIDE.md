# GlucoStream Dashboard Deployment Guide

## ⚠️ IMPORTANT SECURITY NOTE
**Your Databricks token has been exposed in this conversation. Please regenerate it immediately:**
1. Go to: https://dbc-daad7993-4a57.cloud.databricks.com/#setting/account
2. Click "Access tokens"
3. Revoke token: `[REDACTED_TOKEN]`
4. Generate a new one

---

## 📊 Current Status

✅ **App is built and working locally**
- Local dev server: http://localhost:5173
- Production build: `dist/` folder
- All features functional with fake data

❌ **Databricks Deployment Limitations Found:**
- Databricks Apps API not available in this workspace
- Public DBFS access is disabled (security policy)
- FileStore uploads blocked

---

## 🚀 Deployment Options (Ranked by Ease)

### **Option 1: Deploy to Vercel (RECOMMENDED - 2 minutes)**

Vercel is perfect for React apps and completely free:

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy (from the project folder)
cd /Users/justin.ward/Desktop/code/buildathon
vercel --prod
```

**Benefits:**
- ✅ Free forever
- ✅ Automatic HTTPS
- ✅ Global CDN
- ✅ Takes 2 minutes
- ✅ Custom domain support
- ✅ Automatic deployments on git push

**Access:** You'll get a URL like `https://glucostream-dashboard.vercel.app`

---

### **Option 2: Deploy to Netlify (Also Easy & Free)**

```bash
# Install Netlify CLI
npm install -g netlify-cli

# Deploy
cd /Users/justin.ward/Desktop/code/buildathon
netlify deploy --prod --dir=dist
```

**Access:** You'll get a URL like `https://glucostream-dashboard.netlify.app`

---

### **Option 3: GitHub Pages (Free)**

1. Create a GitHub repository
2. Push your code
3. Run: `npm run build`
4. Deploy to gh-pages:
```bash
npm install -g gh-pages
gh-pages -d dist
```

---

### **Option 4: AWS S3 Static Website (If you have AWS)**

```bash
# Install AWS CLI
# Then:
aws s3 sync dist/ s3://your-bucket-name --acl public-read
aws s3 website s3://your-bucket-name --index-document index.html
```

---

### **Option 5: Databricks Workspace (Manual Upload)**

Since automated upload is blocked, you can manually upload via UI:

1. **Open Databricks UI:** https://dbc-daad7993-4a57.cloud.databricks.com
2. **Go to Workspace** → Your user folder
3. **Create a Repo or Folder** called "glucostream"
4. **Upload files** from `dist/` folder manually
5. **Create a notebook** with this code:

```python
# Databricks notebook
displayHTML(open('/Workspace/Users/justin.ward@databricks.com/glucostream/index.html').read())
```

**Note:** This only displays in the notebook, not as standalone app.

---

### **Option 6: Run Docker Container Locally**

If you want to test deployment:

```bash
cd /Users/justin.ward/Desktop/code/buildathon
docker build -t glucostream-dashboard .
docker run -p 8080:8080 glucostream-dashboard
```

Access at: http://localhost:8080

---

## 📋 What We Created for You

1. ✅ **Notebook in Databricks**
   - Location: Workspace → Users → justin.ward@databricks.com → GlucoStream_Dashboard
   - URL: https://dbc-daad7993-4a57.cloud.databricks.com/#notebook/1583306449254098

2. ✅ **Local Development Server**
   - Currently running at http://localhost:5173
   - Hot reload enabled

3. ✅ **Production Build**
   - Location: `dist/` folder
   - Optimized and minified
   - Ready to deploy anywhere

4. ✅ **Deployment Scripts**
   - `deploy_databricks.py` - Databricks deployment checker
   - `upload_to_databricks.py` - DBFS upload script (blocked by policy)
   - `Dockerfile` - Container configuration

---

## 🎯 Recommended Next Steps

### **Best Option: Deploy to Vercel (5 minutes)**

```bash
# 1. Install Vercel
npm install -g vercel

# 2. Login (creates account if needed)
vercel login

# 3. Deploy
cd /Users/justin.ward/Desktop/code/buildathon
vercel --prod
```

That's it! Your app will be live at a public URL that you can share.

---

## 💡 Why Not Databricks Apps?

Databricks Apps is a newer feature (preview) that requires:
1. Databricks workspace version with Apps enabled
2. Specific admin permissions
3. Enterprise or Pro tier (typically)

Your workspace (`dbc-daad7993-4a57.cloud.databricks.com`) appears to be configured with:
- Public DBFS disabled (good security practice)
- Apps API not enabled (common for older workspaces)

This is normal and expected for many enterprise Databricks environments.

---

## 📞 Need Help?

The app is **100% functional** locally. For production hosting:
- **Easiest:** Vercel (recommended)
- **Enterprise:** Contact your Databricks admin about enabling Apps
- **Custom:** Any static hosting service works (S3, Azure Blob, etc.)

---

## 🔧 App Features

Your deployed app includes:
- 🏠 Landing page with real-time metrics
- 🏥 Care Management Dashboard (patient triage)
- 👨‍⚕️ Clinician Dashboard (encounter prep)
- 🔧 Device Support Dashboard (biomedical eng)
- 🎨 Full Tailwind CSS styling
- 📱 Responsive design
- ✨ Interactive animations
- 🔄 Live data updates (fake data for demo)

All ready to connect to real APIs when needed!

