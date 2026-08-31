#!/usr/bin/env node

import path from 'node:path';
import { parseCLIConfig } from './config/index.js';
import { runSingleStoryPipeline, runBatchPipeline, runExcelBatchPipeline } from './batch/index.js';
import { logger } from './utils/logger.js';
import { PipelineOptions } from './types/index.js';

async function main() {
  const options = parseCLIConfig(process.argv);

  console.log(`
╔═════════════════════════════════════════════════════════════════╗
║           HEADLESS AUTOMATED VIDEO GENERATION FRAMEWORK         ║
║                           Version 2.0.0                         ║
╚═════════════════════════════════════════════════════════════════╝
`);

  try {
    if (options.excelFile) {
      // Mode 1: Excel Batch Mode (.xlsx, .csv, .xls)
      logger.info(`Mode: EXCEL BATCH IMPORTER (${options.excelFile})`);
      await runExcelBatchPipeline(options.excelFile, options);
    } else if (options.batchFile) {
      // Mode 2: JSON Batch Config Mode
      logger.info(`Mode: JSON BATCH CONFIG (${options.batchFile})`);
      await runBatchPipeline(options.batchFile, options);
    } else if (options.source === 'reddit' && options.count && options.count > 1) {
      // Mode 3: Reddit Multi-post Batch Mode
      logger.info(`Mode: REDDIT SUBREDDIT BATCH (r/${options.subreddit}, Count: ${options.count})`);
      for (let i = 0; i < options.count; i++) {
        const storyId = `reddit_${options.subreddit}_${i + 1}`;
        const outputName = `${storyId}_${Date.now()}.mp4`;
        const itemOptions: PipelineOptions = {
          ...options,
          storyId,
          limit: i,
          output: path.join(process.cwd(), 'output', outputName)
        };
        await runSingleStoryPipeline(itemOptions);
      }
    } else {
      // Mode 4: Single Parameter-Driven Story Mode (Accepts one-by-one story or video name)
      const storyId = options.storyId || 'tifu_mountain_spirit';
      const outputName = `${storyId}_${Date.now()}.mp4`;
      const singleOptions: PipelineOptions = {
        ...options,
        storyId,
        output: options.output || path.join(process.cwd(), 'output', outputName)
      };
      await runSingleStoryPipeline(singleOptions);
    }
  } catch (error: any) {
    logger.error(`Framework Execution Halted!`);
    logger.error(error.stack || error.message);
    process.exit(1);
  }
}

main();
