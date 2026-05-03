import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokPage, TikTokToken } from "../shared/types";
import type { PassageProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { buildKeywordSet, isKeyword } from "../shared/keywords";

/* ─── Word ─── */

const PassageWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  isKw: boolean;
  textColor: string;
  keywordColor: string;
  fontSize: number;
  fadeDurationMs: number;
  trackingShiftDurationMs: number;
  keywordTrackingFrom: number;
  keywordTrackingTo: number;
  bodyTracking: number;
  textShadow: string;
}> = ({
  token,
  pageStartMs,
  isKw,
  textColor,
  keywordColor,
  fontSize,
  fadeDurationMs,
  trackingShiftDurationMs,
  keywordTrackingFrom,
  keywordTrackingTo,
  bodyTracking,
  textShadow,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pageLocalMs = (frame / fps) * 1000;
  const tokenLocalMs = token.fromMs - pageStartMs;

  const opacity = interpolate(
    pageLocalMs,
    [tokenLocalMs, tokenLocalMs + fadeDurationMs],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Keyword tracking shift: starts tight (at reveal) and expands over trackingShiftDurationMs
  const trackingProgress = interpolate(
    pageLocalMs,
    [tokenLocalMs, tokenLocalMs + trackingShiftDurationMs],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  // Ease out — opens fast then settles
  const eased = 1 - Math.pow(1 - trackingProgress, 2.5);

  const letterSpacing = isKw
    ? `${interpolate(eased, [0, 1], [keywordTrackingFrom, keywordTrackingTo])}em`
    : `${bodyTracking}em`;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: isKw ? CAPTION_FONTS.playfairDisplay : CAPTION_FONTS.lora,
        fontSize: isKw ? Math.round(fontSize * 1.04) : fontSize,
        fontWeight: isKw ? 600 : 400,
        fontStyle: isKw ? "italic" : "normal",
        color: isKw ? keywordColor : textColor,
        letterSpacing,
        lineHeight: 1,
        whiteSpace: "nowrap",
        textShadow,
        // Universal stroke for guaranteed readability over any background.
        WebkitTextStroke: "0.75px rgba(0,0,0,0.6)",
        opacity,
      }}
    >
      {token.text}
    </span>
  );
};

/* ─── Page ─── */

const PassagePage: React.FC<{
  page: TikTokPage;
  lines: TikTokToken[][];
  kwSet: Set<string>;
  textColor: string;
  keywordColor: string;
  fontSize: number;
  fadeDurationMs: number;
  trackingShiftDurationMs: number;
  keywordTrackingFrom: number;
  keywordTrackingTo: number;
  bodyTracking: number;
  textShadow: string;
  lineGap: number;
  wordGap: number;
  lineHeight: number;
  positionStyle: React.CSSProperties;
  maxWidth: number;
}> = ({
  page,
  lines,
  kwSet,
  textColor,
  keywordColor,
  fontSize,
  fadeDurationMs,
  trackingShiftDurationMs,
  keywordTrackingFrom,
  keywordTrackingTo,
  bodyTracking,
  textShadow,
  lineGap,
  wordGap,
  lineHeight,
  positionStyle,
  maxWidth,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pageLocalMs = (frame / fps) * 1000;

  // 15ms snap fade-out so the page exits on spoken-word timing.
  const fadeOut = interpolate(
    pageLocalMs,
    [page.durationMs - 15, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        ...positionStyle,
        opacity: fadeOut,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: lineGap,
          maxWidth,
          width: maxWidth,
          lineHeight,
        }}
      >
        {lines.map((lineTokens, lineIdx) => (
          <div
            key={lineIdx}
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "center",
              flexWrap: "wrap",
              gap: wordGap,
              maxWidth,
            }}
          >
            {lineTokens.map((token, idx) => (
              <PassageWord
                key={idx}
                token={token}
                pageStartMs={page.startMs}
                isKw={isKeyword(token.text, kwSet)}
                textColor={textColor}
                keywordColor={keywordColor}
                fontSize={fontSize}
                fadeDurationMs={fadeDurationMs}
                trackingShiftDurationMs={trackingShiftDurationMs}
                keywordTrackingFrom={keywordTrackingFrom}
                keywordTrackingTo={keywordTrackingTo}
                bodyTracking={bodyTracking}
                textShadow={textShadow}
              />
            ))}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ─── Main Component ─── */

export const Passage: React.FC<PassageProps> = ({
  pages,
  keywords = [],
  textColor = "#F1EADB",
  keywordColor = "#D4A76A",
  fontSize = 76,
  position = "bottom",
  maxWordsPerLine = 5,
  maxWidthPercent = 0.78,
  lineGap = 16,
  wordGap = 18,
  fadeDurationMs = 360,
  trackingShiftDurationMs = 520,
  keywordTrackingFrom = -0.015,
  keywordTrackingTo = 0.09,
  bodyTracking = -0.005,
  lineHeight = 1.12,
  textShadow = "0 2px 18px rgba(0,0,0,0.55)",
}) => {
  const { fps, width } = useVideoConfig();
  const kwSet = useMemo(() => buildKeywordSet(keywords), [keywords]);
  const positionStyle = getCaptionPositionStyle(position);
  const maxWidth = width * maxWidthPercent;

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
            <PassagePage
              page={page}
              lines={lines}
              kwSet={kwSet}
              textColor={textColor}
              keywordColor={keywordColor}
              fontSize={fontSize}
              fadeDurationMs={fadeDurationMs}
              trackingShiftDurationMs={trackingShiftDurationMs}
              keywordTrackingFrom={keywordTrackingFrom}
              keywordTrackingTo={keywordTrackingTo}
              bodyTracking={bodyTracking}
              textShadow={textShadow}
              lineGap={lineGap}
              wordGap={wordGap}
              lineHeight={lineHeight}
              positionStyle={positionStyle}
              maxWidth={maxWidth}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
