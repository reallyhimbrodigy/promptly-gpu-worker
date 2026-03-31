import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Vignette pulse — edges darken dramatically for a brief moment on emphasis.
 * Draws viewer attention to the center. Professional drama technique.
 */
export const VignettePulse: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const intensity = (params.intensity as number) || 0.6;
  const color = (params.color as string) || "black";

  const dur = end - start;
  const alpha = interpolate(
    t,
    [start, start + dur * 0.2, end - dur * 0.4, end],
    [0, intensity, intensity * 0.7, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0.01) return null;

  const vignetteColors: Record<string, string> = {
    black: `rgba(0,0,0,${alpha})`,
    warm: `rgba(40,10,0,${alpha})`,
    cool: `rgba(0,10,30,${alpha})`,
    red: `rgba(60,0,0,${alpha})`,
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(ellipse at 50% 50%, transparent 40%, ${vignetteColors[color] || vignetteColors.black} 100%)`,
      }}
    />
  );
};
