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
import { isPrismKeyword } from "./prismKeywords";

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
}> = ({ token, lineStartFrame, fontSize, isKeyword, keywordScale, color, visible, wordIndex }) => {
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

  const wordFontSize = isKeyword ? fontSize * keywordScale : fontSize * 0.92;

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
}> = ({ line, lineStartFrame, fontSize, maxWidth, keywordScale, soloKeywordScale, color, mode }) => {
  const isSoloKeyword = line.tokens.length === 1 && isPrismKeyword(line.tokens[0].text);
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
        const isKeyword = isPrismKeyword(token.text);
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
}) => {
  const { fps, width } = useVideoConfig();
  const frame = useCurrentFrame();
  const maxWidth = width * maxWidthPercent;

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
  const hasKeywords = activeLine.tokens.some((t) => isPrismKeyword(t.text));

  // Fade out last ~5 frames of the line
  const fadeOutFrames = 5;
  const lineEndFrame = lineStartFrame + lineDurationFrames;
  const lineOpacity = interpolate(
    frame,
    [lineEndFrame - fadeOutFrames, lineEndFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

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
