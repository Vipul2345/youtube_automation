export type AspectRatio = '16:9' | '9:16';

export type TTSProvider = 'edge-tts' | 'openai' | 'elevenlabs';

export interface StoryContent {
  id: string;
  title: string;
  body: string;
  fullRawText: string;
  cleanedText: string;
  author: string;
  subreddit?: string;
  url?: string;
  score?: number;
}

export interface TTSChunk {
  text: string;
  audioPath: string;
  durationSeconds: number;
  wordCount: number;
}

export interface CombinedAudioResult {
  audioPath: string;
  durationSeconds: number;
  chunks: TTSChunk[];
  fromCache?: boolean;
}

export interface CaptionWord {
  word: string;
  startTimeSec: number;
  endTimeSec: number;
}

export interface CaptionItem {
  index: number;
  startTimeSec: number;
  endTimeSec: number;
  formattedStartSRT: string;
  formattedEndSRT: string;
  formattedStartASS: string;
  formattedEndASS: string;
  text: string;
  words?: CaptionWord[];
}

export interface BatchItemOptions {
  story?: string;
  subreddit?: string;
  timeframe?: 'day' | 'week' | 'month' | 'year' | 'all';
  limit?: number;
  ratio?: AspectRatio;
  voice?: string;
  tts?: TTSProvider;
  bgVideo?: string;
  bgMusic?: string;
  output?: string;
  uploadYoutube?: boolean;
}

export interface PipelineOptions {
  storyId?: string;
  source: 'reddit' | 'local' | 'story-id';
  subreddit: string;
  timeframe: 'day' | 'week' | 'month' | 'year' | 'all';
  limit: number;
  file?: string;
  ratio: AspectRatio;
  voice: string;
  tts: TTSProvider;
  bgVideo?: string;
  bgMusic?: string;
  output: string;
  tempDir: string;
  cacheDir: string;
  storiesDir: string;
  assetsDir: string;
  apiKey?: string;
  batchFile?: string;
  excelFile?: string;
  count?: number;
  uploadYoutube?: boolean;
}

export interface BatchRunResult {
  total: number;
  successful: number;
  failed: number;
  results: {
    storyId: string;
    success: boolean;
    outputPath?: string;
    error?: string;
    durationMs: number;
  }[];
}
