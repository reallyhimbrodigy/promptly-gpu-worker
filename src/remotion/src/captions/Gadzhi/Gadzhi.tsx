import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import type { TikTokToken } from "../shared/types";
import type { GadzhiStyleProps } from "./types";
import { msToFrames, getCurrentTimeMs } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { buildKeywordSet, isKeyword } from "../shared/keywords";
import { CAPTION_PADDING } from "../shared/captionPosition";

const SHADOW = "0 2px 8px rgba(0,0,0,0.5), 0 4px 20px rgba(0,0,0,0.3)";
const SLIDE_FRAMES_NORMAL = 10;
const SLIDE_FRAMES_KEYWORD = 16;
const SLIDE_DISTANCE_NORMAL = 35;
const SLIDE_DISTANCE_KEYWORD = 50;

const GadzhiStylePage: React.FC<{
  tokens: TikTokToken[];
  pageStartMs: number;
  fontSize: number;
  textColor: string;
  highlightColor: string;
  keywordSet: Set<string>;
  maxWordsPerLine: number;
  wordGap: number;
}> = ({
  tokens,
  pageStartMs,
  fontSize,
  textColor,
  highlightColor,
  keywordSet,
  maxWordsPerLine,
  wordGap,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTimeMs = getCurrentTimeMs(frame, fps) + pageStartMs;

  const lines: TikTokToken[][] = [];
  for (let i = 0; i < tokens.length; i += maxWordsPerLine) {
    lines.push(tokens.slice(i, i + maxWordsPerLine));
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 4,
      }}
    >
      {lines.map((lineTokens, lineIdx) => (
        <div
          key={lineIdx}
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: wordGap,
          }}
        >
          {lineTokens.map((token, wi) => {
            const isSpoken = currentTimeMs >= token.fromMs;
            const isKw = isKeyword(token.text, keywordSet);
            const finalColor = isKw ? highlightColor : textColor;

            const slideDuration = isKw ? SLIDE_FRAMES_KEYWORD : SLIDE_FRAMES_NORMAL;
            const slideDist = isKw ? SLIDE_DISTANCE_KEYWORD : SLIDE_DISTANCE_NORMAL;
            const wordEntryFrame = msToFrames(token.fromMs - pageStartMs, fps);
            const elapsed = frame - wordEntryFrame;

            const slideProgress = interpolate(elapsed, [0, slideDuration], [0, 1], {
              easing: Easing.out(Easing.cubic),
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            const yOffset = interpolate(slideProgress, [0, 1], [slideDist, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            const opacity = interpolate(slideProgress, [0, 0.4], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            const colorProgress = interpolate(slideProgress, [0, 1], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const color = colorProgress >= 1
              ? finalColor
              : `color-mix(in srgb, #555555 ${Math.round((1 - colorProgress) * 100)}%, ${finalColor} ${Math.round(colorProgress * 100)}%)`;

            return (
              <span
                key={wi}
                style={{
                  display: "inline-block",
                  fontFamily: CAPTION_FONTS.montserrat,
                  fontSize,
                  fontWeight: 700,
                  color,
                  textTransform: "uppercase",
                  letterSpacing: "0.02em",
                  lineHeight: 1.05,
                  whiteSpace: "nowrap",
                  textShadow: SHADOW,
                  opacity: isSpoken ? opacity : 0,
                  transform: isSpoken ? `translateY(${yOffset}px)` : `translateY(${slideDist}px)`,
                  visibility: isSpoken ? "visible" : "hidden",
                }}
              >
                {token.text}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const GadzhiStyle: React.FC<GadzhiStyleProps> = ({
  pages,
  fontSize = 90,
  position = "bottom",
  textColor = "#FFFFFF",
  highlightColor = "#F5C518",
  keywords = [],
  maxWordsPerLine = 2,
  wordGap = 14,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
  const keywordSet = useMemo(() => buildKeywordSet(keywords), [keywords]);

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
          >
            <AbsoluteFill
              style={{
                display: "flex",
                justifyContent: position === "top" ? "flex-start" : position === "center" ? "center" : "flex-end",
                alignItems: "flex-start",
                ...(position === "top"
                  ? { paddingTop: CAPTION_PADDING.top, paddingLeft: 80, paddingRight: 80 }
                  : position === "center"
                    ? { paddingLeft: 80, paddingRight: 80 }
                    : { paddingLeft: 80, paddingRight: 80, paddingBottom: 300 }),
              }}
            >
              <div style={{ maxWidth, width: "100%" }}>
              <GadzhiStylePage
                tokens={page.tokens}
                pageStartMs={page.startMs}
                fontSize={fontSize}
                textColor={textColor}
                highlightColor={highlightColor}
                keywordSet={keywordSet}
                maxWordsPerLine={maxWordsPerLine}
                wordGap={wordGap}
              />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
