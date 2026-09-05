import fs from 'node:fs';
import path from 'node:path';
import ffmpeg from 'fluent-ffmpeg';
import { logger } from '../utils/logger.js';

export interface RedditCardOptions {
  subreddit: string;
  author: string;
  title: string;
  score?: number;
  outputPath: string;
  width?: number;
  height?: number;
}

/**
 * Escapes XML special characters for SVG text rendering.
 */
function escapeXml(unsafe: string): string {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

/**
 * Wraps title text into multiple lines for SVG rendering.
 */
function wrapText(text: string, maxCharsPerLine: number = 32, maxLines: number = 4): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let currentLine = '';

  for (const word of words) {
    if ((currentLine + ' ' + word).trim().length > maxCharsPerLine) {
      if (currentLine) lines.push(currentLine.trim());
      currentLine = word;
      if (lines.length >= maxLines - 1) break;
    } else {
      currentLine = (currentLine + ' ' + word).trim();
    }
  }
  if (currentLine && lines.length < maxLines) {
    lines.push(currentLine.trim());
  }
  return lines;
}

/**
 * Formats score numbers into 12.4k style.
 */
function formatScore(score?: number): string {
  if (!score || score < 100) return '14.2k';
  if (score >= 1000) return `${(score / 1000).toFixed(1)}k`;
  return String(score);
}

/**
 * Renders an authentic dark-mode Reddit Title Header Card as a PNG overlay.
 */
export async function generateRedditTitleCard(options: RedditCardOptions): Promise<string> {
  const { subreddit, author, title, score, outputPath, width = 1080, height = 1920 } = options;

  const cardWidth = 920;
  const subName = subreddit ? (subreddit.startsWith('r/') ? subreddit : `r/${subreddit}`) : 'r/stories';
  const authorName = author ? (author.startsWith('u/') ? author : `u/${author}`) : 'u/RedditStory';
  const formattedScore = formatScore(score);

  const titleLines = wrapText(title, 34, 4);
  const cardHeight = Math.max(340, 220 + titleLines.length * 52);

  const cardX = (width - cardWidth) / 2;
  const cardY = (height - cardHeight) / 2 - 120; // Slightly above vertical center

  const titleSvgLines = titleLines
    .map((line, idx) => `<tspan x="40" dy="${idx === 0 ? 0 : 54}">${escapeXml(line)}</tspan>`)
    .join('');

  const svgContent = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000000" flood-opacity="0.6" />
    </filter>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1A1A1B" />
      <stop offset="100%" stop-color="#121213" />
    </linearGradient>
  </defs>

  <!-- Dark Mode Reddit Post Card Container -->
  <rect x="${cardX}" y="${cardY}" width="${cardWidth}" height="${cardHeight}" rx="28" fill="url(#bgGrad)" stroke="#343536" stroke-width="2.5" filter="url(#shadow)" />

  <!-- Subreddit Icon (Reddit Orange Circle) -->
  <circle cx="${cardX + 55}" cy="${cardY + 55}" r="22" fill="#FF4500" />
  <text x="${cardX + 55}" y="${cardY + 63}" font-family="Arial, Helvetica, sans-serif" font-weight="900" font-size="24" fill="#FFFFFF" text-anchor="middle">r/</text>

  <!-- Subreddit & Author Metadata -->
  <text x="${cardX + 92}" y="${cardY + 48}" font-family="Arial, Helvetica, sans-serif" font-weight="700" font-size="26" fill="#D7DADC">${escapeXml(subName)}</text>
  <text x="${cardX + 92}" y="${cardY + 74}" font-family="Arial, Helvetica, sans-serif" font-weight="400" font-size="20" fill="#818384">Posted by ${escapeXml(authorName)} • 4h ago</text>

  <!-- Post Title Text -->
  <text x="${cardX + 40}" y="${cardY + 138}" font-family="Arial Black, Helvetica, sans-serif" font-weight="900" font-size="38" fill="#FFFFFF">${titleSvgLines}</text>

  <!-- Upvotes & Comments Footer Badges -->
  <g transform="translate(${cardX + 40}, ${cardY + cardHeight - 55})">
    <!-- Upvote Pill -->
    <rect x="0" y="0" width="140" height="38" rx="19" fill="#272729" stroke="#343536" stroke-width="1.5"/>
    <text x="20" y="25" font-family="Arial, sans-serif" font-size="20" fill="#FF4500">▲</text>
    <text x="48" y="25" font-family="Arial, sans-serif" font-weight="700" font-size="20" fill="#D7DADC">${formattedScore}</text>

    <!-- Comments Pill -->
    <rect x="156" y="0" width="130" height="38" rx="19" fill="#272729" stroke="#343536" stroke-width="1.5"/>
    <text x="176" y="25" font-family="Arial, sans-serif" font-size="18" fill="#D7DADC">💬</text>
    <text x="206" y="25" font-family="Arial, sans-serif" font-weight="700" font-size="20" fill="#D7DADC">1.8k</text>
  </g>
</svg>`;

  const svgPath = outputPath.replace(/\.png$/, '.svg');
  fs.writeFileSync(svgPath, svgContent, 'utf-8');

  // Convert SVG to PNG using FFmpeg
  return new Promise((resolve, reject) => {
    ffmpeg(svgPath)
      .outputOptions(['-vframes 1'])
      .output(outputPath)
      .on('end', () => {
        try {
          if (fs.existsSync(svgPath)) fs.unlinkSync(svgPath);
        } catch (_) {}
        logger.success(`Reddit Title Header Card rendered (${width}x${height}): ${outputPath}`);
        resolve(outputPath);
      })
      .on('error', (err) => {
        logger.warn(`SVG rendering fallback warning: ${err.message}. Using SVG image directly.`);
        resolve(svgPath);
      })
      .run();
  });
}
