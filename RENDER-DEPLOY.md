# Deploy to Render - Quick Guide

## What's Ready
✅ `Procfile` - Tells Render how to start your app  
✅ `requirements.txt` - Updated with gunicorn  
✅ Your Flask app is ready to deploy  

## Step 1: Push to GitHub (5 minutes)

```powershell
# Navigate to your project
cd "d:\event_attendence\4.0"

# Initialize git
git init

# Add files (Render will ignore unnecessary files automatically)
git add .
git commit -m "Deploy to Render"

# Push to your existing GitHub repo
git remote add origin https://github.com/Aneesh1856/event_app.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy on Render (3 minutes)

1. Go to **https://render.com** and sign up/login with GitHub
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `Aneesh1856/event_app`
4. Fill in these settings:
   - **Name**: `event-attendance-app` (or any name you like)
   - **Branch**: `main`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn event_app:app --workers 4 --bind 0.0.0.0:$PORT`
   - **Instance Type**: Free
5. Click **"Create Web Service"**

## Step 3: Environment Variables (if needed)
If you need to set environment variables:
1. In Render dashboard, go to your service
2. Click "Environment" tab
3. Add variables like:
   - `FLASK_ENV=production`
   - Any Firebase config variables

## Your App Will Be Live At:
`https://your-app-name.onrender.com`

## Important Notes:
- ✅ Render automatically ignores virtual environments (`don/` folder)
- ✅ Free tier includes 750 hours/month (enough for demos)
- ✅ Automatic HTTPS certificate
- ⚠️ Free tier sleeps after 15 min of inactivity (takes ~30 seconds to wake up)

## Troubleshooting:
- Check build logs in Render dashboard if deployment fails
- Make sure all your Firebase credentials are properly configured
- First request might be slow (cold start)

**Total time: ~8 minutes from start to live app!** 🚀