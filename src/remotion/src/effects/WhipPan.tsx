import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Whip pan transition — horizontal motion blur with directional streak.
 * Simulates a fast camera pan between shots. Professional transition technique.
 */
export const WhipPan: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const direction = (params.direction as string) || "right";
  const intensity = (params.intensity as number) || 0.7;

  const dur = end - start;
  const mid = start + dur / 2;

  // Peaks at midpoint
  const alpha = interpolate(
    t,
    [start, mid, end],
    [0, intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0.01) return null;

  const blurX = alpha * 40;
  const shiftX = direction === "right" ? alpha * 30 : -alpha * 30;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Motion blur streaks */}
      <div
        style={{
          position: "absolute",
          inset: "-20%",
          background: `linear-gradient(${direction === "right" ? "90deg" : "270deg"},
            transparent 0%,
            rgba(0,0,0,${alpha * 0.5}) 30%,
            rgba(0,0,0,${alpha * 0.7}) 50%,
            rgba(0,0,0,${alpha * 0.5}) 70%,
            transparent 100%)`,
          transform: `translateX(${shiftX}px)`,
          filter: `blur(${blurX}px)`,
        }}
      />
      {/* Speed streaks */}
      {Array.from({ length: 8 }).map((_, i) => {
        const y = 10 + (i / 8) * 80;
        const lineAlpha = alpha * (0.2 + Math.sin(i * 3) * 0.15);
        const lineWidth = 40 + Math.sin(i * 2) * 20;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: direction === "right" ? `${50 + shiftX / 3}%` : "auto",
              right: direction === "left" ? `${50 - shiftX / 3}%` : "auto",
              top: `${y}%`,
              width: `${lineWidth}%`,
              height: 1.5,
              backgroundColor: `rgba(255,255,255,${lineAlpha})`,
              filter: `blur(${2 + alpha * 5}px)`,
              transform: `translateX(${shiftX * 2}px)`,
            }}
          />
        );
      })}
    </div>
  );
};
