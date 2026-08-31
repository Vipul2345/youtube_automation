import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { CombinedAudioResult, PipelineOptions } from '../types/index.js';
import { logger } from '../utils/logger.js';

interface CacheManifest {
  [hash: string]: {
    audioPath: string;
    durationSeconds: number;
    textLength: number;
    voice: string;
    tts: string;
    createdAt: string;
    chunks: any[];
  };
}

/**
 * Generate MD5 hash for input text, voice, and tts engine settings.
 */
export function generateContentHash(text: string, voice: string, ttsProvider: string): string {
  return crypto
    .createHash('md5')
    .update(`${text}_${voice}_${ttsProvider}_speed15x_v1`)
    .digest('hex');
}

/**
 * Get cached audio result if hit exists in cacheDir.
 */
export function getCachedVoiceover(
  text: string,
  options: PipelineOptions
): CombinedAudioResult | null {
  const cacheDir = options.cacheDir;
  const manifestPath = path.join(cacheDir, 'manifest.json');

  if (!fs.existsSync(manifestPath)) {
    return null;
  }

  try {
    const manifest: CacheManifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    const hash = generateContentHash(text, options.voice, options.tts);
    const cacheEntry = manifest[hash];

    if (cacheEntry && fs.existsSync(cacheEntry.audioPath)) {
      logger.success(`[CACHE HIT] Found pre-synthesized voiceover audio for hash: ${hash.substring(0, 8)}`);
      return {
        audioPath: cacheEntry.audioPath,
        durationSeconds: cacheEntry.durationSeconds,
        chunks: cacheEntry.chunks,
        fromCache: true
      };
    }
  } catch (err: any) {
    logger.warn(`Failed to read cache manifest: ${err.message}`);
  }

  return null;
}

/**
 * Store generated voiceover audio and metadata in cache directory.
 */
export function saveCachedVoiceover(
  text: string,
  result: CombinedAudioResult,
  options: PipelineOptions
): void {
  const cacheDir = options.cacheDir;
  if (!fs.existsSync(cacheDir)) {
    fs.mkdirSync(cacheDir, { recursive: true });
  }

  const manifestPath = path.join(cacheDir, 'manifest.json');
  const hash = generateContentHash(text, options.voice, options.tts);
  const cachedAudioName = `tts_cached_${hash}.mp3`;
  const cachedAudioPath = path.join(cacheDir, cachedAudioName);

  try {
    // Copy generated audio file to cache folder
    fs.copyFileSync(result.audioPath, cachedAudioPath);

    let manifest: CacheManifest = {};
    if (fs.existsSync(manifestPath)) {
      manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    }

    manifest[hash] = {
      audioPath: cachedAudioPath,
      durationSeconds: result.durationSeconds,
      textLength: text.length,
      voice: options.voice,
      tts: options.tts,
      createdAt: new Date().toISOString(),
      chunks: result.chunks
    };

    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');
    logger.info(`[CACHE STORED] Saved voiceover to cache: ${hash.substring(0, 8)}`);
  } catch (err: any) {
    logger.warn(`Failed to write to cache: ${err.message}`);
  }
}
