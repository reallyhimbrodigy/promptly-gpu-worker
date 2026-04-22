import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface VignettePulseProps {
  children: React.ReactNode;
  // Base vignette darkness 0..1 (before pulse adds on top). Default 0.35.
  baseDarkness?: number;
  // Base vignette softness — where the fade starts as % of radius. Default 55.
  baseInnerPct?: number;
  // Vignette color. Default black.
  color?: string;
  // Peak additional darkness at pulse peak 0..1. Default 0.6.
  intensity?: number;
  // When mode='pulsed' the vignette tightens/darkens on each beat.
  // When 'persistent' it just fades in and sits.
  timing?: ColorTimingMode;
}

// Two-stack vignette: a constant base vignette for cinematic framing plus
// a pulsed darker/tighter vignette that breathes with emphasis. The pulsed
// layer not only darkens but also shrinks its inner radius, so it "closes
// in" on the subject rather than just getting darker.
export const VignettePulse: React.FC<VignettePulseProps> = ({
  children,
  baseDarkness = 0.35,
  baseInnerPct = 55,
  color = "#000000",
  intensity = 0.6,
  timing = { mode: "persistent" },
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 5,
    defaultHoldFrames: 8,
    defaultReleaseFrames: 12,
    defaultFadeInFrames: 16,
  });

  // Pulsed vignette tightens from 55% → 25% inner radius at peak
  const pulseInner = baseInnerPct - 30 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill>{children}</AbsoluteFill>

      {/* Base vignette — always on once mounted */}
      <ColorEffectLayer
        style={{
          background: `radial-gradient(ellipse at 50% 50%, transparent ${baseInnerPct}%, ${color} 105%)`,
          opacity: baseDarkness,
        }}
      />

      {/* Pulsed layer — tightens and darkens on beats */}
      <ColorEffectLayer
        style={{
          background: `radial-gradient(ellipse at 50% 50%, transparent ${pulseInner}%, ${color} 100%)`,
          opacity: k,
        }}
      />
    </AbsoluteFill>
  );
};
