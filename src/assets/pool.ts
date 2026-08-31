import fs from 'node:fs';
import path from 'node:path';
import { PipelineOptions } from '../types/index.js';
import { downloadBackgroundVideo } from '../downloader/index.js';
import { generatePhysicsBackgroundVideo } from '../canvas/physicsEngine.js';
import { logger } from '../utils/logger.js';

export interface SelectedAssets {
  bgVideoPath: string;
  bgMusicPath?: string;
}

/**
 * Scans asset pool directories (/assets/backgrounds & /assets/music) and selects video and audio assets.
 * If no local background video exists, generates a 2D physics simulation video background with shape collisions!
 */
export async function resolveAssetPools(options: PipelineOptions, durationSeconds: number = 60): Promise<SelectedAssets> {
  const assetsDir = options.assetsDir || path.join(process.cwd(), 'assets');
  const bgVideoDir = path.join(assetsDir, 'backgrounds');
  const bgMusicDir = path.join(assetsDir, 'music');

  let bgVideoPath = options.bgVideo;
  let bgMusicPath = options.bgMusic;

  // Check for explicit physics keyword
  if (bgVideoPath === 'physics' || bgVideoPath === 'procedural' || bgVideoPath === 'canvas') {
    logger.info(`[ASSET POOL] Explicit physics engine selected. Generating 2D physics background...`);
    const tempDir = options.tempDir || path.join(process.cwd(), 'temp');
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }
    const physicsBgPath = path.join(tempDir, `physics_bg_${Math.ceil(durationSeconds)}s_${Date.now()}.mp4`);
    const width = options.ratio === '16:9' ? 1920 : 1080;
    const height = options.ratio === '16:9' ? 1080 : 1920;
    bgVideoPath = await generatePhysicsBackgroundVideo(durationSeconds + 1, width, height, physicsBgPath);
  } else if (!bgVideoPath || !fs.existsSync(bgVideoPath)) {
    const videoExtensions = ['.mp4', '.mov', '.mkv', '.webm'];
    let videoFiles: string[] = [];

    if (fs.existsSync(bgVideoDir)) {
      videoFiles = fs
        .readdirSync(bgVideoDir)
        .filter(file => videoExtensions.includes(path.extname(file).toLowerCase()))
        .map(file => path.join(bgVideoDir, file));
    }

    if (videoFiles.length > 0) {
      const randomIndex = Math.floor(Math.random() * videoFiles.length);
      bgVideoPath = videoFiles[randomIndex];
      logger.info(`[ASSET POOL] Selected local background video: ${path.basename(bgVideoPath)} (${randomIndex + 1}/${videoFiles.length})`);
    } else {
      // Local pool empty: try automatic background downloader first, then fallback to procedural 2D physics canvas
      try {
        bgVideoPath = await downloadBackgroundVideo(bgVideoDir);
      } catch (err: any) {
        logger.warn(`Background video download failed: ${err.message}. Generating procedural 2D physics background canvas...`);
        const tempDir = options.tempDir || path.join(process.cwd(), 'temp');
        if (!fs.existsSync(tempDir)) {
          fs.mkdirSync(tempDir, { recursive: true });
        }

        const physicsBgPath = path.join(tempDir, `physics_bg_${Math.ceil(durationSeconds)}s_${Date.now()}.mp4`);
        const width = options.ratio === '16:9' ? 1920 : 1080;
        const height = options.ratio === '16:9' ? 1080 : 1920;

        bgVideoPath = await generatePhysicsBackgroundVideo(durationSeconds + 1, width, height, physicsBgPath);
      }
    }
  }

  // Resolve background music from pool if available
  if (!bgMusicPath || !fs.existsSync(bgMusicPath)) {
    if (fs.existsSync(bgMusicDir)) {
      const musicExtensions = ['.mp3', '.wav', '.aac', '.m4a', '.flac'];
      const musicFiles = fs
        .readdirSync(bgMusicDir)
        .filter(file => musicExtensions.includes(path.extname(file).toLowerCase()))
        .map(file => path.join(bgMusicDir, file));

      if (musicFiles.length > 0) {
        const randomIndex = Math.floor(Math.random() * musicFiles.length);
        bgMusicPath = musicFiles[randomIndex];
        logger.info(`[ASSET POOL] Selected background music: ${path.basename(bgMusicPath)} (${randomIndex + 1}/${musicFiles.length})`);
      }
    }
  }

  return {
    bgVideoPath,
    bgMusicPath
  };
}
