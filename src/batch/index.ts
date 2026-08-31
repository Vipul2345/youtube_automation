import fs from 'node:fs';
import path from 'node:path';
import { PipelineOptions, BatchItemOptions, BatchRunResult } from '../types/index.js';
import { parseExcelStories } from '../fetcher/excel.js';
import { fetchStory } from '../fetcher/index.js';
import { generateVoiceover } from '../tts/index.js';
import { generateCaptions } from '../captions/index.js';
import { composeVideo } from '../video/index.js';
import { logger } from '../utils/logger.js';

/**
 * Executes a single story video generation pipeline.
 */
export async function runSingleStoryPipeline(options: PipelineOptions): Promise<string> {
  const startTime = Date.now();
  logger.info(`Processing story: ${options.storyId || options.file || options.subreddit}`);

  // Step 1: Fetch & Clean
  logger.step(1, 4, 'Content Fetching & Cleaning');
  const story = await fetchStory(options);
  logger.info(`Story Title: "${story.title}" (${story.cleanedText.length} chars)`);

  // Step 2: Voice Synthesis (with Caching)
  logger.step(2, 4, 'Voice Synthesis / TTS (Cache Supported)');
  const audioResult = await generateVoiceover(story.cleanedText, options);

  // Step 3: Subtitle Generation (Hormozi ASS Style)
  logger.step(3, 4, 'Subtitle / Transcription Engine');
  const captionFiles = generateCaptions(audioResult, options.tempDir, options.ratio);

  // Step 4: Video Composition (2D Physics / Gameplay + Audio Ducking)
  logger.step(4, 4, 'Video Composition & Burning Subtitles');
  const finalVideoPath = await composeVideo({
    voiceoverAudioPath: audioResult.audioPath,
    audioDurationSeconds: audioResult.durationSeconds,
    assSubtitlePath: captionFiles.assPath,
    options
  });

  // Optional Step 5: Direct YouTube Upload
  if (options.uploadYoutube) {
    const { uploadToYouTube } = await import('../uploader/youtube.js');
    await uploadToYouTube(
      {
        videoPath: finalVideoPath,
        title: story.title,
        description: story.cleanedText.substring(0, 500),
        privacyStatus: 'public',
        isShort: options.ratio === '9:16'
      },
      options
    );
  }

  const durationMs = Date.now() - startTime;
  logger.success(`Pipeline completed in ${(durationMs / 1000).toFixed(1)}s! Output: ${finalVideoPath}`);
  return finalVideoPath;
}

/**
 * Executes batch processing from an array of batch item options.
 */
export async function executeBatchQueue(
  batchItems: BatchItemOptions[],
  baseOptions: PipelineOptions,
  sourceLabel: string
): Promise<BatchRunResult> {
  logger.info(`Executing batch queue from ${sourceLabel} (${batchItems.length} items).\n`);

  const summary: BatchRunResult = {
    total: batchItems.length,
    successful: 0,
    failed: 0,
    results: []
  };

  for (let i = 0; i < batchItems.length; i++) {
    const item = batchItems[i];
    const storyId = item.story || `batch_item_${i + 1}`;
    const startTime = Date.now();

    console.log(`\n=================================================================`);
    console.log(` BATCH ITEM ${i + 1}/${batchItems.length}: ${storyId.toUpperCase()}`);
    console.log(`=================================================================\n`);

    const outputName = item.output || `${storyId}_${Date.now()}.mp4`;
    const outputPath = path.join(process.cwd(), 'output', outputName);

    const mergedOptions: PipelineOptions = {
      ...baseOptions,
      storyId,
      source: item.story ? 'story-id' : baseOptions.source,
      subreddit: item.subreddit || baseOptions.subreddit,
      ratio: item.ratio || baseOptions.ratio,
      voice: item.voice || baseOptions.voice,
      tts: item.tts || baseOptions.tts,
      bgVideo: item.bgVideo || baseOptions.bgVideo,
      bgMusic: item.bgMusic || baseOptions.bgMusic,
      output: outputPath
    };

    try {
      const renderedPath = await runSingleStoryPipeline(mergedOptions);
      summary.successful++;
      summary.results.push({
        storyId,
        success: true,
        outputPath: renderedPath,
        durationMs: Date.now() - startTime
      });
    } catch (err: any) {
      summary.failed++;
      logger.error(`[BATCH FAILURE] Item '${storyId}' failed: ${err.message}`);
      summary.results.push({
        storyId,
        success: false,
        error: err.message,
        durationMs: Date.now() - startTime
      });
      logger.warn(`Resuming batch run for remaining queue items...`);
    }
  }

  // Print Batch Summary Report
  console.log(`\n╔═════════════════════════════════════════════════════════════════╗`);
  console.log(`║                   BATCH EXECUTION SUMMARY REPORT                ║`);
  console.log(`╚═════════════════════════════════════════════════════════════════╝`);
  console.log(`Source:            ${sourceLabel}`);
  console.log(`Total Queue Items: ${summary.total}`);
  console.log(`✅ Successful:     ${summary.successful}`);
  console.log(`❌ Failed:         ${summary.failed}\n`);

  summary.results.forEach((r, idx) => {
    if (r.success) {
      console.log(` [${idx + 1}] ✅ ${r.storyId} -> ${r.outputPath} (${(r.durationMs / 1000).toFixed(1)}s)`);
    } else {
      console.log(` [${idx + 1}] ❌ ${r.storyId} -> ERROR: ${r.error}`);
    }
  });
  console.log(`-----------------------------------------------------------------\n`);

  return summary;
}

/**
 * Runs batch processing from a batch JSON config file.
 */
export async function runBatchPipeline(
  batchFilePath: string,
  baseOptions: PipelineOptions
): Promise<BatchRunResult> {
  const resolvedPath = path.resolve(batchFilePath);
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Batch configuration file not found: ${resolvedPath}`);
  }

  const rawData = fs.readFileSync(resolvedPath, 'utf-8');
  const batchItems: BatchItemOptions[] = JSON.parse(rawData);

  if (!Array.isArray(batchItems) || batchItems.length === 0) {
    throw new Error(`Batch configuration file must contain a non-empty array of items.`);
  }

  return executeBatchQueue(batchItems, baseOptions, `JSON (${path.basename(batchFilePath)})`);
}

/**
 * Runs batch processing from an Excel spreadsheet (.xlsx, .xls, .csv).
 */
export async function runExcelBatchPipeline(
  excelFilePath: string,
  baseOptions: PipelineOptions
): Promise<BatchRunResult> {
  const batchItems = parseExcelStories(excelFilePath);
  return executeBatchQueue(batchItems, baseOptions, `Excel (${path.basename(excelFilePath)})`);
}
