import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  spring,
  interpolate,
} from "remotion";
import type { TikTokPage, TikTokToken } from "../shared/types";
import type { PrismProps } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { fitFontSize } from "../shared/fitText";
import { isPrismKeyword } from "./prismKeywords";

/** Build the per-word highlight check. When `keywords` has at least one
 *  entry we use it as the source of truth (case-insensitive, punctuation-
 *  stripped match) — that's the production path where Gemini supplies
 *  contextual keywords for THIS specific video. When empty / undefined we
 *  fall back to the bundled static dictionary so the component still works
 *  in isolation. */
function buildKeywordCheck(keywords?: string[]): (word: string) => boolean {
  if (!keywords || keywords.length === 0) return isPrismKeyword;
  const normalized = new Set<string>();
  for (const k of keywords) {
    if (typeof k !== "string") continue;
    const norm = k.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (norm) normalized.add(norm);
  }
  if (normalized.size === 0) return isPrismKeyword;
  return (word: string) => {
    const key = word.toLowerCase().replace(/[^a-z0-9]/g, "");
    return key.length > 0 && normalized.has(key);
  };
}

/* ─── Helpers ─── */

interface Line {
  tokens: TikTokToken[];
  startMs: number;
  endMs: number;
}

function splitIntoLines(page: TikTokPage, maxWordsPerLine: number): Line[] {
  const lines: Line[] = [];
  for (let i = 0; i < page.tokens.length; i += maxWordsPerLine) {
    const tokens = page.tokens.slice(i, i + maxWordsPerLine);
    lines.push({
      tokens,
      startMs: tokens[0].fromMs,
      endMs: tokens[tokens.length - 1].toMs,
    });
  }
  for (let i = 0; i < lines.length - 1; i++) {
    lines[i].endMs = lines[i + 1].startMs;
  }
  if (lines.length > 0) {
    lines[lines.length - 1].endMs = page.startMs + page.durationMs;
  }
  return lines;
}

/* ─── Word Component ─── */

const PrismWord: React.FC<{
  token: TikTokToken;
  lineStartFrame: number;
  fontSize: number;
  isKeyword: boolean;
  keywordScale: number;
  color: string;
  visible: boolean;
  wordIndex: number;
  maxWidth: number;
}> = ({ token, lineStartFrame, fontSize, isKeyword, keywordScale, color, visible, wordIndex, maxWidth }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const triggerFrame = msToFrames(token.fromMs, fps) - lineStartFrame;
  const elapsed = frame - triggerFrame;
  const hasAppeared = elapsed >= 0;

  // Normal: smooth left-to-right slide
  // Keywords: subtle bottom-to-top rise
  const revealSpring = hasAppeared
    ? spring({
        fps,
        frame: elapsed,
        config: isKeyword
          ? { mass: 0.5, damping: 18, stiffness: 160 }
          : { mass: 0.5, damping: 20, stiffness: 140 },
      })
    : 0;

  const offsetX = isKeyword
    ? 0
    : interpolate(revealSpring, [0, 1], [-18, 0], { extrapolateRight: "clamp" });

  const offsetY = isKeyword
    ? interpolate(revealSpring, [0, 1], [12, 0], { extrapolateRight: "clamp" })
    : 0;

  const opacity = interpolate(revealSpring, [0, 0.25, 1], [0, 0.85, 1], {
    extrapolateRight: "clamp",
  });

  // Auto-fit so a long keyword word never overflows the line container.
  // Without this, the browser crops at the canvas edge.
  const requestedSize = isKeyword ? fontSize * keywordScale : fontSize * 0.92;
  const renderedText = isKeyword ? token.text.toUpperCase() : token.text;
  const wordFontSize = React.useMemo(
    () =>
      fitFontSize(renderedText, requestedSize, maxWidth, {
        fontFamily: isKeyword ? CAPTION_FONTS.montserrat : CAPTION_FONTS.poppins,
        fontWeight: isKeyword ? 900 : 400,
        fontStyle: isKeyword ? "italic" : "normal",
      }),
    [renderedText, requestedSize, maxWidth, isKeyword],
  );

  return (
    <div style={{ padding: "0 8px", position: "relative" }}>
      {visible && !isKeyword && (
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            width: "140%",
            height: "220%",
            transform: `translate(calc(-50% + ${offsetX}px), calc(-50% + ${offsetY}px))`,
            borderRadius: "50%",
            background: "radial-gradient(ellipse at center, rgba(0,0,0,0.18) 0%, rgba(0,0,0,0) 60%)",
            filter: "blur(8px)",
            opacity,
            pointerEvents: "none",
          }}
        />
      )}
      <span
        style={{
          display: "inline-block",
          position: "relative",
          fontFamily: isKeyword ? CAPTION_FONTS.montserrat : CAPTION_FONTS.poppins,
          fontStyle: isKeyword ? "italic" : "normal",
          fontWeight: isKeyword ? 900 : 400,
          fontSize: wordFontSize,
          textTransform: isKeyword ? "uppercase" : "none",
          letterSpacing: isKeyword ? "-0.05em" : "-0.09em",
          lineHeight: 1,
          color: visible ? color : "transparent",
          transform: `translate(${offsetX}px, ${offsetY}px)`,
          opacity,
          whiteSpace: "nowrap",
        }}
      >
        {token.text}
      </span>
    </div>
  );
};

/* ─── Single Line Component ─── */

const PrismLine: React.FC<{
  line: Line;
  lineStartFrame: number;
  fontSize: number;
  maxWidth: number;
  keywordScale: number;
  soloKeywordScale: number;
  color: string;
  mode: "normal" | "keywords";
  keywordCheck: (word: string) => boolean;
}> = ({ line, lineStartFrame, fontSize, maxWidth, keywordScale, soloKeywordScale, color, mode, keywordCheck }) => {
  const isSoloKeyword = line.tokens.length === 1 && keywordCheck(line.tokens[0].text);
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "row",
        alignItems: "baseline",
        justifyContent: "center",
        flexWrap: "wrap",
        maxWidth,
        gap: 0,
      }}
    >
{line.tokens.map((token, idx) => {
        const isKeyword = keywordCheck(token.text);
        const visible =
          (mode === "normal" && !isKeyword) || (mode === "keywords" && isKeyword);

        return (
          <PrismWord
            key={idx}
            token={token}
            lineStartFrame={lineStartFrame}
            fontSize={fontSize}
            isKeyword={isKeyword}
            keywordScale={isSoloKeyword ? soloKeywordScale : keywordScale}
            color={visible ? color : "transparent"}
            visible={visible}
            wordIndex={idx}
            maxWidth={maxWidth}
          />
        );
      })}
    </div>
  );
};

/* ─── Main Component ─── */

export const Prism: React.FC<PrismProps> = ({
  pages,
  fontSize = 100,
  position = "bottom",
  maxWidthPercent = 0.85,
  maxWordsPerLine = 4,
  keywordScale = 1.6,
  soloKeywordScale = 2.2,
  keywords,
}) => {
  const { fps, width } = useVideoConfig();
  const frame = useCurrentFrame();
  const maxWidth = width * maxWidthPercent;
  const keywordCheck = React.useMemo(() => buildKeywordCheck(keywords), [keywords]);

  const positionStyle: React.CSSProperties = getCaptionPositionStyle(position);

  const allLines: Line[] = [];
  for (const page of pages) {
    allLines.push(...splitIntoLines(page, maxWordsPerLine));
  }

  const activeLine = allLines.find((line) => {
    const startFrame = msToFrames(line.startMs, fps);
    const endFrame = msToFrames(line.endMs, fps);
    return frame >= startFrame && frame < endFrame;
  });

  if (!activeLine) return null;

  const lineStartFrame = msToFrames(activeLine.startMs, fps);
  const lineDurationFrames = msToFrames(activeLine.endMs, fps) - lineStartFrame;
  const hasKeywords = activeLine.tokens.some((t) => keywordCheck(t.text));

  // Page-boundary fade: 3 frames (~50 ms at 60fps). Audio-sync trumps
  // smoothness — captions need to land ON the spoken word, not trail it.
  // Longer fades (10+ frames / 167+ ms) made captions feel laggy.
  const fadeFrames = 3;
  const lineEndFrame = lineStartFrame + lineDurationFrames;
  const fadeIn = interpolate(
    frame,
    [lineStartFrame, lineStartFrame + fadeFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const fadeOut = interpolate(
    frame,
    [lineEndFrame - fadeFrames, lineEndFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const lineOpacity = fadeIn * fadeOut;

  const layerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    opacity: lineOpacity,
    ...positionStyle,
  };

  const lineProps = {
    line: activeLine,
    lineStartFrame,
    fontSize,
    maxWidth,
    keywordScale,
    soloKeywordScale,
    keywordCheck,
  };

  return (
    <>
      {/* Normal words: white with shadow */}
      <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
        <AbsoluteFill style={layerStyle}>
          <PrismLine {...lineProps} color="#FFFFFF" mode="normal" />
        </AbsoluteFill>
      </Sequence>

      {/* Keyword words: pure negative invert */}
      {hasKeywords && (
        <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
          <AbsoluteFill style={{ ...layerStyle, mixBlendMode: "difference" }}>
            <PrismLine {...lineProps} color="#FFFFFF" mode="keywords" />
          </AbsoluteFill>
        </Sequence>
      )}
    </>
  );
};
