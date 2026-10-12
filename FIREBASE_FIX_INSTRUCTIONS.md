# Firebase Configuration Fix for Render Deployment

## Issue
Your app is deployed successfully but can't find Firebase credentials because:
- `firebase-credentials.json` is not included in the deployment (security)
- The app needs Firebase to function properly

## Solution: Use Environment Variables

### Step 1: Get Your Firebase Credentials as JSON
1. Go to your Firebase Console
2. Project Settings → Service Accounts
3. Generate/Download your private key JSON file
4. Copy the ENTIRE content of that JSON file

### Step 2: Set Environment Variable in Render
1. Go to your Render dashboard: https://dashboard.render.com
2. Click on your `event-app-2mz8` service
3. Go to "Environment" tab
4. Add a new environment variable:
   - **Key**: `FIREBASE_CREDENTIALS_JSON`
   - **Value**: Paste the entire JSON content from Step 1
   
   Example:
   ```json
   {
     "type": "service_account",
     "project_id": "event-fe792",
     "private_key_id": "abc123...",
     "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
     "client_email": "firebase-adminsdk-...@event-fe792.iam.gserviceaccount.com",
     "client_id": "...",
     "auth_uri": "https://accounts.google.com/o/oauth2/auth",
     "token_uri": "https://oauth2.googleapis.com/token",
     "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
     "client_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs/firebase-adminsdk-...%40event-fe792.iam.gserviceaccount.com"
   }
   ```

5. Click "Save Changes"

### Step 3: Redeploy
After saving the environment variable, Render will automatically redeploy your app.

## Alternative Quick Fix (Temporary)
If you need the app working immediately for your demo tomorrow:

1. Upload `firebase-credentials.json` to your GitHub repo temporarily
2. Remove it from `.gitignore` 
3. Push to GitHub (this will trigger auto-deploy on Render)
4. **IMPORTANT**: Remove the file and add it back to `.gitignore` after the demo

## Your App Status
✅ **App is live**: https://event-app-2mz8.onrender.com  
✅ **Flask app is working**  
❌ **Firebase not connected** (causing login issues)  

Once Firebase is fixed, your app will be fully functional!