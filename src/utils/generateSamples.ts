import fs from 'node:fs';
import path from 'node:path';
// @ts-ignore
import { EdgeTTS } from 'node-edge-tts';
import { logger } from './logger.js';

const SAMPLE_TEXT = "Hey there! This is a preview of how this voice sounds for your storytelling videos.";

const VOICES = [
  { id: 'en-US-AnaNeural', name: 'sample_Ana.mp3', label: 'Ana (Energetic & Pitchy Female)' },
  { id: 'en-US-AvaNeural', name: 'sample_Ava.mp3', label: 'Ava (Upbeat & Bright Female)' },
  { id: 'en-US-JennyNeural', name: 'sample_Jenny.mp3', label: 'Jenny (Conversational & Popular Female)' },
  { id: 'en-US-SteffanNeural', name: 'sample_Steffan.mp3', label: 'Steffan (Youthful & Punchy Male)' },
  { id: 'en-US-ChristopherNeural', name: 'sample_Christopher.mp3', label: 'Christopher (Deep & Dramatic Male)' },
  { id: 'en-US-GuyNeural', name: 'sample_Guy.mp3', label: 'Guy (Narrative & Deep Male)' }
];

async function generatePreviews() {
  const outputDir = path.join(process.cwd(), 'output', 'samples');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  logger.info(`Generating ${VOICES.length} audio voice samples into ${outputDir}...`);

  for (const voice of VOICES) {
    const outputPath = path.join(outputDir, voice.name);
    logger.info(`Synthesizing sample for ${voice.label}...`);
    try {
      const tts = new EdgeTTS({
        voice: voice.id,
        lang: 'en-US',
        outputFormat: 'audio-24khz-48kbitrate-mono-mp3',
        pitch: voice.id === 'en-US-AnaNeural' ? '+18%' : '+0%',
        rate: '+10%'
      });

      await tts.ttsPromise(SAMPLE_TEXT, outputPath);
      logger.success(`Generated: ${outputPath}`);
    } catch (err: any) {
      logger.error(`Failed to generate ${voice.id}: ${err.message}`);
    }
  }

  logger.success(`🎉 All voice sample MP3s are ready in ${outputDir}!`);
}

generatePreviews();
