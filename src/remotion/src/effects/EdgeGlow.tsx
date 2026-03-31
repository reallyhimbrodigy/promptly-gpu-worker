import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Edge glow — colored glow around the frame edges, pulsing on beats
 * or during emphasis moments. Adds energy and visual polish.
 */
export const EdgeGlow: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const color = (params.color as string) || "cyan";
  const intensity = (params.intensity as number) || 0.5;
  const pulse = (params.pulse as boolean) ?? true;

  const dur = end - start;
  const age = t - start;

  let alpha = interpolate(
    t,
    [start, start + 0.15, end - 0.2, end],
    [0, intensity, intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Subtle pulse
  if (pulse) {
    alpha *= 0.7 + Math.sin(age * 4) * 0.3;
  }

  if (alpha <= 0.01) return null;

  const colors: Record<string, string> = {
    cyan: `rgba(0,220,220,${alpha})`,
    pink: `rgba(255,50,150,${alpha})`,
    gold: `rgba(255,200,0,${alpha})`,
    purple: `rgba(150,50,255,${alpha})`,
    white: `rgba(255,255,255,${alpha})`,
    blue: `rgba(50,100,255,${alpha})`,
    red: `rgba(255,50,50,${alpha})`,
  };

  const glowColor = colors[color] || colors.cyan;
  const spread = 30 + alpha * 40;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        boxShadow: `inset 0 0 ${spread}px ${glowColor},
                     inset 0 0 ${spread * 2}px ${glowColor.replace(String(alpha), String(alpha * 0.3))}`,
        pointerEvents: "none",
      }}
    />
  );
};
