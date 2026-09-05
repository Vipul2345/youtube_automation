import fs from 'node:fs';
import path from 'node:path';
import { CombinedAudioResult, CaptionItem, AspectRatio, CaptionWord } from '../types/index.js';
import { logger } from '../utils/logger.js';

export interface SubtitleFiles {
  srtPath: string;
  assPath: string;
  captions: CaptionItem[];
}

export function formatSRTTimestamp(seconds: number): string {
  const pad = (n: number, z: number = 2) => String(n).padStart(z, '0');
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const millis = Math.floor((seconds % 1) * 1000);

  return `${pad(hrs)}:${pad(mins)}:${pad(secs)},${pad(millis, 3)}`;
}

export function formatASSTimestamp(seconds: number): string {
  const pad = (n: number, z: number = 2) => String(n).padStart(z, '0');
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  const cs = Math.floor(((seconds % 1) * 100));

  return `${hrs}:${pad(mins)}:${pad(secs)}.${pad(cs, 2)}`;
}

function calculateGroupWeight(words: string[]): number {
  let weight = 0;
  for (const word of words) {
    weight += word.length;
    if (/[,.;:!?]/.test(word)) {
      if (/[,.;]/.test(word)) {
        weight += 4;
      } else {
        weight += 8;
      }
    }
  }
  return Math.max(1, weight);
}

/**
 * Generate 100% audio-synchronized caption items with normalized chunk timing.
 */
export function generateCaptionItems(
  combinedAudio: CombinedAudioResult,
  wordsPerCaption: number = 2
): CaptionItem[] {
  const captions: CaptionItem[] = [];
  let chunkStartTime = 0;
  let captionIndex = 1;

  for (const chunk of combinedAudio.chunks) {
    const text = chunk.text;
    const words = text.split(/\s+/).filter(Boolean);

    if (words.length === 0) {
      chunkStartTime += chunk.durationSeconds;
      continue;
    }

    const chunkDuration = chunk.durationSeconds;

    const wordGroups: string[][] = [];
    for (let i = 0; i < words.length; i += wordsPerCaption) {
      wordGroups.push(words.slice(i, i + wordsPerCaption));
    }

    const groupWeights = wordGroups.map(group => calculateGroupWeight(group));
    const totalChunkWeight = groupWeights.reduce((acc, w) => acc + w, 0) || 1;

    let groupOffsetInChunk = 0;

    for (let i = 0; i < wordGroups.length; i++) {
      const group = wordGroups[i];
      const groupWeight = groupWeights[i];
      const groupText = group.join(' ');

      const groupDuration = (groupWeight / totalChunkWeight) * chunkDuration;
      const startTimeSec = chunkStartTime + groupOffsetInChunk;
      const endTimeSec = startTimeSec + groupDuration;

      const wordWeights = group.map(w => calculateGroupWeight([w]));
      const totalGroupWordWeight = wordWeights.reduce((acc, w) => acc + w, 0) || 1;

      const groupWords: CaptionWord[] = [];
      let wordStartOffset = startTimeSec;

      for (let j = 0; j < group.length; j++) {
        const word = group[j];
        const wWeight = wordWeights[j];
        let wordDuration = (wWeight / totalGroupWordWeight) * groupDuration;
        if (wordDuration < 0.25) {
          wordDuration = 0.25;
        }
        const wordEndOffset = wordStartOffset + wordDuration;

        groupWords.push({
          word,
          startTimeSec: wordStartOffset,
          endTimeSec: wordEndOffset
        });

        wordStartOffset = wordEndOffset;
      }

      captions.push({
        index: captionIndex++,
        startTimeSec,
        endTimeSec,
        formattedStartSRT: formatSRTTimestamp(startTimeSec),
        formattedEndSRT: formatSRTTimestamp(endTimeSec),
        formattedStartASS: formatASSTimestamp(startTimeSec),
        formattedEndASS: formatASSTimestamp(endTimeSec),
        text: groupText,
        words: groupWords
      });

      groupOffsetInChunk += groupDuration;
    }

    chunkStartTime += chunkDuration;
  }

  if (captions.length > 0 && combinedAudio.durationSeconds > 0) {
    captions[captions.length - 1].endTimeSec = combinedAudio.durationSeconds;
    captions[captions.length - 1].formattedEndSRT = formatSRTTimestamp(combinedAudio.durationSeconds);
    captions[captions.length - 1].formattedEndASS = formatASSTimestamp(combinedAudio.durationSeconds);
  }

  return captions;
}

export function createSRTContent(captions: CaptionItem[]): string {
  return captions
    .map(c => `${c.index}\n${c.formattedStartSRT} --> ${c.formattedEndSRT}\n${c.text}\n`)
    .join('\n');
}

/**
 * Premium Alex Hormozi Style Animated ASS Subtitle & Reddit Card Hook Generator.
 */
export function createASSContent(
  captions: CaptionItem[], 
  ratio: AspectRatio,
  storyMeta?: { title?: string; author?: string; subreddit?: string }
): string {
  const isVertical = ratio === '9:16';
  const alignment = 2; // 2 = Bottom-center alignment
  const fontSize = isVertical ? 64 : 42;
  const marginV = isVertical ? 280 : 50;

  const subName = storyMeta?.subreddit ? (storyMeta.subreddit.startsWith('r/') ? storyMeta.subreddit : `r/${storyMeta.subreddit}`) : 'r/stories';
  const authName = storyMeta?.author ? (storyMeta.author.startsWith('u/') ? storyMeta.author : `u/${storyMeta.author}`) : 'u/RedditUser';
  const cleanCardTitle = storyMeta?.title ? storyMeta.title.replace(/\\/g, '/').replace(/{/g, '(').replace(/}/g, ')') : 'Reddit Story';

  const HOOK_CARD_DURATION = 3.50;

  const header = `[Script Info]
Title: High Impact Hormozi Captions & Reddit Hook Card
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: ${isVertical ? 1080 : 1920}
PlayResY: ${isVertical ? 1920 : 1080}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,${fontSize},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,4,${alignment},30,30,${marginV},1
Style: Watermark,Arial Black,26,&H00FFFFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,8,20,20,40,1
Style: RedditCard,Arial Black,34,&H00FFFFFF,&H0000FFFF,&H00000000,&HE01A1A1B,-1,0,0,0,100,100,1,0,3,12,6,5,40,40,900,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:10:00.00,Watermark,,0,0,0,,🤖 AI Created
Dialogue: 1,0:00:00.00,0:00:03.50,RedditCard,,0,0,0,,{\\fad(150,250)}${subName} • ${authName}\\N${cleanCardTitle}

`;

  const dialogueLines: string[] = [];

  for (const caption of captions) {
    if (caption.words && caption.words.length > 0 && isVertical) {
      for (let i = 0; i < caption.words.length; i++) {
        const activeWordObj = caption.words[i];
        
        // Suppress word captions while Reddit Title Card is displayed
        if (activeWordObj.endTimeSec <= HOOK_CARD_DURATION) {
          continue;
        }

        const effectiveStart = Math.max(HOOK_CARD_DURATION, activeWordObj.startTimeSec);
        const effectiveEnd = Math.max(effectiveStart + 0.25, activeWordObj.endTimeSec);

        const startASS = formatASSTimestamp(effectiveStart);
        const endASS = formatASSTimestamp(effectiveEnd);

        const formattedWords = caption.words.map((w, idx) => {
          const upperWord = w.word.toUpperCase();
          if (idx === i) {
            return `{\\c&H0000FFFF\\fscx115\\fscy115}${upperWord}{\\r}`;
          } else {
            return upperWord;
          }
        }).join(' ');

        dialogueLines.push(`Dialogue: 0,${startASS},${endASS},Default,,0,0,0,,${formattedWords}`);
      }
    } else {
      if (caption.endTimeSec <= HOOK_CARD_DURATION) {
        continue;
      }
      const effectiveStart = Math.max(HOOK_CARD_DURATION, caption.startTimeSec);
      const startASS = formatASSTimestamp(effectiveStart);
      const endASS = formatASSTimestamp(Math.max(effectiveStart + 0.25, caption.endTimeSec));

      const displayText = isVertical ? caption.text.toUpperCase() : caption.text;
      dialogueLines.push(`Dialogue: 0,${startASS},${endASS},Default,,0,0,0,,${displayText}`);
    }
  }

  return header + dialogueLines.join('\n');
}

export function generateCaptions(
  combinedAudio: CombinedAudioResult,
  outputDir: string,
  ratio: AspectRatio,
  storyMeta?: { title?: string; author?: string; subreddit?: string }
): SubtitleFiles {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const wordsPerCaption = ratio === '9:16' ? 3 : 5;
  const captions = generateCaptionItems(combinedAudio, wordsPerCaption);

  const srtContent = createSRTContent(captions);
  const assContent = createASSContent(captions, ratio, storyMeta);

  const srtPath = path.join(outputDir, `captions_${Date.now()}.srt`);
  const assPath = path.join(outputDir, `captions_${Date.now()}.ass`);

  fs.writeFileSync(srtPath, srtContent, 'utf-8');
  fs.writeFileSync(assPath, assContent, 'utf-8');

  logger.success(`High-impact styled ASS captions generated (${captions.length} phrases).`);

  return {
    srtPath,
    assPath,
    captions
  };
}
