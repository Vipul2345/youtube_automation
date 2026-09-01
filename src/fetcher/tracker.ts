import fs from 'node:fs';
import path from 'node:path';
import { logger } from '../utils/logger.js';

interface HistoryRecord {
  postedIds: string[];
  lastRunDate?: string;
}

function getPrimaryHistoryFilePath(): string {
  const dir = path.join(process.cwd(), 'content');
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return path.join(dir, 'posted_stories.json');
}

function getLegacyHistoryFilePath(): string {
  return path.join(process.cwd(), 'temp', 'posted_stories.json');
}

export function loadPostedHistory(): HistoryRecord {
  const idsSet = new Set<string>();
  let lastRunDate: string | undefined;

  const pathsToSearch = [getPrimaryHistoryFilePath(), getLegacyHistoryFilePath()];

  for (const filePath of pathsToSearch) {
    if (fs.existsSync(filePath)) {
      try {
        const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        if (Array.isArray(data.postedIds)) {
          data.postedIds.forEach((id: string) => idsSet.add(id));
        }
        if (data.lastRunDate && (!lastRunDate || data.lastRunDate > lastRunDate)) {
          lastRunDate = data.lastRunDate;
        }
      } catch (err: any) {
        logger.warn(`Failed to read posted history file at ${filePath}: ${err.message}`);
      }
    }
  }

  return {
    postedIds: Array.from(idsSet),
    lastRunDate
  };
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

  const primaryPath = getPrimaryHistoryFilePath();
  const legacyPath = getLegacyHistoryFilePath();

  try {
    const jsonContent = JSON.stringify(history, null, 2);
    fs.writeFileSync(primaryPath, jsonContent, 'utf-8');
    
    const tempDir = path.dirname(legacyPath);
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }
    fs.writeFileSync(legacyPath, jsonContent, 'utf-8');

    logger.info(`[STORY TRACKER] Marked story '${storyId}' as posted (Total tracked stories: ${history.postedIds.length}).`);
  } catch (err: any) {
    logger.warn(`Failed to update posted history file: ${err.message}`);
  }
}
