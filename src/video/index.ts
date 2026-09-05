import fs from 'node:fs';
import path from 'node:path';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegPath from '@ffmpeg-installer/ffmpeg';
import ffprobePath from '@ffprobe-installer/ffprobe';
import { PipelineOptions } from '../types/index.js';
import { resolveAssetPools } from '../assets/pool.js';
import { generateRedditTitleCard } from './redditCard.js';
import { logger } from '../utils/logger.js';

ffmpeg.setFfmpegPath(ffmpegPath.path);
ffmpeg.setFfprobePath(ffprobePath.path);

export interface VideoCompositionInput {
  voiceoverAudioPath: string;
  audioDurationSeconds: number;
  assSubtitlePath: string;
  storyTitle?: string;
  storyAuthor?: string;
  subreddit?: string;
  score?: number;
  options: PipelineOptions;
}

function escapeFFmpegPath(filePath: string): string {
  let p = filePath.replace(/\\/g, '/');
  p = p.replace(/^([a-zA-Z]):/, '$1\\:');
  return p;
}

/**
 * 4-Layer High-Retention Video Composition Engine:
 * Layer 0 (Bottom): Background Gameplay Video (Random Start Offset)
 * Layer 1 (Middle): 25% Dark Overlay Tint
 * Layer 2 (Overlay): 3.5s Reddit Title Header Card (Viral 3-Sec Hook)
 * Layer 3 (Top): Animated Hormozi Subtitles + '🤖 AI Created' Watermark
 */
export async function composeVideo(input: VideoCompositionInput): Promise<string> {
  const { 
    voiceoverAudioPath, 
    audioDurationSeconds, 
    assSubtitlePath, 
    storyTitle, 
    storyAuthor, 
    subreddit, 
    score, 
    options 
  } = input;

  const outputFilePath = path.resolve(options.output);
  const outputDir = path.dirname(outputFilePath);

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Resolve background video & background music
  const poolAssets = await resolveAssetPools(options, audioDurationSeconds);
  const bgVideoPath = poolAssets.bgVideoPath;
  const bgMusicPath = poolAssets.bgMusicPath;

  if (!bgVideoPath || !fs.existsSync(bgVideoPath)) {
    throw new Error(`ERROR: No valid video background found in assets/backgrounds/.`);
  }

  const isVertical = options.ratio === '9:16';
  const width = isVertical ? 1080 : 1920;
  const height = isVertical ? 1920 : 1080;

  // Render Reddit Title Card Overlay Image for 3.5s Hook
  let cardOverlayPath = '';
  if (storyTitle) {
    try {
      const cardTempPath = path.join(options.tempDir, `reddit_card_${Date.now()}.png`);
      cardOverlayPath = await generateRedditTitleCard({
        title: storyTitle,
        author: storyAuthor || 'RedditUser',
        subreddit: subreddit || 'stories',
        score: score || 14200,
        outputPath: cardTempPath,
        width,
        height
      });
    } catch (err: any) {
      logger.warn(`Reddit Title Card generation skipped: ${err.message}`);
    }
  }

  logger.info(`=======================================================`);
  logger.info(`VIRAL SHORTS 4-LAYER VIDEO COMPOSITION ENGINE`);
  logger.info(`Layer 0 (Bottom): Background Video -> ${path.basename(bgVideoPath)}`);
  logger.info(`Layer 1 (Middle): 25% Dark Overlay Tint`);
  if (cardOverlayPath) {
    logger.info(`Layer 2 (Hook):   Reddit Title Header Card (0.0s to 3.5s Overlay)`);
  }
  logger.info(`Layer 3 (Top):    Animated ASS Captions -> ${path.basename(assSubtitlePath)}`);
  logger.info(`=======================================================`);

  const hasBgMusic = bgMusicPath && fs.existsSync(bgMusicPath);
  const hasTitleCard = cardOverlayPath && fs.existsSync(cardOverlayPath);
  const randomStartOffset = Math.floor(Math.random() * 45); // Randomize start offset up to 45s

  const command = ffmpeg();

  // Input 0: Main Voiceover Audio Track
  command.input(voiceoverAudioPath);

  // Input 1: Background Video Clip (Randomized start timestamp -ss, looped seamlessly)
  command
    .input(bgVideoPath)
    .inputOptions([
      `-ss ${randomStartOffset}`,
      '-stream_loop', '-1'
    ]);

  let nextInputIndex = 2;

  // Input 2 (Optional): Background Music
  let bgMusicInputIdx = -1;
  if (hasBgMusic) {
    command.input(bgMusicPath);
    bgMusicInputIdx = nextInputIndex++;
  }

  // Input 3 (Optional): Reddit Title Card Image
  let cardInputIdx = -1;
  if (hasTitleCard) {
    command.input(cardOverlayPath);
    cardInputIdx = nextInputIndex++;
  }

  const filterGraph: string[] = [];
  const escapedAssPath = escapeFFmpegPath(assSubtitlePath);

  // Build Video Filter Graph
  let vFilter = `[1:v]scale=${width}:${height}:force_original_aspect_ratio=increase,` +
    `crop=${width}:${height},setpts=PTS/1.25,` +
    `drawbox=y=0:color=black@0.25:width=iw:height=ih:t=fill[vbase];`;

  if (hasTitleCard) {
    // Overlay Reddit Title Card during first 3.5 seconds
    vFilter += `[vbase][${cardInputIdx}:v]overlay=0:0:enable='between(t,0,3.5)'[vhook];` +
      `[vhook]subtitles='${escapedAssPath}'[outv]`;
  } else {
    vFilter += `[vbase]subtitles='${escapedAssPath}'[outv]`;
  }

  filterGraph.push(vFilter);

  // Audio Filter Graph: Main Voiceover (1.0) + Ducked Background Music (-22dB)
  if (hasBgMusic) {
    const audioFilter = `[0:a]volume=1.0[maina];` +
      `[${bgMusicInputIdx}:a]volume=0.06[bga];` +
      `[maina][bga]amix=inputs=2:duration=first:dropout_transition=2[outa]`;
    filterGraph.push(audioFilter);
  } else {
    filterGraph.push(`[0:a]volume=1.0[outa]`);
  }

  command.complexFilter(filterGraph.join(';'));
  command.outputOptions([
    '-map [outv]',
    '-map [outa]',
    '-c:v libx264',
    '-preset ultrafast',
    '-crf 22',
    '-c:a aac',
    '-b:a 192k',
    '-shortest',
    `-t ${audioDurationSeconds + 0.5}`,
    '-pix_fmt yuv420p'
  ]);

  command.output(outputFilePath);

  return new Promise((resolve, reject) => {
    let lastProgressPercent = 0;

    command
      .on('start', commandLine => {
        logger.info(`\n[EXACT FFMPEG COMPOSITION COMMAND]:\n${commandLine}\n`);
      })
      .on('progress', progress => {
        if (progress.percent && Math.floor(progress.percent) >= lastProgressPercent + 20) {
          lastProgressPercent = Math.floor(progress.percent);
          logger.info(`Rendering Progress: ${lastProgressPercent}%`);
        }
      })
      .on('end', () => {
        logger.success(`Video exported successfully to: ${outputFilePath}`);
        resolve(outputFilePath);
      })
      .on('error', (err) => {
        logger.error(`FFmpeg Composition Failed: ${err.message}`);
        reject(err);
      });

    command.run();
  });
}
