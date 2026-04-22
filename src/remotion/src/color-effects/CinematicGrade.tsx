import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface CinematicGradeProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Teal-&-orange cinematic grade. Split tone done by CSS blend modes —
// `multiply` with a cool color darkens shadows toward teal, `overlay`
// with a warm color lifts highlights toward orange. Both overlays are
// FLAT (no radial gradients) so the tint is bound to pixel luminance,
// not screen position — that's what avoids the orange/white halo in
// the center of the frame.
export const CinematicGrade: React.FC<CinematicGradeProps> = ({
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

  const contrast = 1 + 0.1 * k;
  const saturation = 1 + 0.05 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `contrast(${contrast}) saturate(${saturation})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Cool shadow push — flat dark teal via soft-light. Soft-light is
          a gentler curve than multiply so shadows nudge teal without
          going muddy or crushing detail. */}
      <ColorEffectLayer
        style={{
          background: "#0d3a48",
          mixBlendMode: "soft-light",
          opacity: 0.55 * k,
        }}
      />

      {/* Warm highlight lift — flat amber via soft-light, lower opacity.
          Soft-light gives a refined warm roll-off without the orange
          blown-out look of overlay. */}
      <ColorEffectLayer
        style={{
          background: "#ff9a4c",
          mixBlendMode: "soft-light",
          opacity: 0.35 * k,
        }}
      />

      {/* Subtle black vignette for eye containment. No color wash. */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 60%, rgba(0,0,0,0.38) 100%)",
          opacity: 0.4 * k,
        }}
      />
    </AbsoluteFill>
  );
};
