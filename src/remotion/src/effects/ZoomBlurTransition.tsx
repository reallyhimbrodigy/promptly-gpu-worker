import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Zoom blur transition overlay — radial blur effect that simulates
 * a camera zoom during cuts. Creates a professional motion blur feel.
 */
export const ZoomBlurTransition: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const intensity = (params.intensity as number) || 0.6;
  const color = (params.color as string) || "dark";

  const dur = end - start;
  const mid = start + dur / 2;

  // Peak at midpoint of transition
  const alpha = interpolate(
    t,
    [start, mid, end],
    [0, intensity, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.cubic),
    }
  );

  if (alpha <= 0.01) return null;

  const blurAmount = alpha * 20;
  const scaleAmount = 1 + alpha * 0.15;

  const bgColors: Record<string, string> = {
    dark: `rgba(0,0,0,${alpha * 0.5})`,
    warm: `rgba(40,20,0,${alpha * 0.4})`,
    cool: `rgba(0,10,30,${alpha * 0.4})`,
  };

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Radial gradient simulating zoom blur */}
      <div
        style={{
          position: "absolute",
          inset: "-10%",
          background: `radial-gradient(circle at 50% 50%, transparent 30%, ${bgColors[color] || bgColors.dark} 100%)`,
          transform: `scale(${scaleAmount})`,
          filter: `blur(${blurAmount}px)`,
        }}
      />
      {/* Speed lines */}
      {Array.from({ length: 12 }).map((_, i) => {
        const angle = (i / 12) * 360;
        const lineAlpha = alpha * 0.3 * (0.5 + Math.sin(i * 2.5) * 0.5);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              width: "200%",
              height: 2,
              backgroundColor: `rgba(255,255,255,${lineAlpha})`,
              transform: `translate(-50%, -50%) rotate(${angle}deg)`,
              transformOrigin: "center",
              filter: `blur(${1 + alpha * 3}px)`,
            }}
          />
        );
      })}
    </div>
  );
};
