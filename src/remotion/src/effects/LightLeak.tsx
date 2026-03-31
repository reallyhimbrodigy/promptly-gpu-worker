import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Cinematic light leak overlay — warm/cool gradient streaks that
 * drift across the frame. Gives footage that anamorphic lens feel.
 */
export const LightLeak: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const color = (params.color as string) || "warm";
  const intensity = (params.intensity as number) || 0.4;

  // Fade envelope
  const dur = end - start;
  const fadeIn = Math.min(0.3, dur * 0.2);
  const fadeOut = Math.min(0.4, dur * 0.25);
  const alpha = interpolate(
    t,
    [start, start + fadeIn, end - fadeOut, end],
    [0, intensity, intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0) return null;

  // Drift animation
  const progress = interpolate(t, [start, end], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const drift = Math.sin(progress * Math.PI * 2) * 20;
  const drift2 = Math.cos(progress * Math.PI * 1.5) * 15;

  const gradients: Record<string, string> = {
    warm: `radial-gradient(ellipse at ${30 + drift}% ${20 + drift2}%, rgba(255,180,50,${alpha}) 0%, rgba(255,100,30,${alpha * 0.5}) 40%, transparent 70%),
           radial-gradient(ellipse at ${70 - drift}% ${60 + drift2}%, rgba(255,200,100,${alpha * 0.6}) 0%, transparent 60%)`,
    cool: `radial-gradient(ellipse at ${25 + drift}% ${30 + drift2}%, rgba(100,150,255,${alpha}) 0%, rgba(50,100,200,${alpha * 0.5}) 40%, transparent 70%),
           radial-gradient(ellipse at ${75 - drift}% ${50 + drift2}%, rgba(150,200,255,${alpha * 0.5}) 0%, transparent 60%)`,
    golden: `radial-gradient(ellipse at ${20 + drift}% ${25 + drift2}%, rgba(255,215,0,${alpha}) 0%, rgba(255,165,0,${alpha * 0.4}) 45%, transparent 75%),
             radial-gradient(ellipse at ${80 - drift}% ${70 + drift2}%, rgba(255,230,100,${alpha * 0.5}) 0%, transparent 55%)`,
    prismatic: `radial-gradient(ellipse at ${30 + drift}% ${20 + drift2}%, rgba(255,100,150,${alpha * 0.8}) 0%, transparent 50%),
                radial-gradient(ellipse at ${60 - drift}% ${40 + drift2}%, rgba(100,200,255,${alpha * 0.6}) 0%, transparent 50%),
                radial-gradient(ellipse at ${80 + drift}% ${70 - drift2}%, rgba(255,220,50,${alpha * 0.7}) 0%, transparent 50%)`,
  };

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundImage: gradients[color] || gradients.warm,
        mixBlendMode: "screen",
        willChange: "opacity",
      }}
    />
  );
};
