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
import { CAPTION_FONTS } from "../shared/fonts";
import { getCaptionPositionStyle } from "../shared/captionPosition";

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

  // Hard cut on/off — no fade. Captions snap to the spoken word.
  const opacity = 1;

  return (
    <AbsoluteFill
      style={{
        ...getCaptionPositionStyle(position),
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
            fontSize,
            lineHeight: 0.9,
            letterSpacing: "-0.06em",
            whiteSpace: "nowrap",
            color: "rgba(0,0,0,0.4)",
            filter: "blur(10px)",
            transform: `scaleY(${stretchY})`,
            transformOrigin: "center bottom",
            textAlign: "center",
            pointerEvents: "none",
          }}
        >
          {toTitleCase(activeSlot.token.text)}
        </span>
        <span
          style={{
            display: "inline-block",
            position: "relative",
            fontFamily: CAPTION_FONTS.playfairDisplay,
            fontWeight: 700,
            fontSize,
            color,
            lineHeight: 0.9,
            letterSpacing: "-0.06em",
            whiteSpace: "nowrap",
            transform: `scaleY(${stretchY})`,
            transformOrigin: "center bottom",
            textAlign: "center",
            // Universal stroke for guaranteed readability over any background.
            WebkitTextStroke: "1px rgba(0,0,0,0.55)",
            textShadow: "0 2px 8px rgba(0,0,0,0.5), 0 0 2px rgba(0,0,0,0.7)",
          }}
        >
          {toTitleCase(activeSlot.token.text)}
        </span>
      </div>
    </AbsoluteFill>
  );
};
