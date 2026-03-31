import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Subtle progress bar at top or bottom of frame.
 * Shows video progress — increases watch time by signaling content length.
 */
export const ProgressBar: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const position = (params.position as string) || "top";
  const color = (params.color as string) || "#FFFFFF";
  const height = (params.height as number) || 3;
  const opacity = (params.opacity as number) || 0.6;

  const progress = interpolate(t, [start, end], [0, 100], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Fade in/out
  const alpha = interpolate(
    t,
    [start, start + 0.3, end - 0.3, end],
    [0, opacity, opacity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        [position === "bottom" ? "bottom" : "top"]: 0,
        height,
        backgroundColor: "rgba(255,255,255,0.15)",
        opacity: alpha,
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress}%`,
          backgroundColor: color,
          borderRadius: position === "bottom" ? "0 2px 0 0" : "0 0 2px 0",
          boxShadow: `0 0 8px ${color}40`,
          transition: "width 0.033s linear",
        }}
      />
    </div>
  );
};
