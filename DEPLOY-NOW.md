# Quick Render Deployment Commands

## Copy and Paste These Commands:

```powershell
# 1. Navigate to your project
cd "d:\event_attendence\4.0"

# 2. Check your files are ready
echo "Checking deployment files..."
if (Test-Path "Procfile") { Write-Host "✅ Procfile exists" } else { Write-Host "❌ Procfile missing" }
if (Test-Path "requirements.txt") { Write-Host "✅ requirements.txt exists" } else { Write-Host "❌ requirements.txt missing" }
if (Test-Path "firebase-credentials.json") { Write-Host "✅ firebase-credentials.json exists" } else { Write-Host "❌ firebase-credentials.json missing" }

# 3. Git add, commit, and push
git add .
git commit -m "Deploy to Render - ready for demo"
git push origin main

# 4. Deploy message
Write-Host ""
Write-Host "🚀 Code pushed to GitHub!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Go to render.com" -ForegroundColor White
Write-Host "2. New + → Web Service" -ForegroundColor White
Write-Host "3. Connect Aneesh1856/event_app repo" -ForegroundColor White
Write-Host "4. Use these settings:" -ForegroundColor White
Write-Host "   Build: pip install -r requirements.txt" -ForegroundColor Cyan
Write-Host "   Start: gunicorn event_app:app --workers 4 --bind 0.0.0.0:`$PORT" -ForegroundColor Cyan
Write-Host "5. Click Create Web Service" -ForegroundColor White
Write-Host ""
Write-Host "Your app will be live in 3-5 minutes! 🎉" -ForegroundColor Green
```

## Manual Steps on Render.com:

1. **Go to**: https://render.com
2. **Sign in** with GitHub
3. **New +** → **Web Service**
4. **Select repo**: `Aneesh1856/event_app`
5. **Settings**:
   - Name: `event-attendance-app`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn event_app:app --workers 4 --bind 0.0.0.0:$PORT`
   - Plan: Free
6. **Create Web Service**

## Expected Result:
🌐 Your app live at: `https://event-attendance-app.onrender.com`

**Time to deploy: 5-8 minutes total**