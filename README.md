# Reddit Story Automated Video Generator

A modular, production-ready Node.js/TypeScript automated video generation pipeline. It automatically fetches storytelling content from public Reddit APIs (e.g., `r/AskReddit`, `r/tifu`, `r/nosleep`) or local text/JSON files, synthesizes high-quality voiceover audio, generates synchronized styled captions, and stitches everything into horizontal (16:9) or vertical (9:16) videos with soft background music.

---

## Features

- **Multi-Source Fetcher (`src/fetcher`)**:
  - Automatically fetches top stories from subreddits via public JSON API endpoints.
  - Supports local `.txt` or `.json` story file inputs.
  - Strips URLs, markdown formatting, emojis, spoiler tags, and normalizes text.
- **Voiceover Synthesis (`src/tts`)**:
  - **Free Out-of-the-Box**: Uses `edge-tts` (Microsoft Edge Neural voices like `en-US-ChristopherNeural`, `en-US-GuyNeural`) requiring **zero API keys**.
  - Optional integration with **OpenAI TTS** (`tts-1`) and **ElevenLabs API**.
  - Splits long stories into logical sentence chunks to respect API length limits.
- **Synchronized Captions (`src/captions`)**:
  - Automatically generates `.srt` and styled `.ass` (Advanced SubStation Alpha) subtitle files.
  - Optimized caption chunking for short-form content (3-4 words per caption on TikTok/Shorts) and long-form (6-10 words on YouTube).
- **FFmpeg Video Composition (`src/video`)**:
  - Automatic scaling and cropping for **9:16 Vertical (1080x1920)** or **16:9 Horizontal (1920x1080)** output.
  - Mixes soft background music under the main TTS voiceover track.
  - Burns styled ASS subtitles directly into the video stream.
  - Fallback synthetic background generator if no custom loop video is provided.

---

## Directory Architecture

```
Reddit_stories/
├── src/
│   ├── types/
│   │   └── index.ts          # TypeScript interfaces & pipeline options
│   ├── utils/
│   │   ├── logger.ts         # Console logger with timestamps & steps
│   │   └── textCleaner.ts    # Markdown, URL, emoji & text cleaner
│   ├── fetcher/
│   │   └── index.ts          # Content fetcher module (Reddit / Local)
│   ├── tts/
│   │   └── index.ts          # Voice synthesis module (Edge-TTS / OpenAI / ElevenLabs)
│   ├── captions/
│   │   └── index.ts          # Subtitle engine (.srt & .ass generator)
│   ├── video/
│   │   └── index.ts          # Video composition engine (FFmpeg filters)
│   └── index.ts              # CLI entry point (Commander)
├── samples/
│   └── sample_story.txt      # Sample text story for instant testing
├── .env.example              # Environment variables template
├── .gitignore                # Git ignore configuration
├── package.json              # Dependencies and scripts
├── tsconfig.json             # TypeScript config
└── README.md                 # Project documentation
```

---

## Prerequisites & Installation

### 1. Prerequisites
- **Node.js**: v18.0.0 or higher
- **npm**: v9.0.0 or higher
- **FFmpeg**: The application automatically includes `@ffmpeg-installer/ffmpeg`. If you wish to use system FFmpeg, ensure `ffmpeg` and `ffprobe` are installed on your system PATH.

### 2. Installation
Clone or navigate to the project directory and install dependencies:

```bash
npm install
```

---

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `TTS_PROVIDER` | TTS Provider (`edge-tts`, `openai`, `elevenlabs`) | `edge-tts` |
| `DEFAULT_VOICE` | Default voice identifier | `en-US-ChristopherNeural` |
| `DEFAULT_ASPECT_RATIO` | Default video aspect ratio (`9:16` or `16:9`) | `9:16` |
| `OUTPUT_DIR` | Output directory path | `./output` |
| `OPENAI_API_KEY` | OpenAI API key (if using `--tts openai`) | `None` |
| `ELEVENLABS_API_KEY` | ElevenLabs API key (if using `--tts elevenlabs`) | `None` |

---

## CLI Usage & Examples

You can run the CLI directly using `npm run dev` (via `tsx`) or build to JavaScript via `npm run build && npm start`.

### CLI Options

| Flag | Description | Default |
|---|---|---|
| `-s, --source <type>` | Content source (`reddit` or `local`) | `reddit` |
| `-sub, --subreddit <name>` | Subreddit to fetch from | `AskReddit` |
| `-t, --timeframe <tf>` | Reddit timeframe (`day`, `week`, `month`, `year`, `all`) | `week` |
| `-l, --limit <n>` | Top posts limit to fetch | `10` |
| `-f, --file <path>` | Path to local text/json file (when `--source local`) | `None` |
| `-r, --ratio <ratio>` | Aspect ratio (`9:16` or `16:9`) | `9:16` |
| `-v, --voice <voice>` | TTS voice identifier | `en-US-ChristopherNeural` |
| `--tts <provider>` | TTS engine (`edge-tts`, `openai`, `elevenlabs`) | `edge-tts` |
| `--bg-video <path>` | Path to background gameplay/relaxing loop video (.mp4) | `Dynamic animated geometric shape fallback` |
| `--bg-music <path>` | Path to background music audio (.mp3 / .wav) | `None` |
| `-o, --output <path>` | Destination path for final video | `output/generated_video.mp4` |

---

### Usage Examples

#### 1. Generate Vertical Video (9:16) from Local Sample Story (Free Edge-TTS)
```bash
npx ts-node src/index.ts --source local --file samples/sample_story.txt --ratio 9:16 -o output/local_sample_short.mp4
```

#### 2. Fetch Top Reddit Post from r/tifu and Generate TikTok/Reels Video
```bash
npx ts-node src/index.ts --source reddit --subreddit tifu --timeframe week --ratio 9:16 -o output/tifu_story.mp4
```

#### 3. Horizontal Video (16:9) with Custom Background Video & Background Music
```bash
npx ts-node src/index.ts \
  --source reddit \
  --subreddit AskReddit \
  --ratio 16:9 \
  --bg-video path/to/minecraft_loop.mp4 \
  --bg-music path/to/relaxing_music.mp3 \
  -o output/askreddit_longform.mp4
```

#### 4. Using OpenAI TTS Engine
```bash
npx ts-node src/index.ts \
  --source local \
  --file samples/sample_story.txt \
  --tts openai \
  --voice alloy \
  --api-key YOUR_OPENAI_API_KEY \
  -o output/openai_story.mp4
```

---

## Customizing Voices (Edge-TTS)

Available Edge-TTS Voices include:
- `en-US-ChristopherNeural` (Male - Deep & Clear)
- `en-US-GuyNeural` (Male - Energetic)
- `en-US-JennyNeural` (Female - Warm)
- `en-US-AriaNeural` (Female - Expressive)
- `en-GB-SoniaNeural` (British Female)
- `en-GB-RyanNeural` (British Male)

---

## License

This project is licensed under the MIT License.
>>>>>>> 7dd6e3a (feat: complete headless automated youtube shorts framework)
