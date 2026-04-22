import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { StaggerWaveProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

// ── Helpers ────────────────────────────────────────────────────────────────

function splitIntoLines(
  tokens: TikTokToken[],
  maxPerLine: number,
): TikTokToken[][] {
  const lines: TikTokToken[][] = [];
  for (let i = 0; i < tokens.length; i += maxPerLine) {
    lines.push(tokens.slice(i, i + maxPerLine));
  }
  return lines;
}

// ── StaggerWaveWord ────────────────────────────────────────────────────────
//
// Two independent animations run in parallel:
//
// 1. PAGE ENTRANCE STAGGER
//    All words in the page spring in at page start, but each word's spring
//    is offset by (tokenIndex × staggerFrames). This creates a left→right
//    wave of arrivals. The entry Y offset is also token-seeded so words
//    arrive from slightly different heights, reinforcing the wave shape.
//
// 2. KARAOKE ACTIVATION
//    When the word's fromMs arrives, a fast scale+color spring fires.
//    Active word: accent yellow, slight scale-up (1.08×), drop shadow.
//    Past word: full white, scale back to 1.0.
//    Upcoming word: dim white (upcomingOpacity), floating on the idle wave.
//
// 3. IDLE WAVE FLOAT (upcoming words only)
//    A slow propagating sine wave shifts Y by a few px. Phase offset by
//    tokenIndex so the wave moves visibly left→right across the line.

const StaggerWaveWord: React.FC<{
  token: TikTokToken;
  tokenIndex: number;
  pageStartFrame: number;
  currentTimeMs: number;
  accentColor: string;
  upcomingOpacity: number;
  staggerFrames: number;
  waveAmplitude: number;
  waveHz: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  letterSpacing: number;
  allCaps: boolean;
}> = ({
  token,
  tokenIndex,
  pageStartFrame,
  currentTimeMs,
  accentColor,
  upcomingOpacity,
  staggerFrames,
  waveAmplitude,
  waveHz,
  fontFamily,
  fontSize,
  fontWeight,
  letterSpacing,
  allCaps,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isActive = currentTimeMs >= token.fromMs && currentTimeMs < token.toMs;
  const isPast = currentTimeMs >= token.toMs;

  // ── 1. Entry stagger spring ───────────────────────────────────────────
  const entryStart = tokenIndex * staggerFrames;
  const entrySpring = spring({
    fps,
    frame: frame - entryStart,
    config: { mass: 0.55, damping: 14, stiffness: 200, overshootClamping: false },
  });

  // Each word arrives from a slightly different Y height (wave-shaped entry)
  const entryStartY = 44 + Math.sin(tokenIndex * 0.85) * 16;
  const entryTranslateY = interpolate(entrySpring, [0, 1], [entryStartY, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Entry opacity: snaps from 0 → target quickly
  const entryProgress = interpolate(entrySpring, [0, 0.35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // State-based target opacity
  const stateOpacity = isPast || isActive ? 1.0 : upcomingOpacity;
  const finalOpacity = entryProgress * stateOpacity;

  // ── 2. Karaoke activation spring ──────────────────────────────────────
  const wordOnsetFrame = msToFrames(token.fromMs, fps) - pageStartFrame;
  const activateSpring = spring({
    fps,
    frame: frame - wordOnsetFrame,
    config: { mass: 0.3, damping: 12, stiffness: 380, overshootClamping: false },
  });

  // Scale: 1.0 → 1.08 (pop on activation)
  const activateScale = isPast
    ? 1.0
    : isActive
      ? interpolate(activateSpring, [0, 1], [1.0, 1.08], { extrapolateRight: "extend" })
      : 1.0;

  // Interpolate color: we'll express it as a blend factor (0=white, 1=accent)
  const colorBlend = isPast
    ? 0 // deactivated: back to white
    : isActive
      ? interpolate(activateSpring, [0, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
      : 0; // upcoming: white

  const textColor = colorBlend > 0.5 ? accentColor : "#FFFFFF";

  // ── 3. Idle wave float (upcoming words only) ──────────────────────────
  const isSettled = entryProgress > 0.9;
  const idleY =
    !isActive && !isPast && isSettled
      ? Math.sin(
          (frame / fps) * 2 * Math.PI * waveHz - tokenIndex * 0.55,
        ) * waveAmplitude
      : 0;

  const finalTranslateY = entryTranslateY + idleY;
  const finalScale = activateScale;

  // ── Drop shadow ────────────────────────────────────────────────────────
  const shadow = isActive
    ? `0 0 16px ${accentColor}CC, 0 2px 6px rgba(0,0,0,0.65)`
    : `0 2px 5px rgba(0,0,0,0.6)`;

  const displayText = allCaps ? token.text.toUpperCase() : token.text;

  return (
    <span
      style={{
        display: "inline-block",
        opacity: finalOpacity,
        transform: `translateY(${finalTranslateY}px) scale(${finalScale})`,
        transformOrigin: "center bottom",
        textShadow: shadow,
        fontFamily,
        fontSize,
        fontWeight,
        color: textColor,
        letterSpacing: `${letterSpacing}em`,
        lineHeight: 1.2,
        whiteSpace: "nowrap",
        willChange: "transform, opacity, color",
      }}
    >
      {displayText}
    </span>
  );
};

// ── StaggerWavePage ────────────────────────────────────────────────────────

const StaggerWavePage: React.FC<{
  page: TikTokPage;
  pageStartFrame: number;
  accentColor: string;
  upcomingOpacity: number;
  staggerFrames: number;
  waveAmplitude: number;
  waveHz: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  letterSpacing: number;
  allCaps: boolean;
  maxWordsPerLine: number;
  lineGap: number;
  wordGap: number;
}> = ({
  page,
  pageStartFrame,
  accentColor,
  upcomingOpacity,
  staggerFrames,
  waveAmplitude,
  waveHz,
  fontFamily,
  fontSize,
  fontWeight,
  letterSpacing,
  allCaps,
  maxWordsPerLine,
  lineGap,
  wordGap,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentTimeMs = page.startMs + (frame / fps) * 1000;

  const lines = useMemo(
    () => splitIntoLines(page.tokens, maxWordsPerLine),
    [page.tokens, maxWordsPerLine],
  );

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: lineGap,
      }}
    >
      {lines.map((lineTokens, li) => (
        <div
          key={li}
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "center",
            justifyContent: "center",
            flexWrap: "nowrap",
            gap: wordGap,
          }}
        >
          {lineTokens.map((token, ti) => {
            const tokenIndex = li * maxWordsPerLine + ti;
            return (
              <StaggerWaveWord
                key={`${li}-${ti}`}
                token={token}
                tokenIndex={tokenIndex}
                pageStartFrame={pageStartFrame}
                currentTimeMs={currentTimeMs}
                accentColor={accentColor}
                upcomingOpacity={upcomingOpacity}
                staggerFrames={staggerFrames}
                waveAmplitude={waveAmplitude}
                waveHz={waveHz}
                fontFamily={fontFamily}
                fontSize={fontSize}
                fontWeight={fontWeight}
                letterSpacing={letterSpacing}
                allCaps={allCaps}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
};

// ── StaggerWave (main export) ──────────────────────────────────────────────

export const StaggerWave: React.FC<StaggerWaveProps> = ({
  pages,
  fontFamily = CAPTION_FONTS.montserrat,
  fontSize = 76,
  fontWeight = 900,
  position = "bottom",
  accentColor = "#FFED00",
  upcomingOpacity = 0.38,
  staggerFrames = 3,
  waveAmplitude = 3,
  waveHz = 0.7,
  letterSpacing = 0.02,
  allCaps = true,
  maxWordsPerLine = 3,
  lineGap = 14,
  wordGap = 20,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const pageStartFrame = msToFrames(page.startMs, fps);
        const pageDurationFrames = msToFrames(page.durationMs, fps);

        return (
          <Sequence
            key={pageIndex}
            from={pageStartFrame}
            durationInFrames={Math.max(pageDurationFrames, 1)}
            premountFor={5}
          >
            <AbsoluteFill
              style={{
                display: "flex",
                alignItems: "center",
                ...getCaptionPositionStyle(position),
              }}
            >
              <div style={{ maxWidth, width: "100%" }}>
                <StaggerWavePage
                  page={page}
                  pageStartFrame={pageStartFrame}
                  accentColor={accentColor}
                  upcomingOpacity={upcomingOpacity}
                  staggerFrames={staggerFrames}
                  waveAmplitude={waveAmplitude}
                  waveHz={waveHz}
                  fontFamily={fontFamily}
                  fontSize={fontSize}
                  fontWeight={fontWeight}
                  letterSpacing={letterSpacing}
                  allCaps={allCaps}
                  maxWordsPerLine={maxWordsPerLine}
                  lineGap={lineGap}
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
