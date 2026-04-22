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
import type { NegativeFlashProps } from "./types";
import { NEGATIVE_FLASH_PRESETS } from "./types";
import { msToFrames } from "../shared/timing";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { isNegativeKeyword } from "./negativeKeywords";

/* ─── Helpers ─── */

interface Line {
  tokens: TikTokToken[];
  startMs: number;
  endMs: number;
}

/** Split a page's tokens into single-line chunks with computed timing. */
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
  // Each line stays visible until the next line starts (or page ends)
  for (let i = 0; i < lines.length - 1; i++) {
    lines[i].endMs = lines[i + 1].startMs;
  }
  // Last line stays until page ends
  if (lines.length > 0) {
    lines[lines.length - 1].endMs = page.startMs + page.durationMs;
  }
  return lines;
}

/* ─── Word Component ─── */

const NegativeWord: React.FC<{
  token: TikTokToken;
  lineStartFrame: number;
  fontSize: number;
  isKeyword: boolean;
  keywordScale: number;
  color: string;
  spreadColor?: string;
  visible: boolean;
  wordByWord: boolean;
}> = ({ token, lineStartFrame, fontSize, isKeyword, keywordScale, color, spreadColor, visible, wordByWord }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const triggerFrame = msToFrames(token.fromMs, fps) - lineStartFrame;
  const elapsed = frame - triggerFrame;
  const hasAppeared = wordByWord ? elapsed >= 0 : true;

  const revealSpring = hasAppeared
    ? spring({
        fps,
        frame: wordByWord ? elapsed : frame,
        config: { mass: 0.4, damping: 10, stiffness: 220 },
      })
    : 0;

  const scale = interpolate(revealSpring, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  const wordFontSize = isKeyword ? fontSize * keywordScale : fontSize;

  return (
    <div style={{ padding: "0 8px" }}>
      <span
        style={{
          display: "inline-block",
          fontFamily: CAPTION_FONTS.montserrat,
          fontWeight: 900,
          fontSize: wordFontSize,
          textTransform: isKeyword ? "uppercase" : "none",
          letterSpacing: "0.04em",
          lineHeight: 1,
          color: visible ? color : "transparent",
          textShadow:
            visible && spreadColor
              ? `0 0 3px ${spreadColor}, 0 0 3px ${spreadColor}`
              : "none",
          transform: `scale(${scale})`,
          transformOrigin: "center bottom",
          whiteSpace: "nowrap",
        }}
      >
        {token.text}
      </span>
    </div>
  );
};

/* ─── Single Line Component ─── */

const NegativeLine: React.FC<{
  line: Line;
  lineStartFrame: number;
  fontSize: number;
  maxWidth: number;
  keywordScale: number;
  color: string;
  spreadColor?: string;
  mode: "normal" | "keywords";
}> = ({ line, lineStartFrame, fontSize, maxWidth, keywordScale, color, spreadColor, mode }) => {
  const hasKeywords = line.tokens.some((t) => isNegativeKeyword(t.text));

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
        const isKeyword = isNegativeKeyword(token.text);
        const visible =
          (mode === "normal" && !isKeyword) || (mode === "keywords" && isKeyword);

        return (
          <NegativeWord
            key={idx}
            token={token}
            lineStartFrame={lineStartFrame}
            fontSize={fontSize}
            isKeyword={isKeyword}
            keywordScale={keywordScale}
            color={visible ? color : "transparent"}
            spreadColor={visible ? spreadColor : undefined}
            visible={visible}
            wordByWord={hasKeywords}
          />
        );
      })}
    </div>
  );
};

/* ─── Main Component ─── */

export const NegativeFlash: React.FC<NegativeFlashProps> = ({
  pages,
  fontSize = 80,
  position = "bottom",
  maxWidthPercent = 0.85,
  maxWordsPerLine = 4,
  keywordScale = 1.6,
  colorPreset = "red",
}) => {
  const preset = NEGATIVE_FLASH_PRESETS[colorPreset] ?? NEGATIVE_FLASH_PRESETS.red;
  const { fps, width } = useVideoConfig();
  const frame = useCurrentFrame();
  const maxWidth = width * maxWidthPercent;

  const positionStyle: React.CSSProperties = getCaptionPositionStyle(position);

  // Flatten all pages into single lines with timing
  const allLines: Line[] = [];
  for (const page of pages) {
    allLines.push(...splitIntoLines(page, maxWordsPerLine));
  }

  // Find the active line at current frame
  const activeLine = allLines.find((line) => {
    const startFrame = msToFrames(line.startMs, fps);
    const endFrame = msToFrames(line.endMs, fps);
    return frame >= startFrame && frame < endFrame;
  });

  if (!activeLine) return null;

  const lineStartFrame = msToFrames(activeLine.startMs, fps);
  const lineDurationFrames = msToFrames(activeLine.endMs, fps) - lineStartFrame;
  const hasKeywords = activeLine.tokens.some((t) => isNegativeKeyword(t.text));

  const layerStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    ...positionStyle,
  };

  const lineProps = {
    line: activeLine,
    lineStartFrame,
    fontSize,
    maxWidth,
    keywordScale,
  };

  return (
    <>
      {/* Normal words: plain white */}
      <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
        <AbsoluteFill style={layerStyle}>
          <NegativeLine {...lineProps} color="#FFFFFF" mode="normal" />
        </AbsoluteFill>
      </Sequence>

      {/* Keyword words: negative invert effect (three blend layers) */}
      {hasKeywords && (
        <>
          {/* Layer 1: Invert */}
          <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
            <AbsoluteFill style={{ ...layerStyle, mixBlendMode: "difference" }}>
              <NegativeLine {...lineProps} color="#FFFFFF" mode="keywords" />
            </AbsoluteFill>
          </Sequence>

          {/* Layer 2: Tint + darken */}
          <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
            <AbsoluteFill style={{ ...layerStyle, mixBlendMode: "multiply" }}>
              <NegativeLine
                {...lineProps}
                color={preset.tintColor}
                spreadColor={preset.glowColor}
                mode="keywords"
              />
            </AbsoluteFill>
          </Sequence>

          {/* Layer 3: Burn for aggressive contrast */}
          <Sequence premountFor={10} from={lineStartFrame} durationInFrames={lineDurationFrames}>
            <AbsoluteFill style={{ ...layerStyle, mixBlendMode: "color-burn" }}>
              <NegativeLine
                {...lineProps}
                color={preset.burnColor}
                mode="keywords"
              />
            </AbsoluteFill>
          </Sequence>
        </>
      )}
    </>
  );
};
