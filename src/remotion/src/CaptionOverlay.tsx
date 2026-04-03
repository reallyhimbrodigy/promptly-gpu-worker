import React, { useMemo } from "react";
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
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  // Memoize expensive computations that don't change between frames
  const styleConfig = useMemo(() => getStyleConfig(input.style), [input.style]);
  const keywordSet = useMemo(() => buildKeywordSet(input.words, input.keywords), [input.words, input.keywords]);
  const captions = useMemo(() => toRemotionCaptions(input.words), [input.words]);
  const pages = useMemo(() => {
    const result = createTikTokStyleCaptions({
      captions,
      combineTokensWithinMilliseconds: 400,
    });
    return result.pages;
  }, [captions]);
  const wordLookup = useMemo(() => buildWordLookup(input.words), [input.words]);

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {pages.map((page, pi) => {
        // Skip pages far from current time — avoids mounting ~30 unused React
        // components per frame, each with hooks, springs, and DOM output.
        const pageStart = page.startMs / 1000;
        const lastToken = page.tokens[page.tokens.length - 1];
        const pageEnd = lastToken ? lastToken.toMs / 1000 : pageStart + 0.5;
        if (t < pageStart - 0.5 || t > pageEnd + 0.5) return null;

        return (
          <CaptionPage
            key={pi}
            page={page}
            style={styleConfig}
            keywordSet={keywordSet}
            words={input.words}
            wordLookup={wordLookup}
          />
        );
      })}
    </AbsoluteFill>
  );
};
