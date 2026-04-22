import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, random } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface CineMonoProps {
  children: React.ReactNode;
  // Red/green/blue weights for the B&W conversion (must sum near 1).
  // Defaults weighted like a red filter — brightens skin, darkens skies.
  // Classic prestige-doc mix.
  redWeight?: number;
  greenWeight?: number;
  blueWeight?: number;
  // Contrast boost 0..1 (scaled by intensity). Default 0.35.
  contrastBoost?: number;
  // Show optional grain overlay. Default true.
  grain?: boolean;
  // Grain opacity at peak. Default 0.1.
  grainStrength?: number;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Cinematic B&W. Proper channel-mixed grayscale — weights control how each
// color renders in luma. Defaults emulate a red-filter shoot (skin bright,
// skies dark), the Schindler's List / prestige-doc fingerprint. Deep
// contrast shaping + optional fine grain.
export const CineMono: React.FC<CineMonoProps> = ({
  children,
  redWeight = 0.5,
  greenWeight = 0.35,
  blueWeight = 0.15,
  contrastBoost = 0.35,
  grain = true,
  grainStrength = 0.1,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const frame = useCurrentFrame();
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 8,
    defaultHoldFrames: 14,
    defaultReleaseFrames: 12,
    defaultFadeInFrames: 22,
  });

  const filterId = "cinemono-channelmix";
  const contrast = 1 + contrastBoost * k;

  const grainShiftX = useMemo(() => (random(`cm-${frame}-x`) - 0.5) * 30, [frame]);
  const grainShiftY = useMemo(() => (random(`cm-${frame}-y`) - 0.5) * 30, [frame]);

  return (
    <AbsoluteFill>
      {/* Base footage — leave untouched until mixed in */}
      <AbsoluteFill>{children}</AbsoluteFill>

      {/* Channel-mixed B&W overlay. Fades in via opacity = k so when k=0
          the footage is color, and when k=1 it's fully cinema B&W. */}
      <AbsoluteFill
        style={{
          filter: `url(#${filterId}) contrast(${contrast})`,
          opacity: k,
          pointerEvents: "none",
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Deep shadow roll-off */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 45%, rgba(0,0,0,0.5) 100%)",
          opacity: 0.8 * k,
        }}
      />

      {/* Subtle grain */}
      {grain && (
        <ColorEffectLayer
          style={{
            opacity: grainStrength * k,
            mixBlendMode: "overlay",
            transform: `translate(${grainShiftX}px, ${grainShiftY}px) scale(1.1)`,
          }}
        >
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <filter id="cinemono-grain">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.95"
                numOctaves="2"
                stitchTiles="stitch"
              />
              <feColorMatrix type="saturate" values="0" />
            </filter>
            <rect width="100%" height="100%" filter="url(#cinemono-grain)" />
          </svg>
        </ColorEffectLayer>
      )}

      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden>
        <filter id={filterId}>
          <feColorMatrix
            type="matrix"
            values={`${redWeight} ${greenWeight} ${blueWeight} 0 0
                     ${redWeight} ${greenWeight} ${blueWeight} 0 0
                     ${redWeight} ${greenWeight} ${blueWeight} 0 0
                     0            0              0             1 0`}
          />
        </filter>
      </svg>
    </AbsoluteFill>
  );
};
