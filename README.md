# YouTube Shorts Pipeline

A safety-first pipeline that generates, narrates, captions, renders, validates, and uploads YouTube Shorts. The default configuration is `DRY_RUN=true`, so local runs never upload to YouTube unless explicitly enabled.

## Setup

Requirements:

- Python 3.12
- FFmpeg and `ffprobe` on your PATH
- A Gemini API key and Pexels API key for generation and stock footage

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

Fill in `GEMINI_API_KEY` and `PEXELS_API_KEY` in `.env`. Keep `.env` and OAuth files private; they are ignored by Git.

## Local testing

Run the complete pipeline in safe dry-run mode:

```powershell
$env:DRY_RUN = "true"
python -m shorts_pipeline.main
```

A dry run still generates and renders the MP4, validates it with `ffprobe`, and logs the upload metadata, but does not call YouTube. The output is `output/short.mp4`.

Run the offline test suite and lint checks:

```powershell
pytest
ruff check .
ruff format --check .
```

Useful single-component checks:

```powershell
# Validate configuration and safe defaults
pytest tests/test_settings.py

# Test uploader metadata, history, and media validation without external APIs
pytest tests/test_phase4.py

# Check that the installed command can parse its help
python -m shorts_pipeline.main --help

# Check local media tools
ffmpeg -version
ffprobe -version
```

To perform a real upload locally, configure all YouTube credentials, set `DRY_RUN=false`, and confirm the privacy setting remains appropriate (the default is `private`):

```powershell
$env:DRY_RUN = "false"
python -m shorts_pipeline.main
```

## Google Cloud OAuth refresh token

The uploader uses an OAuth refresh token with the YouTube upload scope. Do this once for the Google account that owns the target channel:

1. Open [Google Cloud Console](https://console.cloud.google.com/) and create or select a project.
2. Enable **YouTube Data API v3** under **APIs & Services > Library**.
3. Configure the OAuth consent screen. Add the required app information and add your Google account as a test user if the app is still in testing.
4. Go to **APIs & Services > Credentials > Create credentials > OAuth client ID**.
5. Select **Desktop app**, create the client, and download the JSON file. Do not commit it.
6. Install the project dependencies, then run the helper from the repository root:

   ```powershell
   python scripts/get_refresh_token.py --client-secrets .\client_secret.json
   ```

   Alternatively, put `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` in `.env` and run:

   ```powershell
   python scripts/get_refresh_token.py
   ```

7. Authorize the requested YouTube upload scope in the browser. The helper runs a callback server on `localhost:8080`.
8. Copy the printed refresh token immediately. Never put it in source control or paste it into logs.
9. Add the client ID, client secret, and refresh token as the GitHub Actions secrets listed below.

If port 8080 is busy, choose another local port with `--port 8765` and authorize again.

## GitHub Actions secrets checklist

Add these as **repository Secrets** at **Settings > Secrets and variables > Actions > New repository secret**:

- [ ] `GEMINI_API_KEY`
- [ ] `PEXELS_API_KEY`
- [ ] `YOUTUBE_CLIENT_ID`
- [ ] `YOUTUBE_CLIENT_SECRET`
- [ ] `YOUTUBE_REFRESH_TOKEN`

The workflow in `.github/workflows/daily_shorts.yml` runs at 08:00 and 16:00 UTC and can also be started with **Run workflow**. It installs Python and FFmpeg/ffprobe, runs the live pipeline, and uploads the rendered MP4 as a seven-day artifact.

The workflow uses the repository `GITHUB_TOKEN` to commit `state/history.json` after successful runs. The workflow has `contents: write` permission and serializes runs with the `youtube-shorts-pipeline` concurrency group so recent topics remain consistent.
