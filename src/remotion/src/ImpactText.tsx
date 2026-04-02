import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import type { VisualEffect } from "./types";

/**
 * ImpactText — Full-screen large bold text overlay.
 *
 * Captions AI uses this for dramatic feature callouts:
 * - V1: "#1 EDITING HACK" (cyan/teal, 3D look)
 * - V2: "EASY EDITING", "CREATE CONTENT" (neon yellow-green, scanline texture)
 * - V4: "dynamic transitions", "visual effects" (white + yellow two-tone)
 *
 * Supports:
 * - Single line or two-line layout
 * - Two-tone coloring (word1 in color1, word2 in color2)
 * - Optional scanline texture effect
 * - Spring-animated entrance with scale pop
 *
 * params.text: the text to display (use \n for line break)
 * params.color1: color for first line/word (default: white)
 * params.color2: color for second line/word (default: #FFD700 gold)
 * params.position: "top" | "center" | "bottom" (default: "top")
 * params.scanlines: whether to add scanline texture (default: false)
 */
export const ImpactText: React.FC<{ effect: VisualEffect }> = ({
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

  const text = (effect.params?.text as string) || "IMPACT";
  const color1 = (effect.params?.color1 as string) || "#FFFFFF";
  const color2 = (effect.params?.color2 as string) || "#FFD700";
  const position = (effect.params?.position as string) || "top";
  const scanlines = !!effect.params?.scanlines;

  // Fade envelope
  const fadeIn = interpolate(progress, [0, 0.15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(progress, [0.8, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;
  if (opacity <= 0) return null;

  // Spring entrance
  const age = Math.max(0, frame - Math.round(start * fps));
  const entranceSpring = spring({
    frame: age,
    fps,
    config: { damping: 11, stiffness: 160, mass: 0.7 },
  });
  const scale = interpolate(entranceSpring, [0, 1], [0.7, 1]);
  const translateY = interpolate(entranceSpring, [0, 1], [30, 0]);

  // Split text into lines
  const lines = text.split("\n").filter((l) => l.trim());
  const fontSize = Math.round(
    width * (lines.length > 1 ? 0.12 : 0.15)
  );

  // Position
  let topPct: string;
  if (position === "center") topPct = "40%";
  else if (position === "bottom") topPct = "60%";
  else topPct = "15%"; // top

  const lineElements = lines.map((line, i) => {
    const color = i === 0 ? color1 : color2;
    const lineStyle: React.CSSProperties = {
      fontSize: i === 0 && lines.length > 1 ? fontSize : Math.round(fontSize * 1.15),
      fontFamily: "Montserrat",
      fontWeight: 900,
      fontStyle: "normal",
      textTransform: "uppercase",
      textAlign: "center",
      whiteSpace: "nowrap",
      lineHeight: 1.1,
      color,
      WebkitTextStroke: "2px rgba(0,0,0,0.8)",
      textShadow: [
        `0 0 ${Math.round(fontSize * 0.08)}px ${color}80`,
        `0 0 ${Math.round(fontSize * 0.2)}px ${color}40`,
        `0 4px 12px rgba(0,0,0,0.6)`,
      ].join(", "),
      letterSpacing: "0.03em",
      willChange: "transform",
    };

    // Scanline texture: horizontal stripes via repeating gradient on text
    if (scanlines) {
      lineStyle.background = `repeating-linear-gradient(
        0deg,
        ${color} 0px,
        ${color} 3px,
        transparent 3px,
        transparent 6px
      )`;
      lineStyle.WebkitBackgroundClip = "text";
      lineStyle.WebkitTextFillColor = "transparent";
      // Keep the stroke visible through the scanlines
      lineStyle.WebkitTextStroke = `1.5px ${color}`;
    }

    return (
      <div key={i} style={lineStyle}>
        {line}
      </div>
    );
  });

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: topPct,
        opacity,
        transform: `scale(${scale.toFixed(3)}) translateY(${translateY.toFixed(1)}px)`,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "8px",
        willChange: "transform, opacity",
      }}
    >
      {lineElements}
    </div>
  );
};
