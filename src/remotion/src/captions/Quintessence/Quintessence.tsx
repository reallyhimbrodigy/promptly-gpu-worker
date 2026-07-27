import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import type { TikTokToken, TikTokPage } from "../shared/types";
import type { QuintessenceProps } from "./types";
import { msToFrames } from "../shared/timing";
import { boundedFade } from "../shared/fadeTiming";
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";
import { fitScale, CHARWRAP_FALLBACK_STYLE } from "../shared/fit";

/* ─── Helpers ─── */

interface WordSlot {
  token: TikTokToken;
  startMs: number;
  endMs: number;
}

function toTitleCase(text: string): string {
  return text.replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildWordSlots(pages: TikTokPage[]): WordSlot[] {
  const slots: WordSlot[] = [];
  for (const page of pages) {
    for (let i = 0; i < page.tokens.length; i++) {
      const token = page.tokens[i];
      const next = page.tokens[i + 1];
      slots.push({
        token,
        startMs: token.fromMs,
        endMs: next ? next.fromMs : page.startMs + page.durationMs,
      });
    }
  }
  return slots;
}

/* ─── Main Component ─── */

export const Quintessence: React.FC<QuintessenceProps> = ({
  pages,
  fontSize = 160,
  position = "bottom",
  anchor,
  color = "#E8D44D",
  stretchY = 1.6,
}) => {
  const { fps, width } = useVideoConfig();
  const frame = useCurrentFrame();
  const maxWidth = width * 0.85;

  const slots = buildWordSlots(pages);

  const activeSlot = slots.find((slot) => {
    const startFrame = msToFrames(slot.startMs, fps);
    const endFrame = msToFrames(slot.endMs, fps);
    return frame >= startFrame && frame < endFrame;
  });

  if (!activeSlot) return null;

  const startFrame = msToFrames(activeSlot.startMs, fps);
  const endFrame = msToFrames(activeSlot.endMs, fps);
  const elapsed = frame - startFrame;

  // WS2 fade-bound: a slot's fade never eats more than 25% of the slot window,
  // so fast-speech slots are legible ≥75% of their life (shared/fadeTiming).
  const slotWinF = endFrame - startFrame;

  // CRISP ENTRANCE (Zac 2026-07-13): the word appears at FULL opacity the instant
  // its slot is active — no fade-in ramp (the ghost). Its character is the monumental
  // scaleY stretch + one-word frame, not a soft fade. `elapsed >= 0` gates presence.
  const enteredOpacity = elapsed >= 0 ? 1 : 0;

  // Quick fade out (kept — the exit is not the entrance ghost)
  const fadeOutFrames = boundedFade(3, slotWinF);
  const fadeOut = interpolate(
    frame,
    [endFrame - fadeOutFrames, endFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const opacity = enteredOpacity * fadeOut;

  // F4 width-fit guarantee: one 160px Playfair word, nowrap — the worst
  // single-word overflow risk of the pack. Uniform scale to the margins;
  // below the floor the spans char-break (the blurred scrim twin mirrors).
  const displayText = toTitleCase(activeSlot.token.text);
  const fit = fitScale(
    [
      {
        parts: [
          {
            text: displayText,
            fontSize,
            font: {
              fontFamily: CAPTION_FONTS.playfairDisplay,
              fontWeight: 700,
              letterSpacingEm: -0.06,
            },
          },
        ],
      },
    ],
    maxWidth,
    "Quintessence",
  );
  const fittedFontSize = fontSize * fit.scale;
  const fitFallback = fit.floored ? CHARWRAP_FALLBACK_STYLE : {};

  return (
    <AbsoluteFill
      style={{
        ...getCaptionPositionStyle(position, anchor),
        alignItems: "center",
        opacity,
      }}
    >
      <div style={{ position: "relative", display: "inline-block", maxWidth }}>
        {/* Word-shaped blurred shadow below */}
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            fontFamily: CAPTION_FONTS.playfairDisplay,
            fontWeight: 700,
            fontSize: fittedFontSize,
            lineHeight: 0.9,
            letterSpacing: "-0.06em",
            whiteSpace: "nowrap",
            color: "rgba(0,0,0,0.4)",
            filter: "blur(10px)",
            transform: `scaleY(${stretchY})`,
            transformOrigin: "center bottom",
            textAlign: "center",
            pointerEvents: "none",
            ...fitFallback,
          }}
        >
          {displayText}
        </span>
        <span
          style={{
            display: "inline-block",
            position: "relative",
            fontFamily: CAPTION_FONTS.playfairDisplay,
            fontWeight: 700,
            fontSize: fittedFontSize,
            color,
            lineHeight: 0.9,
            letterSpacing: "-0.06em",
            whiteSpace: "nowrap",
            transform: `scaleY(${stretchY})`,
            transformOrigin: "center bottom",
            textAlign: "center",
            ...fitFallback,
          }}
        >
          {displayText}
        </span>
      </div>
    </AbsoluteFill>
  );
};
