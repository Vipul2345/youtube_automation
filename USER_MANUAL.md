# Headless Automated Video Generation Framework (V2.0.0)
## Complete User Manual & Deployment Guide

Welcome to the **Headless Automated Video Generation Framework**. This CLI tool transforms text stories (Excel sheets, local `.txt` files, JSON configs, or live Reddit posts) into short-form (9:16 Shorts/Reels/TikTok) or long-form (16:9 YouTube) videos with voiceovers, synchronized animated captions, and background video loops or dynamic 2D physics simulations.

---

## 📋 Table of Contents

1. [Prerequisites & System Requirements](#1-prerequisites--system-requirements)
2. [Installation & Project Setup](#2-installation--project-setup)
3. [Project Directory Structure](#3-project-directory-structure)
4. [Story Input Modes](#4-story-input-modes)
   - [Mode A: Excel Spreadsheet Import (.xlsx / .csv)](#mode-a-excel-spreadsheet-import-xlsx--csv)
   - [Mode B: Single Story Lookup (--story)](#mode-b-single-story-lookup---story)
   - [Mode C: Custom File Path (--file)](#mode-c-custom-file-path---file)
   - [Mode D: JSON Batch Processing (--batch)](#mode-d-json-batch-processing---batch)
   - [Mode E: Live Reddit API Fetcher (--source=reddit)](#mode-e-live-reddit-api-fetcher---sourcereddit)
5. [Visual Background Engine](#5-visual-background-engine)
   - [Local Background Video Pool](#local-background-video-pool)
   - [Procedural 2D Physics Canvas Engine](#procedural-2d-physics-canvas-engine)
6. [Text-to-Speech (TTS) & Caching Engine](#6-text-to-speech-tts--caching-engine)
7. [High-Impact Caption Styling](#7-high-impact-caption-styling)
8. [CLI Command Reference](#8-cli-command-reference)
9. [Package Dependency Audit](#9-package-dependency-audit)

---

## 1. Prerequisites & System Requirements

- **Node.js**: `v18.0.0` or higher (Tested on Node `v22.12.0`).
- **npm**: `v9.0.0` or higher.
- **Operating System**: Windows, macOS, or Linux.
- **FFmpeg & FFprobe**: Pre-bundled automatically via `@ffmpeg-installer/ffmpeg` and `@ffprobe-installer/ffprobe` npm packages.
- **yt-dlp** *(Optional)*: If you want to automatically download gameplay video clips from YouTube directly into `/assets/backgrounds/`.

---

## 2. Installation & Project Setup

1. **Clone or Copy Project**:
   ```bash
   git clone <repository_url>
   cd Reddit_stories
   ```

2. **Install Dependencies**:
   ```bash
   npm install
   ```

3. **Build the TypeScript Source**:
   ```bash
   npm run build
   ```

4. **Environment Variables (.env)** *(Optional)*:
   Create a `.env` file in the project root if using third-party TTS services:
   ```env
   TTS_PROVIDER=edge-tts
   DEFAULT_VOICE=en-US-ChristopherNeural
   DEFAULT_ASPECT_RATIO=9:16
   OPENAI_API_KEY=your_openai_key_here
   ELEVENLABS_API_KEY=your_elevenlabs_key_here
   ```

---

## 3. Project Directory Structure

```
Reddit_stories/
├── assets/
│   ├── backgrounds/     # Put your background gameplay/satisfying .mp4 loops here
│   └── music/           # Put your background music .mp3 / .wav files here
├── content/
│   ├── sample_stories.xlsx  # Sample Excel spreadsheet for batch processing
│   ├── batch_config.json    # Sample JSON batch configuration
│   └── stories/             # Put text story files here (e.g. tifu_mountain_spirit.txt)
├── output/              # All final exported MP4 videos are saved here
├── temp/                # Temporary files, cached TTS audio, ASS captions
│   └── cache/           # MD5 Hash cache for synthesized voiceover audio
├── src/
│   ├── assets/          # Asset pool selector & hash cache module
│   ├── batch/           # Batch queue runner & execution reporter
│   ├── canvas/          # 2D Physics Canvas Simulation Engine
│   ├── captions/        # Subtitle generator & Hormozi typography builder
│   ├── config/          # Commander CLI parser & environment configuration
│   ├── downloader/      # YouTube gameplay video downloader wrapper
│   ├── fetcher/         # Story loader & Excel spreadsheet importer (.xlsx/.csv)
│   ├── tts/             # Edge-TTS / OpenAI / ElevenLabs TTS synthesizers
│   ├── utils/           # Color logger & text cleaner utilities
│   ├── video/           # 3-Layer FFmpeg composite engine
│   └── index.ts         # Master CLI controller entry point
├── package.json
└── README.md
```

---

## 4. Story Input Modes

### Mode A: Excel Spreadsheet Import (.xlsx / .csv)
Process a batch of stories from an Excel file in one command.

**Excel Column Headers Supported** (case-insensitive):
- **Video Name**: `video_name`, `name`, `story_id`, `id`, or `title`
- **Video Story**: `video_story`, `story`, `story_text`, `text`, `content`, or `body`
- **Optional**: `ratio` (`9:16` or `16:9`), `voice`, `tts`, `bg_video`, `bg_music`

**Command**:
```bash
npm run excel
# OR
npm run generate -- --excel content/sample_stories.xlsx
```

---

### Mode B: Single Story Lookup (--story)
Process a single story text file stored in `/content/stories/`:

```bash
npm run generate -- --story="tifu_mountain_spirit" --ratio="9:16"
```

---

### Mode C: Custom File Path (--file)
Specify an explicit path to a local text file or Excel file:

```bash
npm run generate -- --file="content/stories/my_custom_story.txt"
# OR pass an Excel file directly:
npm run generate -- --file="content/stories.xlsx"
```

---

### Mode D: JSON Batch Processing (--batch)
Run a batch queue defined in a JSON file:

```bash
npm run batch
# OR
npm run generate -- --batch content/batch_config.json
```

---

### Mode E: Live Reddit API Fetcher (--source=reddit)
Fetch top posts live from Reddit without an API key:

```bash
npm run generate -- --source=reddit --subreddit=AskReddit --count=3 --timeframe=week
```

---

## 5. Visual Background Engine

### Local Background Video Pool
Drop vertical (`1080x1920`) or horizontal (`1920x1080`) `.mp4` video clips into `assets/backgrounds/`. The framework randomly selects a background video clip per video generation and loops it seamlessly across the story duration.

### Procedural 2D Physics Canvas Engine
If no local background video file exists in `assets/backgrounds/`, the framework automatically generates a **2D Physics Motion Video Backdrop**:
- **Multiple Shapes**: Circles, Squares, Triangles, Pentagons, Hexagons, and 5-Pointed Stars in neon colors.
- **Side Wall Bounce**: Shapes bounce elastically off left and right boundaries ($vx = -vx$).
- **Top & Bottom Wrap-Around**: Shapes exiting top/bottom boundaries wrap around to the opposite edge.
- **Elastic 2D Collisions**: Pairwise physical impulse repulsions and angular torque spin.

---

## 6. Text-to-Speech (TTS) & Caching Engine

- **Free Edge-TTS** (Default): Uses Microsoft Edge natural neural voices (`en-US-ChristopherNeural`, `en-US-GuyNeural`, `en-US-JennyNeural`, `en-GB-SoniaNeural`).
- **OpenAI TTS** (`--tts=openai`): High-quality OpenAI voices (`alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`).
- **ElevenLabs** (`--tts=elevenlabs`): Realistic voice cloning / premium voices.
- **Content MD5 Caching**: TTS audio is hashed by story text + voice ID and stored in `temp/cache/`. Duplicate generations load instantly from cache!

---

## 7. High-Impact Caption Styling

Captions are generated as ASS subtitles (`.ass`) with:
- **Typography**: `Arial Black`, 68pt bold font size.
- **Outlines & Shadows**: 6px thick dark outline with a 4px drop shadow.
- **Active Word Pop-Out Highlight**: Current spoken words pop out in electric yellow (`#00FFFF`) with a `115%` scale animation (`{\fscx115\fscy115}`).
- **Speech Sync**: Subtitle duration is normalized to actual TTS word duration with punctuation pause compensation.

---

## 8. CLI Command Reference

| Flag / Option | Description | Default |
| :--- | :--- | :--- |
| `-e, --excel <path>` | Path to Excel spreadsheet containing story entries | `None` |
| `--story <id>` | Story ID inside `/content/stories/` | `tifu_mountain_spirit` |
| `-f, --file <path>` | Path to local `.txt`, `.json`, or `.xlsx` file | `None` |
| `-b, --batch <path>` | Path to JSON batch config file | `None` |
| `-r, --ratio <ratio>` | Aspect ratio: `9:16` (Vertical) or `16:9` (Horizontal) | `9:16` |
| `-v, --voice <name>` | TTS voice identifier | `en-US-ChristopherNeural` |
| `--tts <provider>` | TTS engine (`edge-tts`, `openai`, `elevenlabs`) | `edge-tts` |
| `--bg-video <path>` | Path to background video clip | `2D Physics Simulation` |
| `--bg-music <path>` | Path to background audio track | `None` |
| `-o, --output <path>` | Custom destination path for exported video | `output/<story_id>.mp4` |
| `-s, --source <source>` | Input source (`story-id`, `local`, `reddit`) | `story-id` |
| `-sub, --subreddit` | Subreddit to fetch stories from | `AskReddit` |
| `-c, --count <num>` | Number of stories to process | `1` |

---

## 9. Package Dependency Audit

All required dependencies are specified in [`package.json`](file:///d:/videos/Reddit_stories/package.json):

```json
"dependencies": {
  "@ffmpeg-installer/ffmpeg": "^1.1.0",
  "@ffprobe-installer/ffprobe": "^2.1.2",
  "axios": "^1.7.9",
  "canvas": "^3.2.3",
  "commander": "^12.1.0",
  "dotenv": "^16.4.7",
  "fluent-ffmpeg": "^2.1.3",
  "node-edge-tts": "^1.2.3",
  "xlsx": "^0.18.5"
},
"devDependencies": {
  "@types/fluent-ffmpeg": "^2.1.27",
  "@types/node": "^22.10.1",
  "tsx": "^4.19.2",
  "typescript": "^5.7.2"
}
```

---

## 🚀 Quick Start Example

```bash
# 1. Install dependencies
npm install

# 2. Build project
npm run build

# 3. Process an Excel spreadsheet of stories:
npm run excel

# 4. Process a single custom story:
npm run generate -- --story="askreddit_time_travel" --ratio="9:16"
```
