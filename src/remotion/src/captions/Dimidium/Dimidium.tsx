import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokPage, TikTokToken } from "../shared/types";
import type { DimidiumProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { CAPTION_PADDING } from "../shared/captionPosition";

// Deterministic stagger offsets that feel organic
const STAGGER_OFFSETS = [-60, 40, 80, -20, 60, -40, 20, -80];

function getWordScale(text: string, isHighlight: boolean, wordIndex: number): number {
  if (!isHighlight) return 0.78;
  // Alternate highlight words between normal and big
  return wordIndex % 2 === 0 ? 1.55 : 1;
}

/* ─── Word Component ─── */

const DimidiumWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  fontSize: number;
  color: string;
  isHighlight: boolean;
  highlightColor: string;
  wordIndex: number;
}> = ({ token, pageStartMs, fontSize, color, isHighlight, highlightColor, wordIndex }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const wordScale = getWordScale(token.text, isHighlight, wordIndex);
  const wordFontSize = fontSize * wordScale;

  const activateFrame = Math.round(((token.fromMs - pageStartMs) / 1000) * fps);
  const elapsed = frame - activateFrame;
  const hasAppeared = elapsed >= 0;

  const fadeInFrames = 3;
  const opacity = hasAppeared
    ? interpolate(elapsed, [0, fadeInFrames], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  return (
    <div style={{ display: "inline-block", position: "relative", marginRight: 14, overflow: "visible" }}>
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          fontFamily: CAPTION_FONTS.montserrat,
          fontWeight: 800,
          fontSize: wordFontSize,
          letterSpacing: "-0.03em",
          lineHeight: 1.05,
          whiteSpace: "nowrap",
          color: "#000000",
          filter: "blur(4px)",
          textShadow: "0 0 20px #000, 0 0 40px #000, 0 0 60px #000",
          opacity,
          pointerEvents: "none",
        }}
      >
        {token.text}
      </span>
      <span
        style={{
          display: "inline-block",
          position: "relative",
          fontFamily: CAPTION_FONTS.montserrat,
          fontWeight: 800,
          fontSize: wordFontSize,
          color: isHighlight ? highlightColor : color,
          letterSpacing: "-0.03em",
          lineHeight: 1.05,
          whiteSpace: "nowrap",
          textShadow: "0 0 4px rgba(0,0,0,0.6), 0 2px 3px rgba(0,0,0,0.4)",
          WebkitTextStroke: "14px #000000",
          paintOrder: "stroke fill",
          opacity,
        }}
      >
        {token.text}
      </span>
    </div>
  );
};

/* ─── Page Component ─── */

const DimidiumPage: React.FC<{
  page: TikTokPage;
  fontSize: number;
  color: string;
  highlightColor: string;
  highlightSet: Set<string>;
  maxWordsPerLine: number;
  lineGap: number;
  globalLineOffset: number;
}> = ({ page, fontSize, color, highlightColor, highlightSet, maxWordsPerLine, lineGap, globalLineOffset }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pageLocalMs = (frame / fps) * 1000;

  const t = frame / fps;
  const floatY = Math.sin(t * 1.2) * 14 + Math.sin(t * 1.8) * 7;

  const fadeOut = interpolate(
    pageLocalMs,
    [page.durationMs - 120, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const lines: TikTokToken[][] = [];
  for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
    lines.push(page.tokens.slice(i, i + maxWordsPerLine));
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: lineGap,
        opacity: fadeOut,
        transform: `translateY(${floatY.toFixed(2)}px)`,
        willChange: "transform",
      }}
    >
      {lines.map((lineTokens, lineIdx) => {
        const offset = STAGGER_OFFSETS[(globalLineOffset + lineIdx) % STAGGER_OFFSETS.length];
        return (
          <div
            key={lineIdx}
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "baseline",
              marginLeft: offset + 80,
            }}
          >
            {lineTokens.map((token, tokenIdx) => (
              <DimidiumWord
                key={tokenIdx}
                token={token}
                pageStartMs={page.startMs}
                fontSize={fontSize}
                color={color}
                isHighlight={highlightSet.has(token.text.toLowerCase())}
                highlightColor={highlightColor}
                wordIndex={tokenIdx}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
};

/* ─── Main Component ─── */

export const Dimidium: React.FC<DimidiumProps> = ({
  pages,
  fontSize = 82,
  position = "bottom",
  color = "#FFFFFF",
  highlightColor = "#E8D44D",
  highlightWords = [],
  maxWordsPerLine = 3,
  lineGap = 8,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

  const highlightSet = useMemo(
    () => new Set(highlightWords.map((w) => w.toLowerCase())),
    [highlightWords],
  );

  // Track cumulative line count for consistent stagger across pages
  let cumulativeLines = 0;

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        const lineCount = Math.ceil(page.tokens.length / maxWordsPerLine);
        const globalLineOffset = cumulativeLines;
        cumulativeLines += lineCount;

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
            premountFor={10}
          >
            <AbsoluteFill
              style={{
                justifyContent: position === "top" ? "flex-start" : position === "center" ? "center" : "flex-end",
                alignItems: "flex-start",
                ...(position === "top"
                  ? { paddingTop: CAPTION_PADDING.top, paddingLeft: CAPTION_PADDING.sides - 80, paddingRight: CAPTION_PADDING.sides }
                  : position === "center"
                    ? { paddingLeft: CAPTION_PADDING.sides - 80, paddingRight: CAPTION_PADDING.sides }
                    : { paddingBottom: CAPTION_PADDING.bottomSafe, paddingLeft: CAPTION_PADDING.sidesSafe - 80, paddingRight: CAPTION_PADDING.sides }),
              }}
            >
              <div style={{ maxWidth, width: "100%" }}>
              <DimidiumPage
                page={page}
                fontSize={fontSize}
                color={color}
                highlightColor={highlightColor}
                highlightSet={highlightSet}
                maxWordsPerLine={maxWordsPerLine}
                lineGap={lineGap}
                globalLineOffset={globalLineOffset}
              />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
