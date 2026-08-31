import fs from 'node:fs';
import path from 'node:path';
import axios from 'axios';
// @ts-ignore
import { EdgeTTS } from 'node-edge-tts';
import ffmpeg from 'fluent-ffmpeg';
import ffmpegPath from '@ffmpeg-installer/ffmpeg';
import ffprobePath from '@ffprobe-installer/ffprobe';
import { PipelineOptions, CombinedAudioResult, TTSChunk } from '../types/index.js';
import { splitIntoSentences } from '../utils/textCleaner.js';
import { getCachedVoiceover, saveCachedVoiceover } from '../assets/cache.js';
import { logger } from '../utils/logger.js';

ffmpeg.setFfmpegPath(ffmpegPath.path);
ffmpeg.setFfprobePath(ffprobePath.path);

export function getAudioDuration(audioPath: string): Promise<number> {
  return new Promise((resolve, reject) => {
    ffmpeg.ffprobe(audioPath, (err, metadata) => {
      if (err) {
        try {
          const stats = fs.statSync(audioPath);
          const estimatedDuration = Math.max(1, stats.size / 16000);
          return resolve(estimatedDuration);
        } catch (statErr) {
          return reject(err);
        }
      }
      const duration = metadata.format.duration;
      if (duration && !isNaN(duration)) {
        resolve(duration);
      } else {
        resolve(1.5);
      }
    });
  });
}

export function groupSentencesIntoChunks(sentences: string[], maxChars: number = 400): string[] {
  const chunks: string[] = [];
  let currentChunk = '';

  for (const sentence of sentences) {
    if ((currentChunk + ' ' + sentence).length > maxChars) {
      if (currentChunk.trim()) {
        chunks.push(currentChunk.trim());
      }
      currentChunk = sentence;
    } else {
      currentChunk = currentChunk ? `${currentChunk} ${sentence}` : sentence;
    }
  }

  if (currentChunk.trim()) {
    chunks.push(currentChunk.trim());
  }

  return chunks;
}

export interface DialogueChunk {
  text: string;
  voice: string;
}

/**
 * Parses text into multi-character dialogue chunks.
 * Assigns Guy (en-US-GuyNeural) for male speakers/narrator, Jenny (en-US-JennyNeural) for female speakers,
 * Steffan (en-US-SteffanNeural) for secondary male, and Ava (en-US-AvaNeural) for secondary female characters.
 */
export function parseMultiCharacterDialogue(text: string, defaultVoice: string = 'en-US-GuyNeural'): DialogueChunk[] {
  const VOICE_PRIMARY_MALE = 'en-US-GuyNeural';
  const VOICE_PRIMARY_FEMALE = 'en-US-JennyNeural';
  const VOICE_SECONDARY_MALE = 'en-US-SteffanNeural';
  const VOICE_SECONDARY_FEMALE = 'en-US-AvaNeural';

  const lowerText = text.toLowerCase();
  const femaleNarratorIndicators = /\b(my husband|my boyfriend|my dad|my father|my ex-husband|my fiance)\b/;
  const maleNarratorIndicators = /\b(my wife|my girlfriend|my mom|my mother|my ex-wife|my fiancee)\b/;

  let narratorVoice = VOICE_PRIMARY_MALE;
  if (femaleNarratorIndicators.test(lowerText) && !maleNarratorIndicators.test(lowerText)) {
    narratorVoice = VOICE_PRIMARY_FEMALE;
  }

  if (defaultVoice && !['en-US-GuyNeural', 'en-US-JennyNeural', 'en-US-AnaNeural'].includes(defaultVoice)) {
    narratorVoice = defaultVoice;
  }

  // Regex to match quotes or dialogue lines: "..." or '...'
  const quoteRegex = /(["'][^"']+["']|[^"'\n]+)/g;
  const matches = text.match(quoteRegex);

  if (!matches || matches.length <= 1) {
    return [{ text, voice: narratorVoice }];
  }

  const chunks: DialogueChunk[] = [];

  for (let i = 0; i < matches.length; i++) {
    const rawChunk = matches[i].trim();
    if (!rawChunk) continue;

    const isQuote = /^["'].*["']$/.test(rawChunk);
    if (!isQuote) {
      chunks.push({ text: rawChunk, voice: narratorVoice });
      continue;
    }

    const prevContext = (i > 0 ? matches[i - 1] : '').toLowerCase();
    const nextContext = (i < matches.length - 1 ? matches[i + 1] : '').toLowerCase();
    const context = `${prevContext} ${nextContext}`;

    const isFemaleSpeaker = /\b(she|her|wife|girlfriend|mom|mother|sister|girl|woman|lady|waitress|daughter|mrs|ms)\b/.test(context);
    const isMaleSpeaker = /\b(he|his|him|husband|boyfriend|dad|father|brother|guy|man|cop|officer|manager|waiter|son|mr)\b/.test(context);

    let assignedVoice = narratorVoice;

    if (isFemaleSpeaker && !isMaleSpeaker) {
      assignedVoice = narratorVoice === VOICE_PRIMARY_FEMALE ? VOICE_SECONDARY_FEMALE : VOICE_PRIMARY_FEMALE;
    } else if (isMaleSpeaker && !isFemaleSpeaker) {
      assignedVoice = narratorVoice === VOICE_PRIMARY_MALE ? VOICE_SECONDARY_MALE : VOICE_PRIMARY_MALE;
    } else {
      assignedVoice = narratorVoice === VOICE_PRIMARY_MALE ? VOICE_PRIMARY_FEMALE : VOICE_PRIMARY_MALE;
    }

    chunks.push({ text: rawChunk, voice: assignedVoice });
  }

  // Merge consecutive chunks sharing the same voice
  const mergedChunks: DialogueChunk[] = [];
  for (const chunk of chunks) {
    if (mergedChunks.length > 0 && mergedChunks[mergedChunks.length - 1].voice === chunk.voice) {
      mergedChunks[mergedChunks.length - 1].text += ' ' + chunk.text;
    } else {
      mergedChunks.push({ ...chunk });
    }
  }

  return mergedChunks;
}

/**
 * Main TTS synthesis function supporting Multi-Character Voice Acting, Edge-TTS, OpenAI TTS, ElevenLabs, and content caching.
 */
export async function generateVoiceover(
  text: string,
  options: PipelineOptions
): Promise<CombinedAudioResult> {
  // Check cache first
  const cachedResult = getCachedVoiceover(text, options);
  if (cachedResult) {
    return cachedResult;
  }

  const tempDir = path.resolve(options.tempDir);
  if (!fs.existsSync(tempDir)) {
    fs.mkdirSync(tempDir, { recursive: true });
  }

  const dialogueChunks = parseMultiCharacterDialogue(text, options.voice);
  logger.info(`Multi-character voice parser identified ${dialogueChunks.length} character dialogue segments.`);

  const ttsChunks: TTSChunk[] = [];
  const chunkAudioFiles: string[] = [];

  for (let i = 0; i < dialogueChunks.length; i++) {
    const chunk = dialogueChunks[i];
    const chunkFileName = `dialogue_chunk_${i}_${Date.now()}.mp3`;
    const chunkFilePath = path.join(tempDir, chunkFileName);

    logger.info(`[VOICE ACTING] Synthesizing segment ${i + 1}/${dialogueChunks.length} using voice '${chunk.voice}'...`);

    if (options.tts === 'openai') {
      await generateOpenAITTS(chunk.text, chunkFilePath, options);
    } else if (options.tts === 'elevenlabs') {
      await generateElevenLabsTTS(chunk.text, chunkFilePath, options);
    } else {
      await generateEdgeTTS(chunk.text, chunkFilePath, chunk.voice);
    }

    const durationSeconds = await getAudioDuration(chunkFilePath);
    const wordCount = chunk.text.split(/\s+/).filter(Boolean).length;

    ttsChunks.push({
      text: chunk.text,
      audioPath: chunkFilePath,
      durationSeconds,
      wordCount
    });

    chunkAudioFiles.push(chunkFilePath);
  }

  const finalAudioPath = path.join(tempDir, `voiceover_${Date.now()}.mp3`);
  if (chunkAudioFiles.length === 1) {
    fs.copyFileSync(chunkAudioFiles[0], finalAudioPath);
  } else {
    logger.info(`Concatenating ${chunkAudioFiles.length} multi-character voice acting chunks...`);
    await concatenateAudioFiles(chunkAudioFiles, finalAudioPath);
  }

  const totalDurationSeconds = await getAudioDuration(finalAudioPath);
  logger.success(`Multi-character voiceover generated! Total duration: ${totalDurationSeconds.toFixed(2)}s`);

  const result: CombinedAudioResult = {
    audioPath: finalAudioPath,
    durationSeconds: totalDurationSeconds,
    chunks: ttsChunks
  };

  // Save to cache for future runs
  saveCachedVoiceover(text, result, options);

  return result;
}

async function generateEdgeTTS(text: string, outputPath: string, voice: string) {
  try {
    const ttsVoice = voice && voice !== 'en-US-ChristopherNeural' ? voice : 'en-US-AnaNeural';
    const tts = new EdgeTTS({
      voice: ttsVoice,
      lang: 'en-US',
      outputFormat: 'audio-24khz-48kbitrate-mono-mp3',
      pitch: '+15%',
      rate: '+50%' // 1.5x fast-paced reciting speed
    });

    await tts.ttsPromise(text, outputPath);
  } catch (err: any) {
    throw new Error(`Edge-TTS synthesis failed: ${err.message}`);
  }
}

async function generateOpenAITTS(text: string, outputPath: string, options: PipelineOptions) {
  const apiKey = options.apiKey || process.env.OPENAI_API_KEY;
  if (!apiKey) {
    throw new Error('OPENAI_API_KEY environment variable or --api-key is required for OpenAI TTS.');
  }

  const voice = options.voice || 'alloy';
  try {
    const response = await axios.post(
      'https://api.openai.com/v1/audio/speech',
      {
        model: 'tts-1',
        input: text,
        voice
      },
      {
        headers: {
          Authorization: `Bearer ${apiKey}`,
          'Content-Type': 'application/json'
        },
        responseType: 'arraybuffer'
      }
    );

    fs.writeFileSync(outputPath, Buffer.from(response.data));
  } catch (err: any) {
    throw new Error(`OpenAI TTS synthesis failed: ${err.response?.data?.error?.message || err.message}`);
  }
}

async function generateElevenLabsTTS(text: string, outputPath: string, options: PipelineOptions) {
  const apiKey = options.apiKey || process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    throw new Error('ELEVENLABS_API_KEY environment variable or --api-key is required for ElevenLabs TTS.');
  }

  const voiceId = options.voice || '21m00Tcm4TlvDq8ikWAM';
  try {
    const response = await axios.post(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
      {
        text,
        model_id: 'eleven_monolingual_v1',
        voice_settings: {
          stability: 0.5,
          similarity_boost: 0.75
        }
      },
      {
        headers: {
          'xi-api-key': apiKey,
          'Content-Type': 'application/json'
        },
        responseType: 'arraybuffer'
      }
    );

    fs.writeFileSync(outputPath, Buffer.from(response.data));
  } catch (err: any) {
    throw new Error(`ElevenLabs TTS synthesis failed: ${err.response?.data?.error?.message || err.message}`);
  }
}

function concatenateAudioFiles(inputFiles: string[], outputPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const command = ffmpeg();
    inputFiles.forEach(file => command.input(file));

    command
      .on('end', () => resolve())
      .on('error', err => reject(err))
      .mergeToFile(outputPath, path.dirname(outputPath));
  });
}
