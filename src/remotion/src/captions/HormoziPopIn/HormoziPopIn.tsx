import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { SpringConfig } from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { HormoziPopInProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

const HORMOZI_SPRING: SpringConfig = {
  mass: 0.5,
  damping: 11,
  stiffness: 200,
  overshootClamping: false,
};

function normalizeWord(text: string): string {
  return text.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

function buildStrokeShadow(
  strokeWidth: number,
  strokeColor: string,
  enableSoftShadow: boolean,
): string {
  const s = Math.ceil(strokeWidth / 2);
  const shadows: string[] = [
    `${-s}px ${-s}px 0 ${strokeColor}`,
    `${s}px ${-s}px 0 ${strokeColor}`,
    `${-s}px ${s}px 0 ${strokeColor}`,
    `${s}px ${s}px 0 ${strokeColor}`,
    `0 ${-s}px 0 ${strokeColor}`,
    `0 ${s}px 0 ${strokeColor}`,
    `${-s}px 0 0 ${strokeColor}`,
    `${s}px 0 0 ${strokeColor}`,
  ];
  if (enableSoftShadow) {
    shadows.push("0 4px 8px rgba(0,0,0,0.5)");
  }
  return shadows.join(", ");
}

/** Single word with spring pop-in animation */
const HormoziWord: React.FC<{
  token: TikTokToken;
  globalIndex: number;
  pageStartMs: number;
  wordColor: string;
  isHighlight: boolean;
  highlightScale: number;
  fontFamily: string;
  fontSize: number;
  letterSpacing: number;
  allCaps: boolean;
  textShadow: string;
  springConfig: SpringConfig;
  staggerDelayFrames: number;
  translateYDistance: number;
}> = ({
  token,
  globalIndex,
  pageStartMs,
  wordColor,
  isHighlight,
  highlightScale,
  fontFamily,
  fontSize,
  letterSpacing,
  allCaps,
  textShadow,
  springConfig,
  staggerDelayFrames,
  translateYDistance,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Token entry relative to this Sequence (which starts at page.startMs)
  const tokenEntryFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const stagger = globalIndex * staggerDelayFrames;
  const delayedEntry = tokenEntryFrame + stagger;

  // Spring drives entrance animation only: 0 -> overshoot -> 1
  const springProgress = spring({
    fps,
    frame: frame - delayedEntry,
    config: springConfig,
  });

  // Scale: spring animates 0 -> 1 for entrance only (NOT to highlightScale)
  // Highlighted words use a larger fontSize instead (affects layout properly)
  const scale = springProgress;

  // Y translate: moves from +distance to 0
  const yOffset = interpolate(springProgress, [0, 1], [translateYDistance, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Opacity: tied to spring start so word fades in quickly
  const opacity = interpolate(springProgress, [0, 0.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Highlighted words get a larger fontSize (this DOES affect layout, unlike scale)
  const wordFontSize = isHighlight
    ? Math.round(fontSize * highlightScale)
    : fontSize;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily,
        fontSize: wordFontSize,
        fontWeight: 900,
        color: wordColor,
        textTransform: allCaps ? "uppercase" : "none",
        letterSpacing: `${letterSpacing}em`,
        textShadow,
        transform: `scale(${scale}) translateY(${yOffset}px)`,
        transformOrigin: "center bottom",
        opacity,
        whiteSpace: "nowrap",
        lineHeight: 1.2,
        // Vertical alignment so different font sizes sit on the same baseline
        verticalAlign: "baseline",
      }}
    >
      {token.text}
    </span>
  );
};

/** Single page of words, split into lines */
const HormoziPage: React.FC<{
  page: TikTokPage;
  highlightMap: Map<string, string>;
  highlightScale: number;
  primaryColor: string;
  fontFamily: string;
  fontSize: number;
  letterSpacing: number;
  allCaps: boolean;
  textShadow: string;
  springConfig: SpringConfig;
  staggerDelayFrames: number;
  translateY: number;
  maxWordsPerLine: number;
  maxWidth?: number;
}> = ({
  page,
  highlightMap,
  highlightScale,
  primaryColor,
  fontFamily,
  fontSize,
  letterSpacing,
  allCaps,
  textShadow,
  springConfig,
  staggerDelayFrames,
  translateY,
  maxWordsPerLine,
  maxWidth,
}) => {
  // Split tokens into lines
  const lines: TikTokToken[][] = [];
  for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
    lines.push(page.tokens.slice(i, i + maxWordsPerLine));
  }

  let globalIndex = 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
        width: "100%",
        ...(maxWidth != null ? { maxWidth } : {}),
      }}
    >
      {lines.map((lineTokens, lineIdx) => (
        <div
          key={lineIdx}
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "baseline",
            gap: 0,
          }}
        >
          {lineTokens.map((token) => {
            const normalized = normalizeWord(token.text);
            const matchedColor = highlightMap.get(normalized);
            const isHighlight = matchedColor !== undefined;
            const wordColor = matchedColor ?? primaryColor;
            const idx = globalIndex;
            globalIndex++;

            return (
              <div
                key={`${lineIdx}-${idx}`}
                style={{
                  // Each word gets a fixed-size wrapper with padding for spacing.
                  // This ensures layout is correct regardless of scale transforms.
                  padding: "0 8px",
                }}
              >
                <HormoziWord
                  token={token}
                  globalIndex={idx}
                  pageStartMs={page.startMs}
                  wordColor={wordColor}
                  isHighlight={isHighlight}
                  highlightScale={highlightScale}
                  fontFamily={fontFamily}
                  fontSize={fontSize}
                  letterSpacing={letterSpacing}
                  allCaps={allCaps}
                  textShadow={textShadow}
                  springConfig={springConfig}
                  staggerDelayFrames={staggerDelayFrames}
                  translateYDistance={translateY}
                />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const HormoziPopIn: React.FC<HormoziPopInProps> = ({
  pages,
  highlightWords = [],
  highlightScale = 1.45,
  fontFamily = CAPTION_FONTS.montserrat,
  fontSize = 68,
  primaryColor = "#FFFFFF",
  strokeColor = "#000000",
  strokeWidth = 6,
  position = "center",
  letterSpacing = 0.05,
  springConfig = HORMOZI_SPRING,
  staggerDelayFrames = 1,
  translateY = 8,
  maxWordsPerLine = 4,
  allCaps = true,
  enableSoftShadow = true,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

  const highlightMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const hw of highlightWords) {
      map.set(normalizeWord(hw.text), hw.color);
    }
    return map;
  }, [highlightWords]);

  const textShadow = useMemo(
    () => buildStrokeShadow(strokeWidth, strokeColor, enableSoftShadow),
    [strokeWidth, strokeColor, enableSoftShadow],
  );

  const positionStyle = getCaptionPositionStyle(position);

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
            premountFor={10}
          >
            <AbsoluteFill
              style={{
                display: "flex",
                alignItems: "center",
                ...positionStyle,
              }}
            >
              <HormoziPage
                page={page}
                highlightMap={highlightMap}
                highlightScale={highlightScale}
                primaryColor={primaryColor}
                fontFamily={fontFamily}
                fontSize={fontSize}
                letterSpacing={letterSpacing}
                allCaps={allCaps}
                textShadow={textShadow}
                springConfig={springConfig}
                staggerDelayFrames={staggerDelayFrames}
                translateY={translateY}
                maxWordsPerLine={maxWordsPerLine}
                maxWidth={maxWidth}
              />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
