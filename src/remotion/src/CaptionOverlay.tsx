import React from "react";
import { AbsoluteFill } from "remotion";
import { CaptionGroup } from "./CaptionGroup";
import { FontLoader } from "./FontLoader";
import type { ProjectedWord, WordGroup, StyleConfig, CaptionInput } from "./types";
import { getStyleConfig } from "./styles/presets";

/**
 * Groups words into display groups of 2-4 words.
 * Matches the grouping logic from handler.py for consistency.
 */
function buildWordGroups(words: ProjectedWord[], maxPerGroup: number): WordGroup[] {
  const groups: WordGroup[] = [];
  let buf: ProjectedWord[] = [];

  for (let i = 0; i < words.length; i++) {
    const wd = words[i];
    buf.push(wd);

    const nxt = i + 1 < words.length ? words[i + 1] : null;
    const pause = nxt ? nxt.start - wd.end : 1.0;
    const endsSentence = /[.!?]$/.test(wd.word || "");

    if (!nxt || endsSentence || buf.length >= maxPerGroup || (buf.length >= 2 && pause > 0.15)) {
      groups.push({
        words: [...buf],
        start: buf[0].start,
        end: buf[buf.length - 1].end + 0.06,
      });
      buf = [];
    }
  }

  // Trim overlapping group ends
  for (let i = 0; i < groups.length - 1; i++) {
    groups[i].end = Math.min(groups[i].end, groups[i + 1].start - 0.01);
  }

  return groups;
}

/**
 * Build keyword set for fast lookup.
 */
function buildKeywordSet(words: ProjectedWord[], keywords: string[]): Set<string> {
  const kws = new Set(keywords.map((k) => k.toLowerCase().replace(/[.,!?;:'"\\]/g, "")));
  // Also mark words that are explicitly flagged as keywords
  for (const w of words) {
    if (w._kw) {
      kws.add((w.word || "").toLowerCase().replace(/[.,!?;:'"\\]/g, ""));
    }
  }
  return kws;
}

/**
 * Main caption overlay composition.
 * Renders transparent background with animated caption groups.
 */
export const CaptionOverlay: React.FC<{
  input: CaptionInput;
}> = ({ input }) => {
  const styleConfig = getStyleConfig(input.style);
  const groups = buildWordGroups(input.words, styleConfig.maxWordsPerGroup);
  const keywordSet = buildKeywordSet(input.words, input.keywords);

  // Track keyword color index across groups for consistent coloring
  let kwColorIndex = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {groups.map((group, gi) => {
        const startKwIdx = kwColorIndex;
        // Count keywords in this group to advance the color index
        for (const w of group.words) {
          const clean = (w.word || "").toLowerCase().replace(/[.,!?;:'"\\]/g, "");
          if (keywordSet.has(clean)) kwColorIndex++;
        }

        return (
          <CaptionGroup
            key={gi}
            group={group}
            style={styleConfig}
            keywordSet={keywordSet}
            kwColorIndex={startKwIdx}
          />
        );
      })}
    </AbsoluteFill>
  );
};
