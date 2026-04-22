import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface BleachBypassProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Silver retention / bleach bypass: desaturated, contrasty, with a soft
// silver sheen. Looks like a thriller or prestige documentary. Achieved
// by compositing a desaturated B&W pass over the original via soft-light.
export const BleachBypass: React.FC<BleachBypassProps> = ({
  children,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 6,
    defaultHoldFrames: 12,
    defaultReleaseFrames: 10,
    defaultFadeInFrames: 18,
  });

  const saturation = 1 - 0.55 * k;
  const contrast = 1 + 0.28 * k;
  const brightness = 1 + 0.04 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `saturate(${saturation}) contrast(${contrast}) brightness(${brightness})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Silver sheen layer: contrast-boosted B&W pass via soft-light */}
      <AbsoluteFill
        style={{
          filter: `grayscale(1) contrast(${1 + 0.4 * k})`,
          mixBlendMode: "soft-light",
          opacity: 0.75 * k,
          pointerEvents: "none",
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Slight cool cast in shadows (silver halide) */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, rgba(210,218,228,0.0) 40%, rgba(45,60,78,0.35) 100%)",
          mixBlendMode: "multiply",
          opacity: 0.7 * k,
        }}
      />
    </AbsoluteFill>
  );
};
