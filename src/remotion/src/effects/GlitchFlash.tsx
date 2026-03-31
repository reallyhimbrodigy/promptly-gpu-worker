import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Digital glitch effect — RGB channel split + scan lines + horizontal
 * displacement. Fires on hard cuts and emphasis moments.
 * Duration: ~0.1-0.2s burst.
 */
export const GlitchFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const intensity = (params.intensity as number) || 0.8;
  const color = (params.color as string) || "rgb";

  const dur = end - start;
  const progress = interpolate(t, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Sharp attack, quick decay
  const alpha = interpolate(
    t,
    [start, start + dur * 0.1, end - dur * 0.3, end],
    [0, intensity, intensity * 0.5, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0.01) return null;

  // Pseudo-random offsets based on frame for jitter
  const seed = frame * 13.37;
  const jitter1 = Math.sin(seed) * 15 * alpha;
  const jitter2 = Math.cos(seed * 0.7) * 10 * alpha;
  const jitter3 = Math.sin(seed * 1.3) * 8 * alpha;

  // Scanline density varies with intensity
  const scanlineSize = 3 + Math.floor(Math.sin(seed * 0.5) * 2);

  const colorShifts: Record<string, [string, string]> = {
    rgb: ["rgba(255,0,50,0.4)", "rgba(0,200,255,0.4)"],
    cyan: ["rgba(0,255,200,0.5)", "rgba(255,0,100,0.3)"],
    purple: ["rgba(150,0,255,0.4)", "rgba(0,255,150,0.3)"],
  };

  const [color1, color2] = colorShifts[color] || colorShifts.rgb;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* RGB channel split layers */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: color1,
          transform: `translateX(${jitter1}px)`,
          mixBlendMode: "screen",
          opacity: alpha,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundColor: color2,
          transform: `translateX(${-jitter2}px) translateY(${jitter3}px)`,
          mixBlendMode: "screen",
          opacity: alpha * 0.8,
        }}
      />

      {/* Horizontal displacement bars */}
      {Array.from({ length: 6 }).map((_, i) => {
        const barY = ((seed * (i + 1) * 0.17) % 1) * 100;
        const barH = 2 + (i % 3) * 3;
        const barShift = Math.sin(seed * (i + 1)) * 30 * alpha;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: `${barY}%`,
              height: `${barH}px`,
              backgroundColor: `rgba(255,255,255,${0.15 * alpha})`,
              transform: `translateX(${barShift}px)`,
            }}
          />
        );
      })}

      {/* Scanlines */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `repeating-linear-gradient(
            0deg,
            transparent,
            transparent ${scanlineSize}px,
            rgba(0,0,0,${0.08 * alpha}) ${scanlineSize}px,
            rgba(0,0,0,${0.08 * alpha}) ${scanlineSize + 1}px
          )`,
        }}
      />
    </div>
  );
};
