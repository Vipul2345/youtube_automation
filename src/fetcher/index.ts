import fs from 'node:fs';
import path from 'node:path';
import axios from 'axios';
import { StoryContent, PipelineOptions } from '../types/index.js';
import { cleanStoryText } from '../utils/textCleaner.js';
import { logger } from '../utils/logger.js';

interface RedditPostData {
  id: string;
  title: string;
  selftext: string;
  author: string;
  subreddit: string;
  url: string;
  score: number;
  over_18: boolean;
  is_self: boolean;
}

/**
 * Main story fetcher router.
 */
export async function fetchStory(options: PipelineOptions): Promise<StoryContent> {
  if (options.source === 'reddit') {
    return fetchRedditStory(options.subreddit, options.timeframe, options.limit);
  } else if (options.source === 'local' && options.file) {
    return fetchLocalStory(options.file);
  } else {
    const storyId = options.storyId || 'tifu_mountain_spirit';
    return fetchStoryById(storyId, options.storiesDir);
  }
}

/**
 * Lookup story by ID inside the /content/stories/ folder.
 */
export function fetchStoryById(storyId: string, storiesDir: string): StoryContent {
  const sanitizeId = storyId.replace(/\.txt$|\.json$/, '');
  const storiesFolder = storiesDir || path.join(process.cwd(), 'content', 'stories');

  const txtPath = path.join(storiesFolder, `${sanitizeId}.txt`);
  const jsonPath = path.join(storiesFolder, `${sanitizeId}.json`);

  if (fs.existsSync(jsonPath)) {
    return fetchLocalStory(jsonPath);
  } else if (fs.existsSync(txtPath)) {
    return fetchLocalStory(txtPath);
  } else {
    // If not found in /content/stories/, check if user passed a path directly
    const directPath = path.resolve(storyId);
    if (fs.existsSync(directPath)) {
      return fetchLocalStory(directPath);
    }
    throw new Error(`Story '${storyId}' not found in content directory: ${storiesFolder}`);
  }
}

/**
 * Reads and cleans story text from a local .txt or .json file.
 */
export function fetchLocalStory(filePath?: string): StoryContent {
  if (!filePath) {
    throw new Error('Local source specified, but no file path was provided.');
  }

  const resolvedPath = path.resolve(filePath);
  if (!fs.existsSync(resolvedPath)) {
    throw new Error(`Story file not found at path: ${resolvedPath}`);
  }

  logger.info(`Loading story file: ${resolvedPath}`);
  const rawContent = fs.readFileSync(resolvedPath, 'utf-8');
  const basename = path.basename(filePath, path.extname(filePath));

  if (filePath.endsWith('.json')) {
    try {
      const parsed = JSON.parse(rawContent);
      const title = parsed.title || basename;
      const body = parsed.body || parsed.text || rawContent;
      const combined = `${title}\n\n${body}`;

      return {
        id: parsed.id || basename,
        title,
        body,
        fullRawText: combined,
        cleanedText: cleanStoryText(combined),
        author: parsed.author || 'Local Author'
      };
    } catch (err: any) {
      throw new Error(`Failed to parse JSON file ${filePath}: ${err.message}`);
    }
  }

  const lines = rawContent.split('\n');
  const title = lines[0] ? lines[0].trim() : basename;
  const body = lines.slice(1).join('\n').trim();
  const cleaned = cleanStoryText(rawContent);

  return {
    id: basename,
    title,
    body: body || rawContent,
    fullRawText: rawContent,
    cleanedText: cleaned,
    author: 'Local Author'
  };
}

import { isStoryPosted, markStoryPosted } from './tracker.js';

/**
 * Attempts to obtain an official Reddit OAuth2 Access Token if credentials exist in .env.
 */
async function getRedditOAuthToken(): Promise<string | null> {
  const clientId = process.env.REDDIT_CLIENT_ID;
  const clientSecret = process.env.REDDIT_CLIENT_SECRET;
  const username = process.env.REDDIT_USERNAME;
  const password = process.env.REDDIT_PASSWORD;

  if (!clientId || !clientSecret) {
    return null;
  }

  try {
    logger.info(`Authenticating with Reddit API via OAuth2 (Client ID: ${clientId.slice(0, 5)}...)...`);
    const authHeader = Buffer.from(`${clientId}:${clientSecret}`).toString('base64');
    const params = new URLSearchParams();

    if (username && password) {
      params.append('grant_type', 'password');
      params.append('username', username);
      params.append('password', password);
    } else {
      params.append('grant_type', 'client_credentials');
    }

    const response = await axios.post('https://www.reddit.com/api/v1/access_token', params.toString(), {
      headers: {
        'Authorization': `Basic ${authHeader}`,
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'RedditStoryVideoGenerator/2.0.0 (by /u/AutomatedVideoBot)'
      },
      timeout: 10000
    });

    const token = response.data?.access_token;
    if (token) {
      logger.success(`Reddit OAuth2 Token acquired successfully!`);
      return token;
    }
  } catch (err: any) {
    logger.warn(`Reddit OAuth2 authentication failed: ${err.message}. Falling back to public JSON endpoints.`);
  }

  return null;
}

export const STORY_SUBREDDITS = {
  drama: ['AmItheAsshole', 'relationship_advice', 'confessions', 'offmychest'],
  revenge: ['ProRevenge', 'MaliciousCompliance', 'SupernaturalRevenge'],
  workplace: ['TalesFromRetail', 'TalesFromYourServer', 'talesfromtechsupport'],
  life_stories: ['tifu', 'stories', 'BestofRedditorUpdates'],
  scary_creepy: ['LetsNotMeet', 'nosleep', 'Glitch_in_the_Matrix']
};

export async function fetchRedditStory(
  subreddit: string = 'stories',
  timeframe: string = 'month',
  index: number = 0
): Promise<StoryContent> {
  // Flatten subreddits for fallback search
  const allSubreddits = [
    subreddit,
    ...STORY_SUBREDDITS.life_stories,
    ...STORY_SUBREDDITS.drama,
    ...STORY_SUBREDDITS.revenge,
    ...STORY_SUBREDDITS.workplace
  ].filter((v, i, a) => a.indexOf(v) === i);

  const token = await getRedditOAuthToken();
  let lastError: Error | null = null;

  for (const sub of allSubreddits) {
    const urls: { url: string; headers: Record<string, string> }[] = [];

    if (token) {
      urls.push({
        url: `https://oauth.reddit.com/r/${sub}/top?limit=50&t=${timeframe}`,
        headers: {
          'Authorization': `Bearer ${token}`,
          'User-Agent': 'RedditStoryVideoGenerator/2.0.0 (by /u/AutomatedVideoBot)'
        }
      });
    }

    const userAgent = `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${120 + Math.floor(Math.random() * 5)}.0.0.${Math.floor(Math.random() * 100)} Safari/537.36`;

    // Public JSON Endpoints (with limit=50, timeframe=month/year for top quality)
    urls.push({
      url: `https://www.reddit.com/r/${sub}/top.json?limit=50&t=${timeframe}`,
      headers: {
        'User-Agent': userAgent,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9'
      }
    });
    urls.push({
      url: `https://old.reddit.com/r/${sub}/hot.json?limit=50`,
      headers: {
        'User-Agent': userAgent,
        'Accept': 'application/json'
      }
    });

    // Reddit RSS Atom Feed Endpoint (bypasses 429 rate limits)
    urls.push({
      url: `https://www.reddit.com/r/${sub}/hot.rss`,
      headers: {
        'User-Agent': userAgent,
        'Accept': 'application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8'
      }
    });

    logger.info(`Fetching top-quality stories from r/${sub} (timeframe: ${timeframe}, limit: 50)...`);

    for (const item of urls) {
      try {
        await new Promise(resolve => setTimeout(resolve, 600));

        const response = await axios.get(item.url, {
          headers: item.headers,
          timeout: 10000
        });

        if (item.url.endsWith('.rss')) {
          const xml = String(response.data || '');
          const entries = xml.split('<entry>');
          for (let eIdx = 1; eIdx < entries.length; eIdx++) {
            const entry = entries[eIdx];
            const titleMatch = entry.match(/<title>([^<]+)<\/title>/);
            const contentMatch = entry.match(/<content[^>]*>([\s\S]*?)<\/content>/);
            const idMatch = entry.match(/<id>([^<]+)<\/id>/);

            if (titleMatch && contentMatch) {
              const rawTitle = titleMatch[1];
              const rawContent = contentMatch[1];
              const cleanTitle = cleanStoryText(rawTitle);
              const cleanBody = cleanStoryText(rawContent);
              const postId = idMatch ? idMatch[1].split('/').pop() || `rss_${Date.now()}_${eIdx}` : `rss_${Date.now()}_${eIdx}`;

              // Ensure post is a narrative story (>200 chars) and unread
              if (cleanBody.length >= 200 && cleanBody.length <= 3500 && !isStoryPosted(postId)) {
                markStoryPosted(postId);
                logger.success(`🎉 FETCHED HIGH-QUALITY STORY: "${cleanTitle}" (r/${sub})`);
                const fullRawText = `${cleanTitle}\n\n${cleanBody}`;
                return {
                  id: `reddit_${postId}`,
                  title: cleanTitle,
                  body: cleanBody,
                  fullRawText,
                  cleanedText: fullRawText,
                  author: 'RedditUser',
                  subreddit: sub,
                  url: `https://reddit.com/r/${sub}`,
                  score: 500
                };
              }
            }
          }
          continue;
        }

        const posts = response.data?.data?.children;
        if (!posts || !Array.isArray(posts) || posts.length === 0) {
          continue;
        }

        const validPosts = posts
          .map((child: any) => child.data as RedditPostData)
          .filter((post: RedditPostData) => 
            post.is_self && 
            post.selftext && 
            post.selftext !== '[removed]' &&
            post.selftext !== '[deleted]' &&
            post.selftext.length >= 200 && 
            post.selftext.length <= 3500 &&
            !isStoryPosted(post.id)
          );

        if (validPosts.length === 0) {
          continue;
        }

        const postIndex = Math.min(Math.max(0, index), validPosts.length - 1);
        const selectedPost = validPosts[postIndex] || validPosts[0];

        const cleanTitle = cleanStoryText(selectedPost.title);
        const cleanBody = cleanStoryText(selectedPost.selftext || '');

        markStoryPosted(selectedPost.id);
        logger.success(`🎉 FETCHED HIGH-QUALITY STORY: "${cleanTitle}" by u/${selectedPost.author} (r/${selectedPost.subreddit}, Score: ${selectedPost.score})`);

        const fullCleanText = `${cleanTitle}\n\n${cleanBody}`;

        return {
          id: `reddit_${selectedPost.id}`,
          title: cleanTitle,
          body: cleanBody,
          fullRawText: fullCleanText,
          cleanedText: fullCleanText,
          author: selectedPost.author,
          subreddit: selectedPost.subreddit,
          url: `https://reddit.com${selectedPost.url}`,
          score: selectedPost.score
        };
      } catch (err: any) {
        lastError = err;
      }
    }

    // Attempt PullPush Reddit Archive API (unauthenticated public API endpoint)
    try {
      logger.info(`Fetching live stories from PullPush API for r/${sub}...`);
      const pullpushUrl = `https://api.pullpush.io/reddit/search/submission/?subreddit=${sub}&size=30&sort=desc`;
      const response = await axios.get(pullpushUrl, { timeout: 10000 });
      const posts = response.data?.data;

      if (posts && Array.isArray(posts) && posts.length > 0) {
        const validPosts = posts.filter((post: any) => 
          post.is_self && 
          post.selftext && 
          post.selftext.length >= 100 && 
          !isStoryPosted(post.id)
        );

        if (validPosts.length > 0) {
          const selectedPost = validPosts[0];
          markStoryPosted(selectedPost.id);
          logger.success(`🎉 FETCHED NEW FUNNY REDDIT STORY (via PullPush): "${selectedPost.title}" by u/${selectedPost.author} (r/${selectedPost.subreddit})`);

          const fullRawText = `${selectedPost.title}\n\n${selectedPost.selftext || ''}`;
          const cleanedText = cleanStoryText(fullRawText);

          return {
            id: `reddit_${selectedPost.id}`,
            title: selectedPost.title,
            body: selectedPost.selftext || '',
            fullRawText,
            cleanedText,
            author: selectedPost.author || 'RedditUser',
            subreddit: selectedPost.subreddit || sub,
            url: `https://reddit.com${selectedPost.permalink || ''}`,
            score: selectedPost.score || 100
          };
        }
      }
    } catch (err: any) {
      lastError = err;
    }
  }

  throw new Error(`[FETCH FAILED] Could not fetch a fresh unread story online from Reddit (${lastError?.message}). Please check network connectivity or add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to your .env file.`);
}
