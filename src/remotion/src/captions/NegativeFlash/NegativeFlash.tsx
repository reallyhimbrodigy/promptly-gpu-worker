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
import { fitFontSize } from "../shared/fitText";
import { textOutline } from "../shared/textOutline";
import { isNegativeKeyword } from "./negativeKeywords";

/** Build the per-word highlight check. When `keywords` has at least one
 *  entry we use it as the source of truth (case-insensitive, punctuation-
 *  stripped match) — that's the production path where Gemini supplies
 *  contextual keywords for THIS specific video. When empty / undefined we
 *  fall back to the bundled static dictionary so the component still works
 *  in isolation (e.g. standalone storybook, unit tests). */
function buildKeywordCheck(keywords?: string[]): (word: string) => boolean {
  if (!keywords || keywords.length === 0) return isNegativeKeyword;
  const normalized = new Set<string>();
  for (const k of keywords) {
    if (typeof k !== "string") continue;
    const norm = k.toLowerCase().replace(/[^a-z0-9]/g, "");
    if (norm) normalized.add(norm);
  }
  if (normalized.size === 0) return isNegativeKeyword;
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
  maxWidth: number;
}> = ({ token, lineStartFrame, fontSize, isKeyword, keywordScale, color, spreadColor, visible, wordByWord, maxWidth }) => {
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

  // Auto-fit so a long keyword word (e.g. "ELECTROCUTED" at 1.6× scale)
  // never overflows the line container. Without this, the browser crops
  // at the canvas edge — visible to the user as both sides chopped off.
  // The word's text is uppercased for keywords; measure the rendered
  // form so the fit is accurate.
  const requestedSize = isKeyword ? fontSize * keywordScale : fontSize;
  const renderedText = isKeyword ? token.text.toUpperCase() : token.text;
  const wordFontSize = React.useMemo(
    () =>
      fitFontSize(renderedText, requestedSize, maxWidth, {
        fontFamily: CAPTION_FONTS.montserrat,
        fontWeight: 900,
      }),
    [renderedText, requestedSize, maxWidth],
  );

  // Universal readability: every visible word gets a dark outline + soft
  // shadow that holds up over any background (speaker face, B-roll
  // cutaway, light footage). The outline is rendered as an 8-direction
  // text-shadow rather than WebkitTextStroke — strokes are single-sampled
  // along the letter contour and break under fractional `transform: scale`
  // (sub-pixel coverage at W/A/V apexes leaves "triangle" notches mid-
  // entrance-spring). The 8-direction shadow is multi-sampled, so apex
  // joins survive any transform. Visual appearance at fontSize 80+ is
  // sub-pixel-identical to a 1px stroke. The keyword spread-glow stacks
  // on top.
  const baseShadow = "0 2px 6px rgba(0,0,0,0.55), 0 0 2px rgba(0,0,0,0.85)";
  const outlineShadow = textOutline(1, "rgba(0,0,0,0.7)");
  const composedShadow = visible
    ? spreadColor
      ? `${baseShadow}, ${outlineShadow}, 0 0 3px ${spreadColor}, 0 0 3px ${spreadColor}`
      : `${baseShadow}, ${outlineShadow}`
    : "none";

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
          textShadow: composedShadow,
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
  keywordCheck: (word: string) => boolean;
}> = ({ line, lineStartFrame, fontSize, maxWidth, keywordScale, color, spreadColor, mode, keywordCheck }) => {
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

        // wordByWord is always true so every word springs at its own
        // triggerFrame. Previously this was gated on `hasKeywords`, which
        // meant lines without a keyword sprang every word synchronously
        // off the line's frame=0 — visually identical to a page-level
        // fade-in, which is exactly what we don't want. Per-word stagger
        // is the entire entrance animation we keep.
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
            wordByWord={true}
            maxWidth={maxWidth}
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
  keywords,
}) => {
  const preset = NEGATIVE_FLASH_PRESETS[colorPreset] ?? NEGATIVE_FLASH_PRESETS.red;
  const keywordCheck = React.useMemo(() => buildKeywordCheck(keywords), [keywords]);
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
  const hasKeywords = activeLine.tokens.some((t) => keywordCheck(t.text));

  // Hard cut on/off — no fade. Captions snap to the spoken word the way
  // professional caption tools (captions.ai, etc.) render them. At 60fps
  // even a 1-frame fade is 16.67ms which exceeds the user's 10ms ceiling
  // and produces a perceptible halo at page boundaries.
  const lineOpacity = 1;

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
    keywordCheck,
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
