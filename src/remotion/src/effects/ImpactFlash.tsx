import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Impact flash — a quick white/color flash that fires on emphasis moments.
 * Professional editors use this to punctuate hard cuts and punchlines.
 * Duration: 0.05-0.15s.
 */
export const ImpactFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const color = (params.color as string) || "white";
  const intensity = (params.intensity as number) || 0.7;

  const dur = end - start;
  // Very fast attack (10% of duration), slower decay
  const alpha = interpolate(
    t,
    [start, start + dur * 0.1, end],
    [0, intensity, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    }
  );

  if (alpha <= 0.01) return null;

  const colors: Record<string, string> = {
    white: `rgba(255,255,255,${alpha})`,
    warm: `rgba(255,230,180,${alpha})`,
    cool: `rgba(200,220,255,${alpha})`,
    red: `rgba(255,80,80,${alpha})`,
    gold: `rgba(255,215,0,${alpha})`,
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: colors[color] || colors.white,
        mixBlendMode: "screen",
      }}
    />
  );
};
