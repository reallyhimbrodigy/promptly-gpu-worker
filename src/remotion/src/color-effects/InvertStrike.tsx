import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface InvertStrikeProps {
  children: React.ReactNode;
  // How strong the inversion is at peak 0..1. Default 1.
  intensity?: number;
  // Timing. Pulsed mode is the recommended usage — one strike per beat.
  timing: ColorTimingMode;
  // Add a contrast punch at peak. Default true.
  punch?: boolean;
}

// Negative strike: color-inverts the footage on beat for a single-frame
// editorial punch. Uses CSS invert() so it's lossless and instant. Optional
// contrast punch adds bite so the inversion reads as design, not a glitch.
export const InvertStrike: React.FC<InvertStrikeProps> = ({
  children,
  intensity = 1,
  timing,
  punch = true,
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 1,
    defaultHoldFrames: 2,
    defaultReleaseFrames: 6,
    defaultFadeInFrames: 2,
  });

  const contrast = punch ? 1 + 0.25 * k : 1;
  const saturation = 1 - 0.35 * k; // slight desat when inverted — avoids neon

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `invert(${k}) contrast(${contrast}) saturate(${saturation})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Thin edge flare on the strike to add weight */}
      <ColorEffectLayer
        style={{
          boxShadow: `inset 0 0 80px rgba(255,255,255,${0.35 * k})`,
          opacity: interpolate(k, [0, 0.3, 1], [0, 1, 1]),
        }}
      />
    </AbsoluteFill>
  );
};
