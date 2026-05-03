import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  interpolateColors,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { PaperIIProps } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

// ---------------------------------------------------------------------------
// PaperIIWord
// ---------------------------------------------------------------------------

const PaperIIWord: React.FC<{
  token: TikTokToken;
  pageStartMs: number;
  upcomingColor: string;
  activeColor: string;
  allCaps: boolean;
  fontSize: number;
  fontFamily: string;
  fontWeight: number | string;
  letterSpacing: string;
  colorTransitionMs: number;
  textShadow: string;
}> = ({
  token,
  pageStartMs,
  upcomingColor,
  activeColor,
  allCaps,
  fontSize,
  fontFamily,
  fontWeight,
  letterSpacing,
  colorTransitionMs,
  textShadow,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentTimeMs = (frame / fps) * 1000 + pageStartMs;
  const isPast = currentTimeMs >= token.toMs;

  // Smooth color transition over colorTransitionMs
  const transitionProgress = interpolate(
    currentTimeMs,
    [token.fromMs, token.fromMs + colorTransitionMs],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const color =
    transitionProgress >= 1 || isPast
      ? activeColor
      : interpolateColors(transitionProgress, [0, 1], [upcomingColor, activeColor]);

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily,
        fontSize,
        fontWeight,
        color,
        textTransform: allCaps ? "uppercase" : "none",
        letterSpacing,
        lineHeight: 1.15,
        whiteSpace: "nowrap",
        textShadow,
        // Universal stroke for guaranteed readability over any background.
        WebkitTextStroke: "0.75px rgba(0,0,0,0.6)",
      }}
    >
      {token.text}
    </span>
  );
};

// ---------------------------------------------------------------------------
// PaperIIStrip — one rounded white strip containing one line of words
// ---------------------------------------------------------------------------

const PaperIIStrip: React.FC<{
  tokens: TikTokToken[];
  pageStartMs: number;
  paperColor: string;
  upcomingColor: string;
  activeColor: string;
  allCaps: boolean;
  fontSize: number;
  fontFamily: string;
  fontWeight: number | string;
  letterSpacing: string;
  colorTransitionMs: number;
  stripPaddingX: number;
  stripPaddingY: number;
  borderRadius: number;
  textShadow: string;
}> = ({
  tokens,
  pageStartMs,
  paperColor,
  upcomingColor,
  activeColor,
  allCaps,
  fontSize,
  fontFamily,
  fontWeight,
  letterSpacing,
  colorTransitionMs,
  stripPaddingX,
  stripPaddingY,
  borderRadius,
  textShadow,
}) => {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        background: paperColor,
        padding: `${stripPaddingY}px ${stripPaddingX}px`,
        borderRadius,
      }}
    >
      {tokens.map((token, idx) => (
        <PaperIIWord
          key={idx}
          token={token}
          pageStartMs={pageStartMs}
          upcomingColor={upcomingColor}
          activeColor={activeColor}
          allCaps={allCaps}
          fontSize={fontSize}
          fontFamily={fontFamily}
          fontWeight={fontWeight}
          letterSpacing={letterSpacing}
          colorTransitionMs={colorTransitionMs}
          textShadow={textShadow}
        />
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// PaperIIPage — one caption page (Sequence), splits tokens into strip lines
// ---------------------------------------------------------------------------

const PaperIIPage: React.FC<{
  page: TikTokPage;
  maxWordsPerLine: number;
  stripGap: number;
  paperColor: string;
  upcomingColor: string;
  activeColor: string;
  allCaps: boolean;
  fontSize: number;
  fontFamily: string;
  fontWeight: number | string;
  letterSpacing: string;
  colorTransitionMs: number;
  stripPaddingX: number;
  stripPaddingY: number;
  borderRadius: number;
  textShadow: string;
}> = ({
  page,
  maxWordsPerLine,
  stripGap,
  ...stripProps
}) => {
  // Split tokens into lines
  const lines: TikTokToken[][] = [];
  for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
    lines.push(page.tokens.slice(i, i + maxWordsPerLine));
  }

  // Hard cut on/off — no fade. Captions snap to the spoken word.
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: stripGap,
      }}
    >
      {lines.map((lineTokens, lineIdx) => (
        <PaperIIStrip
          key={lineIdx}
          tokens={lineTokens}
          pageStartMs={page.startMs}
          {...stripProps}
        />
      ))}
    </div>
  );
};

// ---------------------------------------------------------------------------
// PaperII — main exported component
// ---------------------------------------------------------------------------

export const PaperII: React.FC<PaperIIProps> = ({
  pages,
  paperColor = "transparent",
  upcomingColor = "rgba(255,255,255,0.45)",
  activeColor = "#FFFFFF",
  fontFamily = CAPTION_FONTS.lora,
  fontSize = 68,
  fontWeight = 700,
  position = "bottom",
  maxWordsPerLine = 4,
  allCaps = false,
  letterSpacing = "-0.01em",
  stripPaddingX = 0,
  stripPaddingY = 0,
  stripGap = 10,
  borderRadius = 0,
  colorTransitionMs = 60,
  textShadow = "0 2px 10px rgba(0,0,0,0.8), 0 0 3px rgba(0,0,0,0.5)",
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;
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
              <div style={{ maxWidth, width: "100%" }}>
                <PaperIIPage
                  page={page}
                  maxWordsPerLine={maxWordsPerLine}
                  stripGap={stripGap}
                  paperColor={paperColor}
                  upcomingColor={upcomingColor}
                  activeColor={activeColor}
                  allCaps={allCaps}
                  fontSize={fontSize}
                  fontFamily={fontFamily}
                  fontWeight={fontWeight}
                  letterSpacing={letterSpacing}
                  colorTransitionMs={colorTransitionMs}
                  stripPaddingX={stripPaddingX}
                  stripPaddingY={stripPaddingY}
                  borderRadius={borderRadius}
                  textShadow={textShadow}
                />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}

    </AbsoluteFill>
  );
};
