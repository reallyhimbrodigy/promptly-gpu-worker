import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Animated emoji that pops in with spring bounce on emphasis moments.
 * Commonly used in TikTok/Reels style edits for reactions.
 */
export const EmojiPop: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const emoji = (params.emoji as string) || "🔥";
  const size = (params.size as number) || 120;
  const x = (params.x as number) || 0.5; // 0-1 relative
  const y = (params.y as number) || 0.3; // 0-1 relative

  const dur = end - start;
  const age = t - start;

  if (t < start || t > end) return null;

  // Spring pop-in
  const springVal = spring({
    frame: Math.max(0, frame - Math.round(start * fps)),
    fps,
    config: { damping: 10, stiffness: 200, mass: 0.8 },
  });

  const scale = interpolate(springVal, [0, 1], [0, 1.2]);
  const settleScale = age > 0.2 ? interpolate(
    age, [0.2, 0.35], [1.2, 1.0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  ) : scale;

  // Gentle float
  const floatY = Math.sin(age * 3) * 5;
  const floatRot = Math.sin(age * 2) * 8;

  // Fade out
  const fadeOut = interpolate(
    t, [end - 0.2, end], [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        left: `${x * 100}%`,
        top: `${y * 100}%`,
        transform: `translate(-50%, -50%) scale(${settleScale}) translateY(${floatY}px) rotate(${floatRot}deg)`,
        fontSize: size,
        opacity: fadeOut,
        filter: "drop-shadow(0 4px 12px rgba(0,0,0,0.3))",
        willChange: "transform, opacity",
      }}
    >
      {emoji}
    </div>
  );
};
