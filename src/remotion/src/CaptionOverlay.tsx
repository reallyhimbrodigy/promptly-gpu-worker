import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { createTikTokStyleCaptions } from "@remotion/captions";
import type { Caption } from "@remotion/captions";
import { CaptionPage, buildWordLookup } from "./CaptionPage";
import type { ProjectedWord, CaptionInput, StyleConfig } from "./types";
import { getStyleConfig } from "./styles/presets";

/**
 * Convert handler.py's ProjectedWord[] to @remotion/captions Caption[].
 */
function toRemotionCaptions(words: ProjectedWord[]): Caption[] {
  return words
    .filter((w) => typeof w.start === "number" && typeof w.end === "number" && !isNaN(w.start) && !isNaN(w.end) && w.end > w.start)
    .map((w, i) => ({
      text: (i === 0 ? "" : " ") + (w.punctuated_word || w.word),
      startMs: w.start * 1000,
      endMs: w.end * 1000,
      timestampMs: ((w.start + w.end) / 2) * 1000,
      confidence: 1.0,
    }));
}

/**
 * Build keyword set for fast lookup.
 */
function buildKeywordSet(words: ProjectedWord[], keywords: string[]): Set<string> {
  const kws = new Set(keywords.map((k) => k.toLowerCase().replace(/[.,!?;:'"\\]/g, "")));
  for (const w of words) {
    if (w._kw) {
      kws.add((w.word || "").toLowerCase().replace(/[.,!?;:'"\\]/g, ""));
    }
  }
  return kws;
}

/**
 * Main caption overlay composition.
 * Uses @remotion/captions for intelligent word grouping,
 * then renders each page with auto-sizing and word-by-word highlighting.
 */
export const CaptionOverlay: React.FC<{
  input: CaptionInput;
}> = ({ input }) => {
  const styleConfig = getStyleConfig(input.style);
  const keywordSet = buildKeywordSet(input.words, input.keywords);

  // Convert to @remotion/captions format and group into pages
  const captions = toRemotionCaptions(input.words);
  const { pages } = createTikTokStyleCaptions({
    captions,
    combineTokensWithinMilliseconds: 400, // Tight grouping = fewer words per page = bigger text
  });

  // Build O(1) word lookup for fast per-token matching
  const wordLookup = buildWordLookup(input.words);

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {pages.map((page, pi) => (
        <CaptionPage
          key={pi}
          page={page}
          style={styleConfig}
          keywordSet={keywordSet}
          words={input.words}
          wordLookup={wordLookup}
        />
      ))}
    </AbsoluteFill>
  );
};
