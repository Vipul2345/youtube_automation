import fs from 'node:fs';
import path from 'node:path';
import XLSX from 'xlsx';
import { BatchItemOptions } from '../types/index.js';
import { logger } from '../utils/logger.js';

export interface ExcelStoryItem extends BatchItemOptions {
  videoName: string;
  videoStory: string;
}

/**
 * Normalizes column header names to lowercase trimmed strings.
 */
function normalizeHeader(key: string): string {
  return key.toLowerCase().replace(/[^a-z0-9]/g, '_');
}

/**
 * Parses an Excel spreadsheet (.xlsx, .xls, or .csv) and returns a list of batch story items.
 */
export function parseExcelStories(excelFilePath: string): BatchItemOptions[] {
  const resolvedPath = path.resolve(excelFilePath);
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Excel file not found at path: ${resolvedPath}`);
  }

  logger.info(`Parsing Excel spreadsheet: ${resolvedPath}`);
  const workbook = XLSX.readFile(resolvedPath);
  const firstSheetName = workbook.SheetNames[0];

  if (!firstSheetName) {
    throw new Error(`Excel file ${excelFilePath} contains no sheets.`);
  }

  const sheet = workbook.Sheets[firstSheetName];
  const rawRows: Record<string, any>[] = XLSX.utils.sheet_to_json(sheet);

  if (!Array.isArray(rawRows) || rawRows.length === 0) {
    throw new Error(`Excel sheet '${firstSheetName}' is empty.`);
  }

  logger.info(`Found ${rawRows.length} rows in sheet '${firstSheetName}'`);

  const batchItems: BatchItemOptions[] = [];

  for (let i = 0; i < rawRows.length; i++) {
    const rawRow = rawRows[i];
    const rowKeys = Object.keys(rawRow);

    // Flexible column mapping
    let videoName = '';
    let videoStory = '';
    let ratio: any = undefined;
    let voice: string | undefined = undefined;
    let tts: any = undefined;
    let bgVideo: string | undefined = undefined;
    let bgMusic: string | undefined = undefined;
    let output: string | undefined = undefined;

    for (const key of rowKeys) {
      const normKey = normalizeHeader(key);
      const val = String(rawRow[key] || '').trim();

      if (['video_name', 'name', 'story_id', 'id', 'title'].includes(normKey)) {
        videoName = val;
      } else if (['video_story', 'story', 'story_text', 'text', 'content', 'body'].includes(normKey)) {
        videoStory = val;
      } else if (['ratio', 'aspect_ratio'].includes(normKey)) {
        ratio = val === '16:9' ? '16:9' : '9:16';
      } else if (['voice', 'voice_id', 'tts_voice'].includes(normKey)) {
        voice = val;
      } else if (['tts', 'provider', 'tts_provider'].includes(normKey)) {
        tts = val;
      } else if (['bg_video', 'background_video'].includes(normKey)) {
        bgVideo = val;
      } else if (['bg_music', 'background_music'].includes(normKey)) {
        bgMusic = val;
      } else if (['output', 'output_file', 'destination'].includes(normKey)) {
        output = val;
      }
    }

    // Default fallback for video name if missing
    if (!videoName) {
      videoName = `excel_story_${i + 1}`;
    }

    if (!videoStory) {
      logger.warn(`Row ${i + 1} has no story text. Skipping row.`);
      continue;
    }

    // Save temporary text story file to content/stories/ if not already existing
    const sanitizeName = videoName.replace(/[^a-zA-Z0-9_-]/g, '_');
    const tempStoryPath = path.join(process.cwd(), 'content', 'stories', `${sanitizeName}.txt`);
    
    if (!fs.existsSync(path.dirname(tempStoryPath))) {
      fs.mkdirSync(path.dirname(tempStoryPath), { recursive: true });
    }
    
    fs.writeFileSync(tempStoryPath, `${videoName}\n\n${videoStory}`, 'utf-8');

    batchItems.push({
      story: sanitizeName,
      ratio,
      voice,
      tts,
      bgVideo,
      bgMusic,
      output: output || `${sanitizeName}_${Date.now()}.mp4`
    });
  }

  logger.success(`Successfully extracted ${batchItems.length} story items from Excel sheet.`);
  return batchItems;
}
