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
import type { PrimeProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { boundedFade } from "../shared/fadeTiming";
import { CAPTION_PADDING } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE, type ScaleFitItem } from "../shared/fit";

// ---------------------------------------------------------------------------
// PrimeWord — single word with staggered entrance
// ---------------------------------------------------------------------------

const PrimeWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  wordIndex: number;
  windowMs: number;
  isLine2: boolean;
  isSpecial: boolean;
  line1Color: string;
  line2Color: string;
  line1FontSize: number;
  line2FontSize: number;
  line1FontWeight: number | string;
  line2FontWeight: number | string;
  fontFamily: string;
  specialFontFamily: string;
  specialColor: string;
  letterSpacing: string;
  textShadow: string;
  fitFloored?: boolean;
}> = ({
  token,
  pageStartMs,
  wordIndex,
  windowMs,
  isLine2,
  isSpecial,
  line1Color,
  line2Color,
  line1FontSize,
  line2FontSize,
  line1FontWeight,
  line2FontWeight,
  fontFamily,
  specialFontFamily,
  specialColor,
  letterSpacing,
  textShadow,
  fitFloored,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Spring entrance per word — WS2 fade-bound: 160ms base (was 250), capped at
  // 25% of this word's on-screen window so on fast speech the word finishes
  // arriving before the next one starts, instead of a train of half-sprung
  // words (shared/fadeTiming).
  const activateFrame = Math.round(((token.fromMs - pageStartMs) / 1000) * fps);
  // FRAME-1-IS-FINAL ENTRANCE (Zac 2026-07-13, 4th/5th pass): the word SNAPS on — final
  // position, full opacity, from frame 1. ZERO entrance animation of any kind (the old
  // slide-spring is gone entirely, not just zeroed). Prime's character is its two-tier
  // hierarchy + keyword breakout, which is static, not a travelling entrance.
  const slideY = 0;
  const wordOpacity = frame >= activateFrame ? 1 : 0;

  const color = isSpecial ? specialColor : line1Color;
  const fontSize = isSpecial ? line2FontSize : (isLine2 ? line2FontSize : line1FontSize);
  const fontWeightVal = isLine2 ? line2FontWeight : line1FontWeight;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: isSpecial ? specialFontFamily : fontFamily,
        fontSize,
        fontWeight: isSpecial ? 600 : fontWeightVal,
        fontStyle: isSpecial ? "italic" : "normal",
        color,
        letterSpacing,
        lineHeight: 1.1,
        textShadow,
        textTransform: "lowercase",
        whiteSpace: "nowrap",
        transform: `translateY(${slideY}px)`,
        opacity: wordOpacity,
        marginRight: 12,
        // F4 last resort: below the fit floor, let the glyph run break
        // rather than ever cross a margin.
        ...(fitFloored ? CHARWRAP_FALLBACK_STYLE : {}),
      }}
    >
      {token.text}
    </span>
  );
};

// ---------------------------------------------------------------------------
// PrimePage — splits tokens into lines, renders word by word
// ---------------------------------------------------------------------------

const PrimePage: React.FC<{
  page: TikTokPage;
  maxWordsPerLine: number;
  lineGap: number;
  specialWords: string[];
  line1Color: string;
  line2Color: string;
  line1FontSize: number;
  line2FontSize: number;
  line1FontWeight: number | string;
  line2FontWeight: number | string;
  fontFamily: string;
  specialFontFamily: string;
  specialColor: string;
  letterSpacing: string;
  textShadow: string;
}> = ({
  page,
  maxWordsPerLine,
  lineGap,
  specialWords,
  ...wordProps
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();

  const isSpecial = (text: string) =>
    specialWords.some((w) => w.toLowerCase() === text.toLowerCase());

  // Split tokens into lines — special words get their own line
  const lines: { tokens: TikTokToken[]; hasSpecial: boolean }[] = [];
  let buffer: TikTokToken[] = [];

  for (const token of page.tokens) {
    if (isSpecial(token.text)) {
      if (buffer.length > 0) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
      lines.push({ tokens: [token], hasSpecial: true });
    } else {
      buffer.push(token);
      if (buffer.length >= maxWordsPerLine) {
        lines.push({ tokens: buffer, hasSpecial: false });
        buffer = [];
      }
    }
  }
  if (buffer.length > 0) {
    lines.push({ tokens: buffer, hasSpecial: false });
  }

  // F4 width-fit guarantee: Prime's lines never CSS-wrap, so the overflow
  // unit is the whole nowrap line (mixed fonts: inter normals, playfair
  // italic specials at DOUBLE size). Measure each composed line and scale
  // the page uniformly; below the floor the word spans get the char-break
  // fallback and the rows are allowed to flex-wrap.
  const fit = useMemo(() => {
    let normalCount = 0;
    const items = lines.map((line) => {
      const isL2 = !line.hasSpecial && normalCount++ >= 1;
      return {
        parts: line.tokens.map((t) => ({
          text: t.text,
          fontSize: line.hasSpecial
            ? wordProps.line2FontSize * 2
            : isL2
              ? wordProps.line2FontSize
              : wordProps.line1FontSize,
          font: {
            fontFamily: line.hasSpecial
              ? wordProps.specialFontFamily
              : wordProps.fontFamily,
            fontWeight: line.hasSpecial
              ? 600
              : isL2
                ? wordProps.line2FontWeight
                : wordProps.line1FontWeight,
            letterSpacingEm: 0.01,
            lowercase: true, // PrimeWord renders textTransform:"lowercase"
          },
        })),
        extraPx: 12 * line.tokens.length, // marginRight 12 on every word
      };
    });
    return fitScale(items as ScaleFitItem[], width * 0.85, "Prime");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, specialWords, width]);

  if (frame < 0) return null;

  // Fade out — bounded to 25% of the page window so a short final page doesn't
  // spend a fifth of its life fading out (shared/fadeTiming).
  const pageLocalMs = (frame / fps) * 1000;
  const pageFadeOutMs = boundedFade(120, page.durationMs);
  const fadeOut = interpolate(
    pageLocalMs,
    [page.durationMs - pageFadeOutMs, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  let globalWordIdx = 0;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        opacity: fadeOut,
      }}
    >
      {(() => {
        let normalLineCount = 0;
        return lines.map((line, lineIdx) => {
        const isLine2 = !line.hasSpecial && normalLineCount++ >= 1;
        return (
          <div
            key={lineIdx}
            style={{
              display: "flex",
              alignItems: "baseline",
              marginTop: lineIdx > 0 ? lineGap : 0,
              ...(line.hasSpecial ? { justifyContent: "center" } : {}),
              ...(fit.floored
                ? { flexWrap: "wrap", justifyContent: "center" }
                : {}),
            }}
          >
            {line.tokens.map((token, idx) => {
              const wi = globalWordIdx++;
              const specialMul = line.hasSpecial ? 2 : 1;
              // window = time until the next word arrives (page.tokens is flat,
              // reading order), or page end for the last word — the WS2 bound.
              const nextTok = page.tokens[wi + 1];
              const windowMs = (nextTok ? nextTok.fromMs : page.startMs + page.durationMs) - token.fromMs;
              return (
                <PrimeWord
                  key={idx}
                  token={token}
                  pageStartMs={page.startMs}
                  wordIndex={wi}
                  windowMs={windowMs}
                  isLine2={isLine2}
                  isSpecial={line.hasSpecial}
                  {...wordProps}
                  line2FontSize={wordProps.line2FontSize * specialMul * fit.scale}
                  line1FontSize={wordProps.line1FontSize * specialMul * fit.scale}
                  fitFloored={fit.floored}
                />
              );
            })}
          </div>
        );
      });
      })()}
    </div>
  );
};

// ---------------------------------------------------------------------------
// Prime — main exported component
// ---------------------------------------------------------------------------

export const Prime: React.FC<PrimeProps> = ({
  pages,
  fontFamily = CAPTION_FONTS.inter,
  position = "bottom",
  line1Color = "#FFFFFF",
  line2Color = "#3BA5FF",
  line1FontSize = 52,
  line2FontSize = 66,
  line1FontWeight = 600,
  line2FontWeight = 800,
  maxWordsPerLine = 3,
  letterSpacing = "0.01em",
  // Positive gap so the oversized italic "break-out" keyword line and the
  // regular sans line below it don't visibly overlap. Prior value of -30
  // pulled them on top of each other on long keywords.
  lineGap = 12,
  textShadow = "0 2px 8px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.4)",
  specialWords = [],
  specialFontFamily = CAPTION_FONTS.playfairDisplay,
  specialColor = "#5ED4E8",
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

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
            <div
              style={{
                position: "absolute",
                left: "50%",
                maxWidth,
                ...(position === "top"
                  ? { top: CAPTION_PADDING.top, transform: "translateX(-50%)" }
                  : position === "center"
                    ? { top: "50%", transform: "translate(-50%, -50%)" }
                    : { bottom: CAPTION_PADDING.bottomSafe, transform: "translateX(-50%)" }
                ),
              }}
            >
              <PrimePage
                page={page}
                maxWordsPerLine={maxWordsPerLine}
                lineGap={lineGap}
                specialWords={specialWords}
                line1Color={line1Color}
                line2Color={line2Color}
                line1FontSize={line1FontSize}
                line2FontSize={line2FontSize}
                line1FontWeight={line1FontWeight}
                line2FontWeight={line2FontWeight}
                fontFamily={fontFamily}
                specialFontFamily={specialFontFamily}
                specialColor={specialColor}
                letterSpacing={letterSpacing}
                textShadow={textShadow}
              />
            </div>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
