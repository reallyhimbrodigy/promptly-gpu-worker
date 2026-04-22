import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface DreamHazeProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Dreamy nostalgic pass: lifted blacks, soft highlight bloom, pastel
// desaturation. Uses a blurred second copy of the footage composited via
// screen to get that diffusion look without a hard "Instagram filter" feel.
export const DreamHaze: React.FC<DreamHazeProps> = ({
  children,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 8,
    defaultHoldFrames: 14,
    defaultReleaseFrames: 14,
    defaultFadeInFrames: 24,
  });

  const saturation = 1 - 0.28 * k;
  const contrast = 1 - 0.12 * k;
  const brightness = 1 + 0.05 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `saturate(${saturation}) contrast(${contrast}) brightness(${brightness})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Diffusion: blurred copy via screen lifts highlights, softens edges */}
      <AbsoluteFill
        style={{
          filter: `blur(${14 * k}px) brightness(1.12)`,
          mixBlendMode: "screen",
          opacity: 0.45 * k,
          pointerEvents: "none",
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Pastel pink/peach wash */}
      <ColorEffectLayer
        style={{
          background:
            "linear-gradient(180deg, rgba(255,205,195,0.25) 0%, rgba(220,215,240,0.25) 100%)",
          mixBlendMode: "soft-light",
          opacity: 0.9 * k,
        }}
      />

      {/* Lifted blacks: a low-opacity off-white wash */}
      <ColorEffectLayer
        style={{
          background: "rgba(240,232,222,0.18)",
          mixBlendMode: "screen",
          opacity: k,
        }}
      />
    </AbsoluteFill>
  );
};
