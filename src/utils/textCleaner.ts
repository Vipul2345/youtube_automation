/**
 * Clean text by stripping URLs, markdown formatting, emojis, and excessive whitespace.
 */
export function cleanStoryText(rawText: string): string {
  if (!rawText) return '';

  let text = rawText;

  // Remove URLs
  text = text.replace(/https?:\/\/\S+/gi, '');

  // Remove Reddit markdown spoiler tags >!text!< -> text
  text = text.replace(/>!([\s\S]*?)!</g, '$1');

  // Remove markdown headers (# Header)
  text = text.replace(/^#+\s+/gm, '');

  // Remove markdown blockquotes (> Quote)
  text = text.replace(/^>\s+/gm, '');

  // Remove markdown links [title](url) -> title
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');

  // Remove bold / italics / strikethrough (*text*, **text**, ~~text~~)
  text = text.replace(/(\*\*|__|\*|_|~~)(.*?)\1/g, '$2');

  // Remove edit notes often found in Reddit posts (e.g., "EDIT: thanks for gold")
  text = text.replace(/\bEDIT:.*$/gmi, '');
  text = text.replace(/\bUPDATE:.*$/gmi, '');

  // Normalize quotes and dashes
  text = text.replace(/[“”]/g, '"').replace(/[‘’]/g, "'");
  text = text.replace(/[—–]/g, ' - ');

  // Remove emojis and non-standard control characters
  text = text.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '');

  // Replace multiple spaces/newlines with a single clean space/newline structure
  text = text.replace(/[ \t]+/g, ' ');
  text = text.replace(/\n\s*\n+/g, '\n\n');
  text = text.trim();

  return text;
}

/**
 * Split text into logical sentences for TTS processing and chunk management.
 */
export function splitIntoSentences(text: string): string[] {
  if (!text) return [];

  // Match sentences ending in ., !, ?, or newlines
  const regex = /[^.!?\n]+[.!?\n]+/g;
  const matches = text.match(regex);

  if (!matches) {
    return [text.trim()];
  }

  return matches
    .map(s => s.trim())
    .filter(s => s.length > 0);
}
