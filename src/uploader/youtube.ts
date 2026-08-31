import fs from 'node:fs';
import path from 'node:path';
import { google } from 'googleapis';
import { PipelineOptions } from '../types/index.js';
import { logger } from '../utils/logger.js';

const SCOPES = ['https://www.googleapis.com/auth/youtube.upload'];

/**
 * Initializes OAuth2 client for YouTube Data API v3 authentication.
 */
function getOAuth2Client(options: PipelineOptions) {
  const clientId = process.env.YOUTUBE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET;
  const redirectUri = process.env.YOUTUBE_REDIRECT_URI || 'http://localhost:3000/oauth2callback';

  if (!clientId || !clientSecret) {
    throw new Error(
      `YouTube API Client Credentials missing! Please set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in your .env file.`
    );
  }

  const oauth2Client = new google.auth.OAuth2(clientId, clientSecret, redirectUri);
  const tokenPath = path.join(options.tempDir || path.join(process.cwd(), 'temp'), 'youtube_tokens.json');

  const refreshToken = process.env.YOUTUBE_REFRESH_TOKEN;

  if (refreshToken) {
    logger.info(`Authenticating YouTube API via YOUTUBE_REFRESH_TOKEN environment variable...`);
    oauth2Client.setCredentials({ refresh_token: refreshToken });
  } else if (fs.existsSync(tokenPath)) {
    const tokens = JSON.parse(fs.readFileSync(tokenPath, 'utf-8'));
    oauth2Client.setCredentials(tokens);
  } else {
    logger.warn(`No YouTube OAuth2 tokens found at ${tokenPath} and YOUTUBE_REFRESH_TOKEN is not set.`);
    logger.warn(`To authorize YouTube upload access, set YOUTUBE_REFRESH_TOKEN in your secrets or generate youtube_tokens.json.`);
  }

  return { oauth2Client, tokenPath };
}

export interface YouTubeUploadOptions {
  videoPath: string;
  title: string;
  description?: string;
  tags?: string[];
  privacyStatus?: 'public' | 'unlisted' | 'private';
  isShort?: boolean;
}

/**
 * Directly uploads a rendered video file to YouTube via YouTube Data API v3.
 */
export async function uploadToYouTube(
  uploadOptions: YouTubeUploadOptions,
  pipelineOptions: PipelineOptions
): Promise<string> {
  const { videoPath, title, description, tags, privacyStatus = 'private', isShort = true } = uploadOptions;

  if (!fs.existsSync(videoPath)) {
    throw new Error(`Video file for YouTube upload not found at: ${videoPath}`);
  }

  logger.info(`=======================================================`);
  logger.info(`DIRECT YOUTUBE UPLOADER INITIALIZED`);
  logger.info(`Video: ${path.basename(videoPath)}`);
  logger.info(`Title: "${title}"`);
  logger.info(`Privacy Status: ${privacyStatus.toUpperCase()}`);
  logger.info(`=======================================================`);

  const { oauth2Client } = getOAuth2Client(pipelineOptions);
  const youtube = google.youtube({ version: 'v3', auth: oauth2Client });

  const defaultDescription = isShort
    ? `${description || title}\n\n#Shorts #Storytelling #RedditStories #Viral`
    : `${description || title}\n\nAutomated Storytelling Video. Subscribe for more!`;

  const defaultTags = tags || ['shorts', 'reddit', 'storytelling', 'viral', 'animation'];

  try {
    const fileSize = fs.statSync(videoPath).size;
    logger.info(`Uploading ${(fileSize / (1024 * 1024)).toFixed(2)} MB video stream to YouTube...`);

    const res = await youtube.videos.insert({
      part: ['snippet', 'status'],
      requestBody: {
        snippet: {
          title: title.substring(0, 100),
          description: defaultDescription,
          tags: defaultTags,
          categoryId: '24' // 24 = Entertainment category
        },
        status: {
          privacyStatus,
          selfDeclaredMadeForKids: false
        }
      },
      media: {
        body: fs.createReadStream(videoPath)
      }
    });

    const videoId = res.data.id;
    const youtubeUrl = `https://youtu.be/${videoId}`;

    logger.success(`🎉 VIDEO DIRECTLY PUBLISHED TO YOUTUBE!`);
    logger.success(`YouTube Link: ${youtubeUrl}`);

    return youtubeUrl;
  } catch (err: any) {
    logger.error(`YouTube Direct Upload Failed: ${err.message}`);
    throw err;
  }
}
