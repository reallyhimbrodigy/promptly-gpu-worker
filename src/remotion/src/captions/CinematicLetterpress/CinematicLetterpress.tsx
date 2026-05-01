import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { CinematicLetterpressProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { CAPTION_PADDING } from "../shared/captionPosition";

// ── LetterpressWord ───────────────────────────────────────────────────────
// Each word does a blur-to-sharp "focus pull" when it activates.

const LetterpressWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  textColor: string;
  letterSpacing: string;
  textShadow: string;
  lineHeight: number;
  blurAmount: number;
  blurDurationMs: number;
  enableScale: boolean;
  scaleFrom: number;
  lowercase: boolean;
}> = ({
  token,
  pageStartMs,
  fontFamily,
  fontSize,
  fontWeight,
  textColor,
  letterSpacing,
  textShadow,
  lineHeight,
  blurAmount,
  blurDurationMs,
  enableScale,
  scaleFrom,
  lowercase,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Current time in ms relative to page start (frame is Sequence-local)
  const pageLocalMs = (frame / fps) * 1000;

  // When this word activates relative to the page start
  const tokenLocalMs = token.fromMs - pageStartMs;

  // ── Blur: focus pull from blurry to sharp ──────────────────────────────
  const blur = interpolate(
    pageLocalMs,
    [tokenLocalMs, tokenLocalMs + blurDurationMs],
    [blurAmount, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // ── Opacity: invisible before activation, fades in with blur ──────────
  const opacity = interpolate(
    pageLocalMs,
    [tokenLocalMs, tokenLocalMs + blurDurationMs],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // ── Scale: subtle grow on entry ───────────────────────────────────────
  const scale = enableScale
    ? interpolate(
        pageLocalMs,
        [tokenLocalMs, tokenLocalMs + blurDurationMs],
        [scaleFrom, 1.0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      )
    : 1.0;

  const displayText = lowercase ? token.text.toLowerCase() : token.text;

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily,
        fontSize,
        fontWeight,
        color: textColor,
        letterSpacing,
        textShadow,
        // Universal stroke for guaranteed readability over any background.
        WebkitTextStroke: "0.75px rgba(0,0,0,0.55)",
        lineHeight,
        filter: `blur(${blur}px)`,
        opacity,
        transform: `scale(${scale})`,
        transformOrigin: "center center",
        whiteSpace: "nowrap",
      }}
    >
      {displayText}
    </span>
  );
};

// ── LetterpressPage ───────────────────────────────────────────────────────
// Wraps all words for one page, handles line splitting and page exit blur.

const LetterpressPage: React.FC<{
  page: TikTokPage;
  pageDurationFrames: number;
  fontFamily: string;
  fontSize: number;
  fontWeight: number | string;
  textColor: string;
  letterSpacing: string;
  textShadow: string;
  lineHeight: number;
  blurAmount: number;
  blurDurationMs: number;
  enableScale: boolean;
  scaleFrom: number;
  maxWordsPerLine: number;
  lineGap: number;
  exitDurationMs: number;
  lowercase: boolean;
}> = ({
  page,
  pageDurationFrames,
  fontFamily,
  fontSize,
  fontWeight,
  textColor,
  letterSpacing,
  textShadow,
  lineHeight,
  blurAmount,
  blurDurationMs,
  enableScale,
  scaleFrom,
  maxWordsPerLine,
  lineGap,
  exitDurationMs,
  lowercase,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Current time in ms relative to page start
  const pageLocalMs = (frame / fps) * 1000;

  // ── Page exit: reverse blur in the final exitDurationMs ────────────────
  const exitStartMs = page.durationMs - exitDurationMs;

  const exitBlur = interpolate(
    pageLocalMs,
    [exitStartMs, page.durationMs],
    [0, blurAmount],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const exitOpacity = interpolate(
    pageLocalMs,
    [exitStartMs, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // ── Split tokens into lines ───────────────────────────────────────────
  const lines: TikTokToken[][] = [];
  for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
    lines.push(page.tokens.slice(i, i + maxWordsPerLine));
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: lineGap,
        width: "100%",
        filter: `blur(${exitBlur}px)`,
        opacity: exitOpacity,
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
          {lineTokens.map((token, tokenIdx) => (
            <div
              key={`${lineIdx}-${tokenIdx}`}
              style={{ padding: "0 10px" }}
            >
              <LetterpressWord
                token={token}
                pageStartMs={page.startMs}
                fontFamily={fontFamily}
                fontSize={fontSize}
                fontWeight={fontWeight}
                textColor={textColor}
                letterSpacing={letterSpacing}
                textShadow={textShadow}
                lineHeight={lineHeight}
                blurAmount={blurAmount}
                blurDurationMs={blurDurationMs}
                enableScale={enableScale}
                scaleFrom={scaleFrom}
                lowercase={lowercase}
              />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

// ── CinematicLetterpress (main export) ────────────────────────────────────

export const CinematicLetterpress: React.FC<CinematicLetterpressProps> = ({
  pages,
  fontFamily = CAPTION_FONTS.cormorantGaramond,
  fontSize = 62,
  fontWeight = 300,
  position = "bottom",
  textColor = "#F5F0EB",
  letterSpacing = "0.12em",
  blurAmount = 8,
  blurDurationMs = 200,
  enableScale = true,
  scaleFrom = 0.95,
  textShadow = "0 0 40px rgba(0,0,0,0.3), 0 0 80px rgba(0,0,0,0.15)",
  maxWordsPerLine = 3,
  lineGap = 12,
  exitDurationMs = 250,
  lowercase = false,
  lineHeight = 1.2,
}) => {
  const { fps, width } = useVideoConfig();

  // ── Position styling ──────────────────────────────────────────────────
  const maxWidth = width * 0.85;

  let positionStyles: React.CSSProperties;
  switch (position) {
    case "top":
      positionStyles = {
        position: "absolute",
        left: "50%",
        top: CAPTION_PADDING.top,
        transform: "translateX(-50%)",
      };
      break;
    case "center":
      positionStyles = {
        position: "absolute",
        left: "50%",
        top: "50%",
        transform: "translate(-50%, -50%)",
      };
      break;
    case "bottom":
    default:
      positionStyles = {
        position: "absolute",
        left: "50%",
        bottom: CAPTION_PADDING.bottomSafe,
        transform: "translateX(-50%)",
      };
      break;
  }

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
            <AbsoluteFill>
              <div
                style={{
                  ...positionStyles,
                  maxWidth,
                  width: "max-content",
                  textAlign: "center",
                }}
              >
                <LetterpressPage
                  page={page}
                  pageDurationFrames={durationFrames}
                  fontFamily={fontFamily}
                  fontSize={fontSize}
                  fontWeight={fontWeight}
                  textColor={textColor}
                  letterSpacing={letterSpacing}
                  textShadow={textShadow}
                  lineHeight={lineHeight}
                  blurAmount={blurAmount}
                  blurDurationMs={blurDurationMs}
                  enableScale={enableScale}
                  scaleFrom={scaleFrom}
                  maxWordsPerLine={maxWordsPerLine}
                  lineGap={lineGap}
                  exitDurationMs={exitDurationMs}
                  lowercase={lowercase}
                />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
