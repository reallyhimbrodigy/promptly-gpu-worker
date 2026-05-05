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
import type { MagazineCutoutProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { leadInElapsed } from "../shared/leadIn";

// Lead-in for the cutout flutter spring (mass:0.65, damping:13,
// stiffness:180). Slightly slower settle than the editorial springs —
// 14 frames gives the paper-drop time to land before the word is spoken.
const CUTOUT_LEAD_IN = 14;

// ── Helpers ────────────────────────────────────────────────────────────────

// Deterministic hash for per-word visual variation.
// Returns a float in [0, 1) seeded by two integers.
function seededRand(a: number, b: number): number {
  return Math.abs(Math.sin(a * 127.1 + b * 311.7) * 43758.5453) % 1;
}

// Newsprint cream palette — subtle variation simulates different source pages.
const CUTOUT_BG_VARIANTS = [
  "#FDF8F0", // warm cream
  "#F9F4EC", // slightly more yellow — older newsprint
  "#FBF6ED", // middle ground
];

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

// ── MagazineCutoutWord ─────────────────────────────────────────────────────
//
// Visual identity:
//   • Each word is a rectangular "clipping" (slightly off-white bg, ink text).
//   • Per-word deterministic tilt, bg shade, and size shift — mimics real
//     cutouts taken from different magazine/newspaper pages.
//   • Entry: the clipping flutters down from slightly above its final resting
//     position, entering with extra tilt that settles to its final angle.
//   • Active word: paper lifts (larger shadow, slight scale-up).
//   • Past words: settled flat, shadow reduced.

const MagazineCutoutWord: React.FC<{
  token: TikTokToken;
  tokenIndex: number;
  pageIndex: number;
  pageStartFrame: number;
  currentTimeMs: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  inkColor: string;
  cutoutBg: string;
  maxRotation: number;
  sizeVariation: number;
  cutoutPaddingX: number;
  cutoutPaddingY: number;
  allCaps: boolean;
}> = ({
  token,
  tokenIndex,
  pageIndex,
  pageStartFrame,
  currentTimeMs,
  fontFamily,
  fontSize,
  fontWeight,
  inkColor,
  cutoutBg: _baseBg,
  maxRotation,
  sizeVariation,
  cutoutPaddingX,
  cutoutPaddingY,
  allCaps,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const isActive = currentTimeMs >= token.fromMs && currentTimeMs < token.toMs;
  const isPast = currentTimeMs >= token.toMs;

  const wordOnsetFrame = msToFrames(token.fromMs, fps) - pageStartFrame;

  // ── Deterministic per-word variation ──────────────────────────────────
  // Seeded on (tokenIndex, pageIndex) so the same word always looks the same.
  const r1 = seededRand(tokenIndex * 5 + 1, pageIndex * 7 + 3);
  const r2 = seededRand(tokenIndex * 11 + 2, pageIndex * 5 + 9);
  const r3 = seededRand(tokenIndex * 3 + 7, pageIndex * 13 + 1);
  const r4 = seededRand(tokenIndex * 17 + 4, pageIndex * 3 + 6);

  // Final resting rotation: spans [-maxRotation, +maxRotation]
  const finalRotation = (r1 - 0.5) * 2 * maxRotation;

  // Entry rotation: word arrives with extra tilt, settles to finalRotation
  const entryExtraRotation = (r2 - 0.5) * 2 * 8; // extra ±8°

  // Drop height: words fall from different heights
  const dropHeight = 28 + r3 * 20; // 28–48px above final position

  // Background shade: cycle through newsprint variants
  const bg = CUTOUT_BG_VARIANTS[Math.floor(r4 * CUTOUT_BG_VARIANTS.length)];

  // Font size variation: each word is slightly larger or smaller
  const sizeShift = (r1 - 0.5) * 2 * sizeVariation;
  const wordFontSize = fontSize + sizeShift;

  // ── Entry spring ───────────────────────────────────────────────────────
  // Floaty, slight overshoot: the clipping flutters down and settles AT the
  // spoken moment (the lead-in shifts the spring start earlier so the paper
  // is at rest when the word is audibly delivered).
  const entrySpring = spring({
    fps,
    frame: leadInElapsed(frame, wordOnsetFrame, CUTOUT_LEAD_IN),
    config: {
      mass: 0.65,
      damping: 13,
      stiffness: 180,
      overshootClamping: false,
    },
  });

  const translateY = interpolate(entrySpring, [0, 1], [-dropHeight, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(entrySpring, [0, 0.2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Rotation animates from (finalRotation + entryExtraRotation) → finalRotation
  const currentRotation = interpolate(
    entrySpring,
    [0, 1],
    [finalRotation + entryExtraRotation, finalRotation],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // ── Active lift ────────────────────────────────────────────────────────
  // Active word scales up slightly ("lifted from the table").
  const liftScale = isPast ? 1.0 : isActive ? 1.05 : 1.0;

  // Shadow depth communicates paper lift
  const shadow = isActive
    ? `3px 6px 14px rgba(0,0,0,0.38), 1px 2px 4px rgba(0,0,0,0.22)`
    : isPast
      ? `1px 2px 5px rgba(0,0,0,0.22)`
      : `1px 2px 5px rgba(0,0,0,0.22)`;

  // Ink color dims slightly for past words (faded newsprint)
  const textColor = inkColor;
  const textOpacity = isPast ? 0.72 : 1.0;

  const displayText = allCaps ? token.text.toUpperCase() : token.text;

  return (
    <span
      style={{
        display: "inline-block",
        opacity,
        transform: `translateY(${translateY}px) rotate(${currentRotation}deg) scale(${liftScale})`,
        transformOrigin: "center center",
        willChange: "transform, opacity",
      }}
    >
      <span
        style={{
          display: "inline-block",
          background: bg,
          paddingTop: cutoutPaddingY,
          paddingBottom: cutoutPaddingY,
          paddingLeft: cutoutPaddingX,
          paddingRight: cutoutPaddingX,
          boxShadow: shadow,
          // Slightly irregular border — simulates imperfect cut edge
          border: "1px solid rgba(0,0,0,0.10)",
          borderBottomWidth: 2,
          fontFamily,
          fontSize: wordFontSize,
          fontWeight,
          color: textColor,
          opacity: textOpacity,
          lineHeight: 1.2,
          letterSpacing: "0.01em",
          whiteSpace: "nowrap",
          userSelect: "none",
        }}
      >
        {displayText}
      </span>
    </span>
  );
};

// ── MagazineCutoutPage ─────────────────────────────────────────────────────

const MagazineCutoutPage: React.FC<{
  page: TikTokPage;
  pageIndex: number;
  pageStartFrame: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  inkColor: string;
  cutoutBg: string;
  maxRotation: number;
  sizeVariation: number;
  cutoutPaddingX: number;
  cutoutPaddingY: number;
  allCaps: boolean;
  maxWordsPerLine: number;
  lineGap: number;
  wordGap: number;
}> = ({
  page,
  pageIndex,
  pageStartFrame,
  fontFamily,
  fontSize,
  fontWeight,
  inkColor,
  cutoutBg,
  maxRotation,
  sizeVariation,
  cutoutPaddingX,
  cutoutPaddingY,
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

  let globalTokenIndex = 0;

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
          {lineTokens.map((token) => {
            const idx = globalTokenIndex++;
            return (
              <MagazineCutoutWord
                key={idx}
                token={token}
                tokenIndex={idx}
                pageIndex={pageIndex}
                pageStartFrame={pageStartFrame}
                currentTimeMs={currentTimeMs}
                fontFamily={fontFamily}
                fontSize={fontSize}
                fontWeight={fontWeight}
                inkColor={inkColor}
                cutoutBg={cutoutBg}
                maxRotation={maxRotation}
                sizeVariation={sizeVariation}
                cutoutPaddingX={cutoutPaddingX}
                cutoutPaddingY={cutoutPaddingY}
                allCaps={allCaps}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
};

// ── MagazineCutout (main export) ───────────────────────────────────────────

export const MagazineCutout: React.FC<MagazineCutoutProps> = ({
  pages,
  fontFamily = CAPTION_FONTS.playfairDisplay,
  fontSize = 70,
  fontWeight = 900,
  position = "center",
  cutoutBg = "#FDF8F0",
  inkColor = "#0D0D0D",
  maxRotation = 6,
  sizeVariation = 10,
  cutoutPaddingX = 14,
  cutoutPaddingY = 8,
  allCaps = true,
  maxWordsPerLine = 3,
  lineGap = 18,
  wordGap = 12,
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
            premountFor={10}
          >
            <AbsoluteFill
              style={{
                ...getCaptionPositionStyle(position),
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div style={{ maxWidth, width: "100%" }}>
                <MagazineCutoutPage
                  page={page}
                  pageIndex={pageIndex}
                  pageStartFrame={pageStartFrame}
                  fontFamily={fontFamily}
                  fontSize={fontSize}
                  fontWeight={fontWeight}
                  inkColor={inkColor}
                  cutoutBg={cutoutBg}
                  maxRotation={maxRotation}
                  sizeVariation={sizeVariation}
                  cutoutPaddingX={cutoutPaddingX}
                  cutoutPaddingY={cutoutPaddingY}
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
