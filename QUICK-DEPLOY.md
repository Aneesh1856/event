# Quick Render Deployment Commands

## Copy & Paste These Commands:

```powershell
# 1. Navigate to your project
cd "d:\event_attendence\4.0"

# 2. Initialize git and add files
git init
git add .
git commit -m "Deploy to Render"

# 3. Connect to your existing GitHub repo
git remote add origin https://github.com/Aneesh1856/event_app.git
git branch -M main
git push -u origin main
```

## Then:
1. Go to **render.com** → Sign in with GitHub
2. Click **"New +"** → **"Web Service"**  
3. Select your repo: **Aneesh1856/event_app**
4. Settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn event_app:app --workers 4 --bind 0.0.0.0:$PORT`
5. Click **"Create Web Service"**

## Done! 🎉
Your app will be live at: `https://your-app-name.onrender.com`

**Note**: First deployment takes 2-3 minutes. After that, your app is ready for tomorrow's demo!