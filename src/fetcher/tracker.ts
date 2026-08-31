import fs from 'node:fs';
import path from 'node:path';
import { logger } from '../utils/logger.js';

interface HistoryRecord {
  postedIds: string[];
  lastRunDate?: string;
}

function getHistoryFilePath(): string {
  const dir = path.join(process.cwd(), 'temp');
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return path.join(dir, 'posted_stories.json');
}

export function loadPostedHistory(): HistoryRecord {
  const filePath = getHistoryFilePath();
  if (fs.existsSync(filePath)) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      return {
        postedIds: Array.isArray(data.postedIds) ? data.postedIds : [],
        lastRunDate: data.lastRunDate
      };
    } catch (err: any) {
      logger.warn(`Failed to read posted history file: ${err.message}`);
    }
  }
  return { postedIds: [] };
}

export function isStoryPosted(storyId: string): boolean {
  const history = loadPostedHistory();
  return history.postedIds.includes(storyId);
}

export function markStoryPosted(storyId: string): void {
  const history = loadPostedHistory();
  if (!history.postedIds.includes(storyId)) {
    history.postedIds.push(storyId);
  }
  history.lastRunDate = new Date().toISOString();

  const filePath = getHistoryFilePath();
  try {
    fs.writeFileSync(filePath, JSON.stringify(history, null, 2), 'utf-8');
    logger.info(`[STORY TRACKER] Marked story '${storyId}' as posted in history log.`);
  } catch (err: any) {
    logger.warn(`Failed to update posted history file: ${err.message}`);
  }
}
