/**
 * Shared keyword detection utility for caption styles.
 * All styles take keywords as props and use these helpers for matching.
 */

export function normalizeWord(text: string): string {
  return text.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

export function buildKeywordSet(words: string[]): Set<string> {
  return new Set(words.map((w) => normalizeWord(w)));
}

export function isKeyword(text: string, keywordSet: Set<string>): boolean {
  return keywordSet.has(normalizeWord(text));
}
