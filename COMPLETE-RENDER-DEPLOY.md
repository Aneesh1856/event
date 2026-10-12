# Complete Render Deployment Guide

## Prerequisites ✅
- GitHub account
- Render account (free at render.com)
- Your Flask app ready to deploy

## Step 1: Prepare Your Code (2 minutes)

### Check Your Files
Make sure you have these files in your project:
- ✅ `event_app.py` (your main Flask app)
- ✅ `requirements.txt` (with gunicorn)
- ✅ `Procfile` (tells Render how to start your app)
- ✅ `firebase-credentials.json` (uncommented in .gitignore)

### Quick Check Commands:
```powershell
cd "d:\event_attendence\4.0"
dir Procfile
dir requirements.txt
dir firebase-credentials.json
```

## Step 2: Push to GitHub (3 minutes)

```powershell
# Navigate to your project
cd "d:\event_attendence\4.0"

# Check git status
git status

# Add all files
git add .

# Commit changes
git commit -m "Deploy to Render with Firebase credentials"

# Push to GitHub (your repo: event_app)
git push origin main
```

## Step 3: Deploy on Render (5 minutes)

### 3.1 Go to Render
1. Visit: https://render.com
2. Sign up/Login with your GitHub account

### 3.2 Create New Web Service
1. Click **"New +"** button
2. Select **"Web Service"**
3. Connect your GitHub repository: **Aneesh1856/event_app**

### 3.3 Configure Service Settings
Fill in these details:

**Basic Settings:**
- **Name**: `event-attendance-app` (or any name you prefer)
- **Branch**: `main`
- **Root Directory**: (leave empty)
- **Runtime**: `Python 3`

**Build & Deploy:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn event_app:app --workers 4 --bind 0.0.0.0:$PORT`

**Instance Type:**
- **Plan**: `Free` (perfect for demos)

### 3.4 Deploy
1. Click **"Create Web Service"**
2. Render will start building your app
3. Wait 3-5 minutes for deployment to complete

## Step 4: Monitor Deployment

### Check Build Logs
1. In Render dashboard, click on your service
2. Go to "Logs" tab
3. Watch for:
   - ✅ `Build successful`
   - ✅ `Your service is live 🎉`
   - ✅ `Available at https://your-app-name.onrender.com`

### Test Your App
1. Click the provided URL
2. You should see your login page
3. Try logging in to test Firebase connection

## Step 5: Troubleshooting

### Common Issues:
1. **Build fails**: Check requirements.txt for typos
2. **App won't start**: Verify Procfile syntax
3. **Firebase errors**: Check firebase-credentials.json is included

### Check Service Status:
- Go to Render dashboard
- Check "Events" tab for deployment status
- Check "Logs" tab for runtime errors

## Your App URLs:
- **Dashboard**: https://dashboard.render.com
- **Live App**: https://your-app-name.onrender.com

## Important Notes:
- 🆓 Free tier: 750 hours/month
- 💤 App sleeps after 15 min inactivity (wakes in ~30 seconds)
- 🔄 Auto-deploys when you push to GitHub
- 🌐 Automatic HTTPS included

## Success! 🎉
Your event attendance app is now live and ready for your management demo!

---
**Need help?** Check the logs in Render dashboard or contact support.