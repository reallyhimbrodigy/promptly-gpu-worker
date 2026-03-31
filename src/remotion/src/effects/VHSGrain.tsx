import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * VHS/film grain overlay — scanlines, noise, and color aberration.
 * Adds retro/analog texture. Great for nostalgic or dramatic vibes.
 */
export const VHSGrain: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const intensity = (params.intensity as number) || 0.3;
  const style = (params.style as string) || "film"; // film, vhs, digital

  const alpha = interpolate(
    t,
    [start, start + 0.2, end - 0.2, end],
    [0, intensity, intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  if (alpha <= 0.01) return null;

  // Pseudo-random noise pattern that changes every frame
  const noiseOpacity = alpha * 0.15;
  const seed = frame * 7919; // prime for variation

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Film grain noise via CSS */}
      <div
        style={{
          position: "absolute",
          inset: "-50%",
          width: "200%",
          height: "200%",
          background: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
          opacity: noiseOpacity,
          transform: `translate(${(seed % 50) - 25}px, ${((seed * 3) % 50) - 25}px)`,
          mixBlendMode: "overlay",
        }}
      />

      {/* Scanlines */}
      {(style === "vhs" || style === "film") && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `repeating-linear-gradient(
              0deg,
              transparent,
              transparent 2px,
              rgba(0,0,0,${alpha * 0.06}) 2px,
              rgba(0,0,0,${alpha * 0.06}) 4px
            )`,
          }}
        />
      )}

      {/* VHS color fringing */}
      {style === "vhs" && (
        <>
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: `rgba(255,0,50,${alpha * 0.04})`,
              transform: "translateX(2px)",
              mixBlendMode: "screen",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: `rgba(0,100,255,${alpha * 0.04})`,
              transform: "translateX(-2px)",
              mixBlendMode: "screen",
            }}
          />
          {/* VHS tracking line */}
          {Math.sin(seed * 0.01) > 0.7 && (
            <div
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: `${((seed * 0.013) % 1) * 100}%`,
                height: 3,
                backgroundColor: `rgba(255,255,255,${alpha * 0.3})`,
                filter: "blur(1px)",
              }}
            />
          )}
        </>
      )}
    </div>
  );
};
