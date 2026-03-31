import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Cinematic letterbox bars — black bars slide in from top/bottom.
 * Instantly makes footage feel like a movie. Great for dramatic moments.
 */
export const LetterboxCinematic: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps, height } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const barHeight = (params.barHeight as number) || 0.12; // fraction of height
  const barPx = barHeight * height;

  const dur = end - start;
  const slideIn = Math.min(0.4, dur * 0.15);
  const slideOut = Math.min(0.4, dur * 0.15);

  const progress = interpolate(
    t,
    [start, start + slideIn, end - slideOut, end],
    [0, 1, 1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.cubic),
    }
  );

  if (progress <= 0) return null;

  const currentBar = barPx * progress;

  return (
    <>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: currentBar,
          backgroundColor: "black",
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: currentBar,
          backgroundColor: "black",
        }}
      />
    </>
  );
};
