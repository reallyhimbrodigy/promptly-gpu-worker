import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Color flash/wash — brief color tint that washes over the frame.
 * Used for mood shifts, transitions, or beat-synced pulses.
 */
export const ColorFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const color = (params.color as string) || "cyan";
  const intensity = (params.intensity as number) || 0.25;
  const blendMode = (params.blendMode as string) || "overlay";

  const dur = end - start;
  const alpha = interpolate(
    t,
    [start, start + dur * 0.15, end - dur * 0.4, end],
    [0, intensity, intensity * 0.6, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0.01) return null;

  const colors: Record<string, string> = {
    cyan: `rgba(0,200,220,${alpha})`,
    pink: `rgba(255,60,130,${alpha})`,
    gold: `rgba(255,200,0,${alpha})`,
    purple: `rgba(130,50,255,${alpha})`,
    teal: `rgba(0,180,180,${alpha})`,
    orange: `rgba(255,120,0,${alpha})`,
    blue: `rgba(50,100,255,${alpha})`,
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: colors[color] || colors.cyan,
        mixBlendMode: blendMode as React.CSSProperties["mixBlendMode"],
      }}
    />
  );
};
