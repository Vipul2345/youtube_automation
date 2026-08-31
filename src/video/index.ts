import fs from 'node:fs';
import path from 'node:path';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegPath from '@ffmpeg-installer/ffmpeg';
import ffprobePath from '@ffprobe-installer/ffprobe';
import { PipelineOptions } from '../types/index.js';
import { resolveAssetPools } from '../assets/pool.js';
import { logger } from '../utils/logger.js';

ffmpeg.setFfmpegPath(ffmpegPath.path);
ffmpeg.setFfprobePath(ffprobePath.path);

export interface VideoCompositionInput {
  voiceoverAudioPath: string;
  audioDurationSeconds: number;
  assSubtitlePath: string;
  options: PipelineOptions;
}

function escapeFFmpegPath(filePath: string): string {
  let p = filePath.replace(/\\/g, '/');
  p = p.replace(/^([a-zA-Z]):/, '$1\\:');
  return p;
}

/**
 * 3-Layer Video Composition Engine with Physics Motion Video Support & Audio Ducking.
 */
export async function composeVideo(input: VideoCompositionInput): Promise<string> {
  const { voiceoverAudioPath, audioDurationSeconds, assSubtitlePath, options } = input;

  const outputFilePath = path.resolve(options.output);
  const outputDir = path.dirname(outputFilePath);

  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Resolve background video (or generate 2D physics simulation video)
  const poolAssets = await resolveAssetPools(options, audioDurationSeconds);
  const bgVideoPath = poolAssets.bgVideoPath;
  const bgMusicPath = poolAssets.bgMusicPath;

  if (!bgVideoPath || !fs.existsSync(bgVideoPath)) {
    throw new Error(`ERROR: No valid video background found in assets/backgrounds/ and physics video generator failed.`);
  }

  const isVertical = options.ratio === '9:16';
  const width = isVertical ? 1080 : 1920;
  const height = isVertical ? 1920 : 1080;

  logger.info(`=======================================================`);
  logger.info(`2D PHYSICS & GAMEPLAY 3-LAYER VIDEO COMPOSITION ENGINE`);
  logger.info(`Layer 0 (Bottom): Background Video -> ${path.basename(bgVideoPath)}`);
  logger.info(`Layer 1 (Middle): 20% Dark Overlay Tint`);
  logger.info(`Layer 2 (Top):    Animated ASS Captions -> ${path.basename(assSubtitlePath)}`);
  if (bgMusicPath) {
    logger.info(`Audio Stacking:   Voiceover Track (100%) + Background Music (Ducked -20dB)`);
  } else {
    logger.info(`Audio Stacking:   Voiceover Track (100%)`);
  }
  logger.info(`=======================================================`);

  const hasBgMusic = bgMusicPath && fs.existsSync(bgMusicPath);
  const command = ffmpeg();

  // Input 0: Main Voiceover Audio Track
  command.input(voiceoverAudioPath);

  // Input 1: Background Video Clip (Looped seamlessly via -stream_loop -1)
  command
    .input(bgVideoPath)
    .inputOptions(['-stream_loop', '-1']);

  // Input 2: Optional Background Music Audio Track
  if (hasBgMusic) {
    command.input(bgMusicPath);
  }

  const filterGraph: string[] = [];
  const escapedAssPath = escapeFFmpegPath(assSubtitlePath);

  // Video Filter Graph: Scale, Center-Crop, 1.5x Video Speedup, 20% Dark Tint Overlay, Burn Subtitles
  const videoFilter = `[1:v]scale=${width}:${height}:force_original_aspect_ratio=increase,` +
    `crop=${width}:${height},setpts=PTS/1.5,` +
    `drawbox=y=0:color=black@0.20:width=iw:height=ih:t=fill[vdimmed];` +
    `[vdimmed]subtitles='${escapedAssPath}'[outv]`;

  filterGraph.push(videoFilter);

  // Audio Filter Graph: Main Voiceover (1.0) + Ducked Background Music (-20dB)
  if (hasBgMusic) {
    const audioFilter = `[0:a]volume=1.0[maina];` +
      `[2:a]volume=0.07[bga];` +
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
      .on('error', (err, stdout, stderr) => {
        logger.error(`FFmpeg Composition Failed: ${err.message}`);
        reject(err);
      });

    command.run();
  });
}
