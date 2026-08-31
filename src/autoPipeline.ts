#!/usr/bin/env node

import path from 'node:path';
import { runSingleStoryPipeline } from './batch/index.js';
import { parseCLIConfig } from './config/index.js';
import { logger } from './utils/logger.js';
import { PipelineOptions } from './types/index.js';

async function runDailyAutomation() {
  console.log(`
╔═════════════════════════════════════════════════════════════════╗
║         DAILY AUTOMATED YOUTUBE SHORTS GENERATOR & UPLOADER     ║
║                          Version 2.0.0                          ║
╚═════════════════════════════════════════════════════════════════╝
`);

  const baseConfig = parseCLIConfig(process.argv);
  
  // Set default parameters for automated daily YouTube Shorts
  const dailyOptions: PipelineOptions = {
    ...baseConfig,
    source: 'reddit',
    subreddit: baseConfig.subreddit || 'AskReddit',
    ratio: '9:16',
    voice: baseConfig.voice || 'en-US-GuyNeural',
    tts: baseConfig.tts || 'edge-tts',
    uploadYoutube: baseConfig.uploadYoutube || Boolean(process.env.YOUTUBE_REFRESH_TOKEN)
  };

  logger.info(`Starting Daily Automation Run...`);
  logger.info(`Source: Reddit (r/${dailyOptions.subreddit})`);
  logger.info(`Format: 9:16 Vertical Short`);
  logger.info(`YouTube Upload: ${dailyOptions.uploadYoutube ? 'ENABLED ✅' : 'DISABLED ❌ (pass --upload-youtube)'}`);

  try {
    const videoPath = await runSingleStoryPipeline(dailyOptions);
    logger.success(`🎉 DAILY VIDEO GENERATED & PROCESSED: ${videoPath}`);
  } catch (err: any) {
    logger.error(`Daily Automation Pipeline Failed: ${err.message}`);
    process.exit(1);
  }
}

runDailyAutomation();
