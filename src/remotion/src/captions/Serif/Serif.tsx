import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { SpringConfig } from "remotion";
import type { TikTokPage, TikTokToken } from "../shared/types";
import type { SerifProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";
import { textOutline } from "../shared/textOutline";

// 8-direction text-shadow stand-in for `WebkitTextStroke: 0.75px`. Stroke
// rasterizes as a single geometric outline that breaks at letter apexes
// under the entrance `transform: scale` mid-spring; 8-direction shadow
// is multi-sampled and survives any transform.
const STROKE_OUTLINE = textOutline(0.75, "rgba(0,0,0,0.6)");

// Smooth deceleration, zero bounce — editorial feel
const SPRING_EDITORIAL: SpringConfig = {
  damping: 28,
  mass: 1.2,
  stiffness: 100,
  overshootClamping: true,
};

/* ─── Word ─── */

const SerifWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  isKw: boolean;
  textColor: string;
  keywordColor: string;
  bodyFontSize: number;
  keywordSizeMultiplier: number;
  letterSpacing: string;
  keywordLetterSpacing: string;
  textShadow: string;
  scaleFrom: number;
}> = ({
  token,
  pageStartMs,
  isKw,
  textColor,
  keywordColor,
  bodyFontSize,
  keywordSizeMultiplier,
  letterSpacing,
  keywordLetterSpacing,
  textShadow,
  scaleFrom,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const activateFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const elapsed = frame - activateFrame;
  const hasAppeared = elapsed >= 0;

  const entranceSpring = hasAppeared
    ? spring({ fps, frame: elapsed, config: SPRING_EDITORIAL })
    : 0;

  const scale = interpolate(entranceSpring, [0, 1], [scaleFrom, 1], {
    extrapolateRight: "clamp",
  });

  const opacity = interpolate(entranceSpring, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Keywords: subtle glow + dark backing for readability
  const glowPulse = isKw && hasAppeared
    ? Math.sin(frame * 0.1) * 0.08 + 0.92
    : 0;

  const fontSize = isKw
    ? Math.round(bodyFontSize * keywordSizeMultiplier)
    : bodyFontSize;

  // Dark shadow for contrast against video, gentle blue glow on top
  const kwShadow = isKw
    ? `0 2px 10px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.5), 0 0 12px rgba(90,159,212,${(glowPulse * 0.35).toFixed(2)}), 0 0 30px rgba(90,159,212,${(glowPulse * 0.15).toFixed(2)})`
    : textShadow;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: isKw ? CAPTION_FONTS.dmSerifDisplay : CAPTION_FONTS.dmSans,
        fontSize,
        fontWeight: isKw ? 400 : 400,
        fontStyle: isKw ? "italic" : "normal",
        color: isKw ? keywordColor : textColor,
        letterSpacing: isKw ? keywordLetterSpacing : letterSpacing,
        lineHeight: 1.15,
        textShadow: `${kwShadow}, ${STROKE_OUTLINE}`,
        whiteSpace: "nowrap",
        transform: `scale(${scale})`,
        transformOrigin: "center bottom",
        opacity,
      }}
    >
      {token.text}
    </span>
  );
};

/* ─── Page ─── */

const SerifPage: React.FC<{
  page: TikTokPage;
  lines: TikTokToken[][];
  kwSet: Set<string>;
  textColor: string;
  keywordColor: string;
  bodyFontSize: number;
  keywordSizeMultiplier: number;
  letterSpacing: string;
  keywordLetterSpacing: string;
  textShadow: string;
  scaleFrom: number;
  lineGap: number;
  wordGap: number;
  maxWidth: number;
  positionStyle: React.CSSProperties;
}> = ({
  page,
  lines,
  kwSet,
  lineGap,
  wordGap,
  maxWidth,
  positionStyle,
  ...wordProps
}) => {
  // Hard cut on/off — no fade. Captions snap to the spoken word.
  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        ...positionStyle,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth,
          width: "100%",
          gap: lineGap,
        }}
      >
        {lines.map((lineTokens, lineIdx) => (
          <div
            key={lineIdx}
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "center",
              gap: wordGap,
            }}
          >
            {lineTokens.map((token, idx) => (
              <SerifWord
                key={idx}
                token={token}
                pageStartMs={page.startMs}
                isKw={isKeyword(token.text, kwSet)}
                {...wordProps}
              />
            ))}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ─── Main Component ─── */

export const Serif: React.FC<SerifProps> = ({
  pages,
  keywords = [],
  textColor = "#F0EEE9",
  keywordColor = "#5A9FD4",
  bodyFontSize = 62,
  keywordSizeMultiplier = 1.35,
  position = "bottom",
  maxWordsPerLine = 4,
  lineGap = 14,
  wordGap = 16,
  letterSpacing = "0.01em",
  keywordLetterSpacing = "-0.02em",
  textShadow = "0 2px 12px rgba(0,0,0,0.6)",
  scaleFrom = 0.96,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const kwSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position);

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        const lines: TikTokToken[][] = [];
        for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
          lines.push(page.tokens.slice(i, i + maxWordsPerLine));
        }

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
            premountFor={10}
          >
            <SerifPage
              page={page}
              lines={lines}
              kwSet={kwSet}
              textColor={textColor}
              keywordColor={keywordColor}
              bodyFontSize={bodyFontSize}
              keywordSizeMultiplier={keywordSizeMultiplier}
              letterSpacing={letterSpacing}
              keywordLetterSpacing={keywordLetterSpacing}
              textShadow={textShadow}
              scaleFrom={scaleFrom}
              lineGap={lineGap}
              wordGap={wordGap}
              maxWidth={maxWidth}
              positionStyle={positionStyle}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
