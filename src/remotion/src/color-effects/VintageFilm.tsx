import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, random } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface VintageFilmProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
  // Add an animated grain pass. Default true.
  grain?: boolean;
  // Grain opacity at full intensity (0..1). Default 0.12.
  grainStrength?: number;
}

// Vintage film emulation: warm highlights, slightly green-cast shadows,
// halation glow around highlights, optional procedural grain. Tuned for
// a Portra/Kodachrome "analog but clean" look (not blown-out VHS).
export const VintageFilm: React.FC<VintageFilmProps> = ({
  children,
  intensity = 1,
  timing = { mode: "persistent" },
  grain = true,
  grainStrength = 0.12,
}) => {
  const frame = useCurrentFrame();
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 6,
    defaultHoldFrames: 12,
    defaultReleaseFrames: 10,
    defaultFadeInFrames: 20,
  });

  const sepia = 0.18 * k;
  const contrast = 1 + 0.08 * k;
  const saturation = 1 - 0.1 * k;

  // Animate grain offset so it shimmers frame-to-frame
  const grainShiftX = useMemo(() => (random(`g-${frame}-x`) - 0.5) * 40, [frame]);
  const grainShiftY = useMemo(() => (random(`g-${frame}-y`) - 0.5) * 40, [frame]);

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `sepia(${sepia}) contrast(${contrast}) saturate(${saturation})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Warm highlight lift */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 42%, rgba(255,198,140,0.22) 0%, rgba(255,170,90,0.0) 60%)",
          mixBlendMode: "screen",
          opacity: 0.9 * k,
        }}
      />

      {/* Green shadow cast — subtle, only in dark areas */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 60%, rgba(40,60,45,0.0) 45%, rgba(50,78,56,0.4) 100%)",
          mixBlendMode: "multiply",
          opacity: 0.55 * k,
        }}
      />

      {/* Halation: orange glow bleeding from edges of the frame */}
      <ColorEffectLayer
        style={{
          boxShadow: `inset 0 0 200px rgba(255,130,60,${0.25 * k})`,
        }}
      />

      {/* Soft vignette */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(22,14,6,0.55) 100%)",
          opacity: 0.65 * k,
        }}
      />

      {/* Procedural grain via SVG turbulence */}
      {grain && (
        <ColorEffectLayer
          style={{
            opacity: grainStrength * k,
            mixBlendMode: "overlay",
            transform: `translate(${grainShiftX}px, ${grainShiftY}px) scale(1.1)`,
          }}
        >
          <svg
            width="100%"
            height="100%"
            xmlns="http://www.w3.org/2000/svg"
            style={{ display: "block" }}
          >
            <filter id="vintage-grain">
              <feTurbulence
                type="fractalNoise"
                baseFrequency="0.9"
                numOctaves="2"
                stitchTiles="stitch"
              />
              <feColorMatrix type="saturate" values="0" />
            </filter>
            <rect width="100%" height="100%" filter="url(#vintage-grain)" />
          </svg>
        </ColorEffectLayer>
      )}
    </AbsoluteFill>
  );
};
