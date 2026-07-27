import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokPage } from "../shared/types";
import type { TypewriterRevealProps, TypewriterColorScheme } from "./types";
import { TYPEWRITER_SCHEMES } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { boundedFade } from "../shared/fadeTiming";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";

function resolveScheme(
  scheme: TypewriterRevealProps["scheme"],
  custom?: Partial<TypewriterColorScheme>,
): TypewriterColorScheme {
  if (scheme === "custom" && custom) {
    return {
      textColor: custom.textColor ?? "#FFFFFF",
      bgColor: custom.bgColor ?? "rgba(0,0,0,0.8)",
      cursorColor: custom.cursorColor ?? custom.textColor ?? "#FFFFFF",
    };
  }
  const key = scheme ?? "classic";
  if (key === "custom") return TYPEWRITER_SCHEMES.classic;
  return TYPEWRITER_SCHEMES[key];
}

function buildCharTimings(
  page: TikTokPage,
  lowercase: boolean,
): { text: string; timings: number[] } {
  const parts: string[] = [];
  const timings: number[] = [];

  for (let ti = 0; ti < page.tokens.length; ti++) {
    const token = page.tokens[ti];
    const word = lowercase ? token.text.toLowerCase() : token.text;

    if (ti > 0) {
      parts.push(" ");
      timings.push(page.tokens[ti - 1].toMs);
    }

    const charCount = word.length;
    for (let ci = 0; ci < charCount; ci++) {
      parts.push(word[ci]);
      timings.push(
        token.fromMs + (ci / charCount) * (token.toMs - token.fromMs),
      );
    }
  }

  return { text: parts.join(""), timings };
}

/** A single page with character-by-character typewriter reveal */
const TypewriterPage: React.FC<{
  page: TikTokPage;
  colors: TypewriterColorScheme;
  fontSize: number;
  fontFamily: string;
  letterSpacing: string;
  lineHeight: number;
  lowercase: boolean;
  showCursor: boolean;
  cursorBlinkMs: number;
  enableBox: boolean;
  boxBorderRadius: number;
  maxWidth: number;
  fadeInDurationMs: number;
  fadeOutDurationMs: number;
}> = ({
  page,
  colors,
  fontSize,
  fontFamily,
  letterSpacing,
  lineHeight,
  lowercase,
  showCursor,
  cursorBlinkMs,
  enableBox,
  boxBorderRadius,
  maxWidth,
  fadeInDurationMs,
  fadeOutDurationMs,
}) => {
  // Inside Sequence: frame is relative to Sequence start
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (frame < 0) return null; // intentional premount guard (repo-side; changelogged directive #12)

  // Absolute time for character timing lookups
  const currentTimeMs = page.startMs + (frame / fps) * 1000;

  const { text, timings } = useMemo(
    () => buildCharTimings(page, lowercase),
    [page, lowercase],
  );

  // F4 width-fit guarantee: pre-wrap breaks at spaces, so the overflow unit
  // is the longest word (mono glyphs, wide). Scale it into the box; below
  // the floor the container gets overflowWrap:anywhere (per-char spans give
  // CSS clean break points).
  const fit = fitScale(
    text
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => ({
        parts: [
          {
            text: w,
            fontSize,
            font: { fontFamily, fontWeight: 600, letterSpacingEm: 0.03 },
          },
        ],
      })),
    maxWidth,
    "TypewriterReveal",
  );
  const fittedFontSize = fontSize * fit.scale;

  // CRISP ENTRANCE (Zac 2026-07-13): the page is at FULL opacity from frame 1 — no
  // fade-in ramp (the ghost). TypewriterReveal's identity IS the per-character typing
  // (chars hard-appear as they're "typed", never fade); the page fade-OUT stays.
  const pageLocalMs = (frame / fps) * 1000;
  const fadeOutMs = boundedFade(fadeOutDurationMs, page.durationMs);
  const fadeOutStart = page.durationMs - fadeOutMs;
  const fadeOut = interpolate(
    pageLocalMs,
    [fadeOutStart, page.durationMs],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const pageOpacity = fadeOut;

  // Find last revealed character
  let lastRevealedIdx = -1;
  for (let i = 0; i < timings.length; i++) {
    if (currentTimeMs >= timings[i]) {
      lastRevealedIdx = i;
    } else {
      break;
    }
  }

  // Cursor blink
  const blinkCycleFrames = Math.max(2, Math.round((cursorBlinkMs / 1000) * fps));
  const cursorVisible = showCursor && (frame % blinkCycleFrames) < blinkCycleFrames / 2;

  const charStyle: React.CSSProperties = {
    fontFamily,
    fontSize: fittedFontSize,
    fontWeight: 600, // directive #12: was 400
    letterSpacing,
    lineHeight,
    whiteSpace: "pre-wrap",
    textShadow: [
      // directive #12: real stroke under the mono glyphs (4-direction)
      "-1.5px -1.5px 0 rgba(0,0,0,0.9)",
      "1.5px -1.5px 0 rgba(0,0,0,0.9)",
      "-1.5px 1.5px 0 rgba(0,0,0,0.9)",
      "1.5px 1.5px 0 rgba(0,0,0,0.9)",
      "0 2px 4px rgba(0,0,0,0.9)",
      "0 0 8px rgba(0,0,0,0.8)",
      "0 0 20px rgba(0,0,0,0.6)",
      "0 0 40px rgba(0,0,0,0.4)",
      "0 4px 12px rgba(0,0,0,0.5)",
    ].join(", "),
  };

  return (
    <div style={{ opacity: pageOpacity, display: "flex", justifyContent: "center", width: "100%" }}>
      <div
        style={{
          ...(enableBox
            ? { background: colors.bgColor, borderRadius: boxBorderRadius, padding: "16px 24px" }
            : {}),
          maxWidth,
          textAlign: "center",
          ...(fit.floored ? CHARWRAP_FALLBACK_STYLE : {}),
        }}
      >
        {text.split("").map((char, i) => {
          const isRevealed = i <= lastRevealedIdx;
          const isCursorPos = i === lastRevealedIdx + 1;

          return (
            <React.Fragment key={i}>
              {isCursorPos && showCursor && (
                <span style={{ ...charStyle, color: colors.cursorColor, opacity: cursorVisible ? 1 : 0 }}>|</span>
              )}
              <span style={{ ...charStyle, color: colors.textColor, opacity: isRevealed ? 1 : 0 }}>{char}</span>
            </React.Fragment>
          );
        })}
        {lastRevealedIdx === text.length - 1 && showCursor && (
          <span style={{ ...charStyle, color: colors.cursorColor, opacity: cursorVisible ? 1 : 0 }}>|</span>
        )}
      </div>
    </div>
  );
};

export const TypewriterReveal: React.FC<TypewriterRevealProps> = ({
  pages,
  scheme = "classic",
  customColors,
  fontSize = 62, // directive #12: bumped from 48 — mono identity was too faint at phone scale
  fontFamily = CAPTION_FONTS.spaceMono,
  position = "bottom",
  anchor,
  showCursor = true,
  cursorBlinkMs = 530,
  enableBox = false,
  lowercase = true,
  letterSpacing = "0.03em",
  lineHeight = 1.4,
  fadeInDurationMs = 90, // WS2 faster base (was 150); further capped to 25% of the page window
  fadeOutDurationMs = 90, // WS2 faster base (was 150)
  boxBorderRadius = 8,
  maxWidthPercent = 0.85,
}) => {
  const { fps, width } = useVideoConfig();
  const maxWidth = width * maxWidthPercent;

  const colors = useMemo(
    () => resolveScheme(scheme, customColors),
    [scheme, customColors],
  );

  const positionStyle = getCaptionPositionStyle(position, anchor);

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
            name={page.tokens.map((t) => t.text).join(" ")}
          >
            <AbsoluteFill
              style={{
                display: "flex",
                alignItems: "center",
                ...positionStyle,
              }}
            >
              <div style={{ position: "absolute", width: "calc(100% - 120px)" }}>
                <TypewriterPage
                  page={page}
                  colors={colors}
                  fontSize={fontSize}
                  fontFamily={fontFamily}
                  letterSpacing={letterSpacing}
                  lineHeight={lineHeight}
                  lowercase={lowercase}
                  showCursor={showCursor}
                  cursorBlinkMs={cursorBlinkMs}
                  enableBox={enableBox}
                  boxBorderRadius={boxBorderRadius}
                  maxWidth={maxWidth}
                  fadeInDurationMs={fadeInDurationMs}
                  fadeOutDurationMs={fadeOutDurationMs}
                />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
