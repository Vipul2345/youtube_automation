# 🤖 Automated YouTube Channel Setup Guide (GitHub Actions)

This guide walks you through setting up **100% autonomous daily video generation and YouTube Shorts publishing** using your repository and GitHub Actions.

---

## 📋 How It Works Automatically

```
┌────────────────────────────────────────────────────────────────────────┐
│                        GitHub Actions Daily Cron                       │
│                        (Triggered Every 24 Hours)                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│  1. Fetch Fresh Reddit Story (Filters out previously posted IDs)       │
│  2. Download Background Video Clip (Gameplay / ASMR / Satisfying 9:16) │
│  3. Multi-Character TTS Voiceover (Guy + Jenny + Steffan + Ava)        │
│  4. Generate 100% Audio-Synced Lower-Third Hormozi Captions            │
│  5. Render 3-Layer Composite Video (Video + 20% Tint + ASS Captions)   │
│  6. Directly Upload Video to YouTube via YouTube Data API v3           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🔑 Step 1: Get Your YouTube API Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project named **`YouTube Automation`**.
3. Go to **APIs & Services > Library**, search for **YouTube Data API v3**, and click **Enable**.
4. Go to **APIs & Services > OAuth consent screen**:
   - Choose **External**, fill in app name and email, and save.
   - Under **Scopes**, add `https://www.googleapis.com/auth/youtube.upload`.
   - Under **Test users**, add your own Google/YouTube email address.
5. Go to **APIs & Services > Credentials > Create Credentials > OAuth client ID**:
   - Application type: **Web application**.
   - Authorized redirect URIs: `https://developers.google.com/oauthplayground` (or `http://localhost:3000/oauth2callback`).
   - Copy your **Client ID** and **Client Secret**.

---

## 🔓 Step 2: Get Your `YOUTUBE_REFRESH_TOKEN`

1. Open [Google OAuth2 Playground](https://developers.google.com/oauthplayground).
2. Click the ⚙️ **Gear Icon** in the top right:
   - Check **"Use your own OAuth credentials"**.
   - Paste your **OAuth Client ID** and **OAuth Client Secret**.
3. In the left panel, scroll down to **YouTube Data API v3**, expand it, and select:
   - `https://www.googleapis.com/auth/youtube.upload`
4. Click **Authorize APIs** and log in with your YouTube account.
5. Click **Exchange authorization code for tokens**.
6. Copy the **`refresh_token`** string. (This token allows GitHub Actions to automatically publish videos without logging in again!).

---

## 🔐 Step 3: Add Secrets to Your GitHub Repository

1. Push this project folder to your GitHub Repository:
   ```bash
   git init
   git add .
   git commit -m "feat: complete automated youtube shorts channel generator"
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.name.git
   git branch -M main
   git push -u origin main
   ```

2. Go to your GitHub Repository on GitHub.com $\rightarrow$ **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.

3. Add the following **Repository Secrets**:

| Secret Name | Description / Value |
| :--- | :--- |
| **`YOUTUBE_CLIENT_ID`** | Your Google Cloud OAuth Client ID |
| **`YOUTUBE_CLIENT_SECRET`** | Your Google Cloud OAuth Client Secret |
| **`YOUTUBE_REFRESH_TOKEN`** | Your OAuth2 Refresh Token from Step 2 |

*(Optional)* If you use OpenAI or ElevenLabs for TTS, add `OPENAI_API_KEY` or `ELEVENLABS_API_KEY`.

---

## ⚡ Step 4: Test & Run

### Manual Test Trigger (On Demand):
1. Go to your GitHub Repository $\rightarrow$ **Actions** tab.
2. Select **Daily Autonomous YouTube Shorts Generator & Uploader**.
3. Click **Run workflow** $\rightarrow$ **Run workflow**.

### Daily Automatic Schedule:
The GitHub Actions workflow [.github/workflows/daily_video.yml](file:///.github/workflows/daily_video.yml) will trigger **automatically every single day at 14:00 UTC** (7:30 PM IST / 10:00 AM EST), generate a fresh video, and post it to your YouTube channel as a Short!

---

## 💻 Local One-Command Trigger:
You can also run the full daily automation pipeline locally on your computer anytime:
```bash
npm run generate:daily -- --upload-youtube
```
