import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import type { VisualEffect } from "./types";

/**
 * CascadeEcho — Captions AI's dramatic emphasis effect.
 *
 * A single word repeated 5 times vertically, stacked from top to bottom,
 * each repetition with decreasing opacity. The text cascades in from top
 * with a staggered spring animation.
 *
 * Observed in V1: "SKEPTIC" x5, "RESULT" x5
 * Observed in V2: "SECONDS" x7, "EDITING" x5+
 * Observed in V3: (not used)
 * Observed in V4: (not used — uses ImpactText instead)
 *
 * params.word: the word to display
 * params.color: primary color (default: cyan #00D4FF)
 * params.outlineColor: stroke color (default: same as color)
 * params.rows: number of repetitions (default: 5)
 * params.italic: whether to use italic (default: true)
 */
export const CascadeEcho: React.FC<{ effect: VisualEffect }> = ({
  effect,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;

  const word = (effect.params?.word as string) || "IMPACT";
  const color = (effect.params?.color as string) || "#00D4FF";
  const outlineColor = (effect.params?.outlineColor as string) || color;
  const rows = (effect.params?.rows as number) || 5;
  const italic = effect.params?.italic !== false;

  // Overall fade envelope: quick fade in, hold, fade out
  const fadeIn = interpolate(progress, [0, 0.12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(progress, [0.8, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;
  if (opacity <= 0) return null;

  // Font size: fill ~60% of width
  const fontSize = Math.round(width * 0.18);
  const lineHeight = fontSize * 1.05;

  // Each row cascades in with staggered spring
  const age = Math.max(0, frame - Math.round(start * fps));

  const rowElements = Array.from({ length: rows }, (_, i) => {
    // Stagger: each row starts 2 frames after the previous
    const rowAge = Math.max(0, age - i * 2);
    const rowSpring = spring({
      frame: rowAge,
      fps,
      config: { damping: 12, stiffness: 180, mass: 0.6 },
    });

    // Opacity: top row = full, bottom row = very faint
    const rowOpacity = interpolate(i, [0, rows - 1], [1, 0.08]);

    // Scale entrance: start slightly larger, settle to 1.0
    const scale = interpolate(rowSpring, [0, 1], [1.15, 1]);
    // Slide in from slightly above
    const translateY = interpolate(rowSpring, [0, 1], [-20, 0]);

    // Style variations per row:
    // Row 0: filled with color
    // Row 1-2: filled with slightly dimmer color
    // Row 3+: outline only (stroke, no fill)
    const isOutline = i >= Math.ceil(rows * 0.6);

    const rowStyle: React.CSSProperties = {
      fontSize,
      fontFamily: "Montserrat",
      fontWeight: 900,
      fontStyle: italic ? "italic" : "normal",
      textTransform: "uppercase",
      textAlign: "center",
      whiteSpace: "nowrap",
      lineHeight: 1,
      opacity: rowOpacity * rowSpring,
      transform: `scale(${scale.toFixed(3)}) translateY(${translateY.toFixed(1)}px)`,
      // willChange removed for faster compositing
      letterSpacing: "0.02em",
    };

    if (isOutline) {
      // Outline-only: thicker stroke + glow for visibility
      rowStyle.WebkitTextStroke = `3px ${outlineColor}`;
      rowStyle.WebkitTextFillColor = "transparent";
      rowStyle.textShadow = [
        `0 0 ${Math.round(fontSize * 0.12)}px ${color}50`,
        `0 0 ${Math.round(fontSize * 0.06)}px ${color}30`,
      ].join(", ");
    } else {
      // Filled: solid color with strong glow + black outline for readability
      rowStyle.color = color;
      rowStyle.WebkitTextStroke = `2px rgba(0,0,0,0.6)`;
      rowStyle.textShadow = [
        `0 0 ${Math.round(fontSize * 0.12)}px ${color}90`,
        `0 0 ${Math.round(fontSize * 0.25)}px ${color}50`,
        `0 3px 10px rgba(0,0,0,0.8)`,
      ].join(", ");
    }

    return (
      <div key={i} style={rowStyle}>
        {word}
      </div>
    );
  });

  // Container: positioned in upper 2/3 of frame, centered
  const totalHeight = rows * lineHeight;
  const topOffset = Math.max(
    height * 0.08,
    (height * 0.65 - totalHeight) / 2
  );

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: topOffset,
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: `${Math.round(lineHeight * 0.05)}px`,
        // willChange removed for faster compositing
      }}
    >
      {rowElements}
    </div>
  );
};
