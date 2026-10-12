# Copy-Paste Commands to Fix and Deploy

## Step 1: Fix Git Security Issue
```powershell
cd "d:\event_attendence\4.0"
git add .
git commit -m "Secure deployment - use environment variables for credentials"
git push origin main
```

## Step 2: Get Firebase Credentials for Environment Variable
```powershell
# This copies your Firebase JSON content to clipboard
Get-Content "firebase-credentials.json" | Set-Clipboard
Write-Host "✅ Firebase credentials copied to clipboard!"
Write-Host "You can now paste them in Render dashboard"
```

## Step 3: Deploy on Render
1. Go to: **https://render.com**
2. Sign in with GitHub
3. **New +** → **Web Service**
4. Select: **Aneesh1856/event_app**
5. Settings:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn event_app:app --workers 4 --bind 0.0.0.0:$PORT`
6. **Create Web Service**

## Step 4: Add Environment Variable
1. In Render dashboard → Your service → **Environment** tab
2. Add variable:
   - **Key**: `FIREBASE_CREDENTIALS_JSON`
   - **Value**: Paste the JSON from clipboard (Step 2)
3. **Save Changes**

## Result:
🎉 **Secure deployment complete!**
🌐 **App URL**: https://your-app-name.onrender.com

---
**This is the professional way to deploy with secrets!**