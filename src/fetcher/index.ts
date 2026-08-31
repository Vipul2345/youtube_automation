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

export async function fetchRedditStory(
  subreddit: string,
  timeframe: string = 'week',
  index: number = 0
): Promise<StoryContent> {
  const subreddits = [subreddit, 'AskReddit', 'tifu', 'confession', 'AmItheAsshole', 'stories'];
  let lastError: Error | null = null;

  for (const sub of subreddits) {
    const endpoints = [
      `https://www.reddit.com/r/${sub}/top.json?limit=30&t=${timeframe}`,
      `https://old.reddit.com/r/${sub}/top.json?limit=30&t=${timeframe}`
    ];

    logger.info(`Fetching top stories from r/${sub} (timeframe: ${timeframe})...`);

    for (const url of endpoints) {
      try {
        const response = await axios.get(url, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9'
          },
          timeout: 10000
        });

        const posts = response.data?.data?.children;
        if (!posts || !Array.isArray(posts) || posts.length === 0) {
          continue;
        }

        const validPosts = posts
          .map((child: any) => child.data as RedditPostData)
          .filter((post: RedditPostData) => post.is_self && post.selftext && post.selftext.length > 50 && !isStoryPosted(post.id));

        if (validPosts.length === 0) {
          continue;
        }

        const postIndex = Math.min(Math.max(0, index), validPosts.length - 1);
        const selectedPost = validPosts[postIndex] || validPosts[0];

        markStoryPosted(selectedPost.id);
        logger.success(`Fetched fresh new post: "${selectedPost.title}" by u/${selectedPost.author} (Score: ${selectedPost.score})`);

        const fullRawText = `${selectedPost.title}\n\n${selectedPost.selftext || ''}`;
        const cleanedText = cleanStoryText(fullRawText);

        return {
          id: `reddit_${selectedPost.id}`,
          title: selectedPost.title,
          body: selectedPost.selftext || '',
          fullRawText,
          cleanedText,
          author: selectedPost.author,
          subreddit: selectedPost.subreddit,
          url: `https://reddit.com${selectedPost.url}`,
          score: selectedPost.score
        };
      } catch (err: any) {
        lastError = err;
      }
    }
  }

  logger.warn(`Reddit API query blocked or unavailable (${lastError?.message}). Falling back to local sample story.`);
  return fetchStoryById('tifu_mountain_spirit', path.join(process.cwd(), 'content', 'stories'));
}
