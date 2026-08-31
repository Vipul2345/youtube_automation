/**
 * Expand English contractions and Reddit shortcuts for flawless human voice TTS narration.
 */
export function expandContractions(text: string): string {
  if (!text) return '';

  let t = text;

  const contractions: [RegExp, string][] = [
    // Contractions with apostrophes or normalized quotes
    [/\bI['’]ve\b/gi, 'I have'],
    [/\bI['’]m\b/gi, 'I am'],
    [/\bI['’]d\b/gi, 'I would'],
    [/\bI['’]ll\b/gi, 'I will'],

    [/\byou['’]re\b/gi, 'you are'],
    [/\byou['’]ve\b/gi, 'you have'],
    [/\byou['’]ll\b/gi, 'you will'],
    [/\byou['’]d\b/gi, 'you would'],

    [/\bhe['’]s\b/gi, 'he is'],
    [/\bshe['’]s\b/gi, 'she is'],
    [/\bit['’]s\b/gi, 'it is'],
    [/\bthat['’]s\b/gi, 'that is'],
    [/\bwhat['’]s\b/gi, 'what is'],
    [/\bthere['’]s\b/gi, 'there is'],
    [/\bhere['’]s\b/gi, 'here is'],
    [/\bwho['’]s\b/gi, 'who is'],

    [/\bwe['’]re\b/gi, 'we are'],
    [/\bwe['’]ve\b/gi, 'we have'],
    [/\bwe['’]ll\b/gi, 'we will'],
    [/\bthey['’]re\b/gi, 'they are'],
    [/\bthey['’]ve\b/gi, 'they have'],
    [/\bthey['’]ll\b/gi, 'they will'],

    // Negative contractions
    [/\bdon['’]?t\b/gi, 'do not'],
    [/\bdoesn['’]?t\b/gi, 'does not'],
    [/\bdidn['’]?t\b/gi, 'did not'],
    [/\bcan['’]?t\b/gi, 'cannot'],
    [/\bcouldn['’]?t\b/gi, 'could not'],
    [/\bwon['’]?t\b/gi, 'will not'],
    [/\bwouldn['’]?t\b/gi, 'would not'],
    [/\bshouldn['’]?t\b/gi, 'should not'],
    [/\bisn['’]?t\b/gi, 'is not'],
    [/\baren['’]?t\b/gi, 'are not'],
    [/\bwasn['’]?t\b/gi, 'was not'],
    [/\bweren['’]?t\b/gi, 'were not'],
    [/\bhaven['’]?t\b/gi, 'have not'],
    [/\bhasn['’]?t\b/gi, 'has not'],
    [/\bhadn['’]?t\b/gi, 'had not'],

    // Common Reddit & Internet Shortcuts
    [/\bAITA\b/g, 'Am I the asshole'],
    [/\bWIBTA\b/g, 'Would I be the asshole'],
    [/\bTIFU\b/g, 'Today I messed up'],
    [/\bMIL\b/g, 'mother in law'],
    [/\bFIL\b/g, 'father in law'],
    [/\bSIL\b/g, 'sister in law'],
    [/\bBIL\b/g, 'brother in law'],
    [/\bSO\b/g, 'significant other'],
    [/\bBF\b/g, 'boyfriend'],
    [/\bGF\b/g, 'girlfriend'],
    [/\bOP\b/g, 'original poster'],
    [/\bidk\b/gi, 'I do not know'],
    [/\bimo\b/gi, 'in my opinion'],
    [/\bimho\b/gi, 'in my honest opinion'],
    [/\btbh\b/gi, 'to be honest'],
    [/\btbf\b/gi, 'to be fair'],
    [/\bw\/\b/gi, 'with '],
    [/\bw\/o\b/gi, 'without '],
    [/\bb\/c\b/gi, 'because '],
    [/\bfyi\b/gi, 'for your information'],
    [/\blet['’]s\b/gi, 'let us'],
    [/\betc\.?\b/gi, 'and so on']
  ];

  for (const [regex, replacement] of contractions) {
    t = t.replace(regex, replacement);
  }

  // Universal 's rule: Any word with 's (e.g. person's -> person is, car's -> car is, it's -> it is)
  t = t.replace(/\b([A-Za-z0-9]+)['’]s\b/gi, '$1 is');

  return t;
}

/**
 * Ultra-Clean human narrative text processor.
 * Decodes HTML entities, strips HTML comments (<!-- -->), removes HTML tags (<div class="md">),
 * expands contractions (I've -> I have), strips Reddit RSS metadata, comment IDs, hashtags, URLs, and markdown junk.
 */
export function cleanStoryText(rawText: string): string {
  if (!rawText) return '';

  let text = rawText;

  // Step 1: Decode HTML entities repeatedly (handles double-encoded entities like &amp;lt;)
  for (let i = 0; i < 3; i++) {
    text = text.replace(/&amp;/g, '&')
               .replace(/&lt;/gi, '<')
               .replace(/&gt;/gi, '>')
               .replace(/&quot;/gi, '"')
               .replace(/&#39;/gi, "'")
               .replace(/&nbsp;/gi, ' ');
  }

  // Step 2: Strip HTML comments completely (e.g. <!-- SCOFF -->)
  text = text.replace(/<!--[\s\S]*?-->/gi, ' ');

  // Step 3: Strip all HTML tags (e.g. <div class="md"><p> ... </p></div>)
  text = text.replace(/<[^>]+>/g, ' ');

  // Step 4: Expand contractions & internet shortcuts for flawless voice acting
  text = expandContractions(text);

  // Step 5: Remove Reddit RSS / metadata boilerplate
  text = text.replace(/submitted by\s+\/u\/\S+/gi, ' ');
  text = text.replace(/to\s+\/r\/\S+/gi, ' ');
  text = text.replace(/\[link\]/gi, ' ');
  text = text.replace(/\[comments\]/gi, ' ');
  text = text.replace(/\[\+\]/g, ' ');
  text = text.replace(/t3_[a-z0-9]+/gi, ' ');
  text = text.replace(/submitted\s+\d+\s+hours?\s+ago.*/gi, ' ');
  text = text.replace(/view\s+entire\s+discussion.*/gi, ' ');

  // Step 6: Remove URLs
  text = text.replace(/https?:\/\/\S+/gi, ' ');
  text = text.replace(/www\.\S+/gi, ' ');

  // Step 7: Remove Reddit user/sub tags (/u/name, r/sub)
  text = text.replace(/\/?[ur]\/[A-Za-z0-9_]+/g, ' ');

  // Step 8: Remove hashtags (#tag)
  text = text.replace(/#\w+/g, ' ');

  // Step 9: Remove markdown formatting (headers, quotes, bold, italics, spoilers)
  text = text.replace(/>!([\s\S]*?)!</g, '$1');
  text = text.replace(/^#+\s+/gm, ' ');
  text = text.replace(/^>\s+/gm, ' ');
  text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
  text = text.replace(/(\*\*|__|\*|_|~~)(.*?)\1/g, '$2');

  // Step 10: Remove Edit/Update/TLDR lines
  text = text.replace(/\bEDIT:.*$/gmi, ' ');
  text = text.replace(/\bUPDATE:.*$/gmi, ' ');
  text = text.replace(/\bTL;?DR:?.*$/gmi, ' ');

  // Step 11: Clean any orphan brackets/quotes or non-word symbols at the beginning/end
  text = text.replace(/^[<>/=]+\s*/, '');

  // Step 12: Normalize quotes, dashes, and whitespace
  text = text.replace(/[“”]/g, '"').replace(/[‘’]/g, "'");
  text = text.replace(/[—–]/g, ' - ');
  text = text.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, ' ');

  // Collapse whitespace & clean lines
  text = text.replace(/[ \t]+/g, ' ');
  text = text.replace(/\n\s*\n+/g, '\n\n');
  text = text.trim();

  return text;
}

/**
 * Split text into natural spoken sentences.
 */
export function splitIntoSentences(text: string): string[] {
  if (!text) return [];

  const regex = /[^.!?\n]+[.!?\n]+/g;
  const matches = text.match(regex);

  if (!matches) {
    return [text.trim()];
  }

  return matches
    .map(s => s.trim())
    .filter(s => s.length > 5);
}
