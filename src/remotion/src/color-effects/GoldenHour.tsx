import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface GoldenHourProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
  // Add the soft low-angle warm wash across the frame. Default true.
  sunWash?: boolean;
}

// Golden hour lock. Warm amber cast, cream highlights, a touch of magenta
// in shadows, preserved contrast. Different from VintageFilm — no halation
// or grain, no green shadows; this is "sun is about to set and everything
// glows" rather than "shot on film in 1978". Great for interviews, b-roll,
// and any footage you want to feel elevated without announcing a filter.
export const GoldenHour: React.FC<GoldenHourProps> = ({
  children,
  intensity = 1,
  timing = { mode: "persistent" },
  sunWash = true,
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 8,
    defaultHoldFrames: 14,
    defaultReleaseFrames: 12,
    defaultFadeInFrames: 22,
  });

  const saturation = 1 + 0.1 * k;
  const contrast = 1 + 0.06 * k;
  const warmth = 0.12 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `saturate(${saturation}) contrast(${contrast}) sepia(${warmth})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Cream highlight lift — soft amber wash across bright areas */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 38%, rgba(255,215,170,0.32) 0%, rgba(255,180,120,0.0) 55%)",
          mixBlendMode: "screen",
          opacity: 0.9 * k,
        }}
      />

      {/* Magenta hint in shadows — very subtle, gives depth */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 60%, rgba(80,40,60,0.0) 50%, rgba(110,55,70,0.35) 100%)",
          mixBlendMode: "multiply",
          opacity: 0.55 * k,
        }}
      />

      {/* Warm global wash — ties the frame together */}
      <ColorEffectLayer
        style={{
          background: "rgba(255,170,90,0.12)",
          mixBlendMode: "soft-light",
          opacity: 0.9 * k,
        }}
      />

      {/* Low-angle sun sweep from top-left, default on */}
      {sunWash && (
        <ColorEffectLayer
          style={{
            background:
              "linear-gradient(135deg, rgba(255,210,140,0.35) 0%, rgba(255,170,90,0.08) 35%, rgba(0,0,0,0) 70%)",
            mixBlendMode: "screen",
            opacity: 0.75 * k,
          }}
        />
      )}

      {/* Gentle vignette to contain the eye */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 58%, rgba(40,20,8,0.4) 100%)",
          opacity: 0.55 * k,
        }}
      />
    </AbsoluteFill>
  );
};
