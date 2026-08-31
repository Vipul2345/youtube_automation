import path from 'node:path';
import dotenv from 'dotenv';
import { Command } from 'commander';
import { PipelineOptions, AspectRatio, TTSProvider } from '../types/index.js';

dotenv.config();

export function parseCLIConfig(argv: string[] = process.argv): PipelineOptions {
  const program = new Command();

  program
    .name('reddit-video-generator')
    .description('Parameter-driven automated video generation framework (supports Excel / JSON batching & single stories)')
    .version('2.0.0')
    .option('--story <id_or_name>', 'Story ID or filename inside /content/stories/ (e.g. tifu_mountain_spirit)')
    .option('-s, --source <source>', 'Source type: "reddit", "local", or "story-id"', 'reddit')
    .option('-sub, --subreddit <name>', 'Subreddit name to fetch stories from', 'stories')
    .option('-t, --timeframe <timeframe>', 'Reddit timeframe: "day", "week", "month", "year", "all"', 'week')
    .option('-c, --count <number>', 'Number of stories to batch process from Reddit', '1')
    .option('-f, --file <path>', 'Explicit path to local text, JSON, or Excel (.xlsx/.csv) story file')
    .option('-e, --excel <path>', 'Path to Excel spreadsheet file containing multiple video names & stories (.xlsx/.csv)')
    .option('-b, --batch <path>', 'Path to batch JSON config file (e.g. content/batch_config.json)')
    .option('-r, --ratio <ratio>', 'Aspect ratio: "9:16" (Shorts/TikTok) or "16:9" (YouTube)', process.env.DEFAULT_ASPECT_RATIO as AspectRatio || '9:16')
    .option('-v, --voice <voice>', 'TTS voice identifier', process.env.DEFAULT_VOICE || 'en-US-AnaNeural')
    .option('--tts <provider>', 'TTS engine: "edge-tts", "openai", "elevenlabs"', (process.env.TTS_PROVIDER as TTSProvider) || 'edge-tts')
    .option('--bg-video <path>', 'Explicit path to background loop video file')
    .option('--bg-music <path>', 'Explicit path to background music file')
    .option('-o, --output <path>', 'Custom destination path for generated video')
    .option('--api-key <key>', 'API key for OpenAI or ElevenLabs')
    .option('--upload-youtube', 'Directly upload exported video to YouTube via YouTube Data API v3', false);

  program.parse(argv);
  const opts = program.opts();

  const rootDir = process.cwd();
  
  // Auto-detect Excel file passed via --excel or --file (.xlsx / .csv)
  let excelFile = opts.excel;
  if (!excelFile && opts.file && (opts.file.endsWith('.xlsx') || opts.file.endsWith('.csv') || opts.file.endsWith('.xls'))) {
    excelFile = opts.file;
  }

  const storyId = opts.story || (opts.file ? path.basename(opts.file, path.extname(opts.file)) : undefined);
  
  let source: 'reddit' | 'local' | 'story-id' = 'story-id';
  if (excelFile || opts.batch) {
    source = 'local';
  } else if (opts.story) {
    source = 'story-id';
  } else if (opts.file) {
    source = 'local';
  } else if (opts.source === 'reddit' || opts.subreddit) {
    source = 'reddit';
  }

  const defaultOutputName = storyId 
    ? `${storyId}_${Date.now()}.mp4`
    : `generated_${Date.now()}.mp4`;

  return {
    storyId,
    source,
    subreddit: opts.subreddit || 'stories',
    timeframe: opts.timeframe || 'month',
    limit: parseInt(opts.count, 10) || 1,
    count: parseInt(opts.count, 10) || 1,
    file: opts.file,
    batchFile: opts.batch,
    excelFile,
    ratio: (opts.ratio === '16:9' ? '16:9' : '9:16') as AspectRatio,
    voice: opts.voice || 'en-US-ChristopherNeural',
    tts: (['edge-tts', 'openai', 'elevenlabs'].includes(opts.tts) ? opts.tts : 'edge-tts') as TTSProvider,
    bgVideo: opts.bgVideo,
    bgMusic: opts.bgMusic,
    output: opts.output || path.join(rootDir, 'output', defaultOutputName),
    tempDir: path.join(rootDir, 'temp'),
    cacheDir: path.join(rootDir, 'temp', 'cache'),
    storiesDir: path.join(rootDir, 'content', 'stories'),
    assetsDir: path.join(rootDir, 'assets'),
    apiKey: opts.apiKey,
    uploadYoutube: Boolean(opts.uploadYoutube)
  };
}
