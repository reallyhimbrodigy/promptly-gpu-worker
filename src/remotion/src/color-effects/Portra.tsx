import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface PortraProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Kodak Portra 400 emulation — the modern-editorial portrait stock.
// Signature: low contrast, slightly lifted shadows, creamy warm-neutral
// skin tones, muted greens (so foliage doesn't compete with skin), clean
// highlight roll-off. Refined rather than flashy. Very different from
// GoldenHour (no sun glow) and VintageFilm (no halation, no grain bath)
// — Portra's whole point is that it looks "invisibly nice", like real
// shot-on-film editorial portraits.
export const Portra: React.FC<PortraProps> = ({
  children,
  intensity = 1,
  timing = { mode: "persistent" },
}) => {
  const { intensity: k } = useColorPhase(timing, {
    baseIntensity: intensity,
    defaultAttackFrames: 8,
    defaultHoldFrames: 14,
    defaultReleaseFrames: 12,
    defaultFadeInFrames: 22,
  });

  // Low contrast is the Portra fingerprint
  const contrast = 1 - 0.07 * k;
  const saturation = 1 - 0.05 * k;
  const brightness = 1 + 0.04 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `contrast(${contrast}) saturate(${saturation}) brightness(${brightness})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Lifted shadows — flat cream screen to raise black point without
          going milky. Screen has no effect on highlights, lifts shadows. */}
      <ColorEffectLayer
        style={{
          background: "#efe1cf",
          mixBlendMode: "screen",
          opacity: 0.08 * k,
        }}
      />

      {/* Warm-neutral skin cast — soft-light with a creamy peach. Nudges
          skin toward the Portra warm-neutral direction without tinting
          the whole frame. */}
      <ColorEffectLayer
        style={{
          background: "#f5c7a0",
          mixBlendMode: "soft-light",
          opacity: 0.3 * k,
        }}
      />

      {/* Muted-green pass — soft-light with desaturated olive. Green
          foliage and backgrounds get pulled toward a more neutral tone,
          which is how real Portra keeps skin dominant. */}
      <ColorEffectLayer
        style={{
          background: "#9eaf7f",
          mixBlendMode: "soft-light",
          opacity: 0.14 * k,
        }}
      />

      {/* Very subtle vignette — barely there, just edge control */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 70%, rgba(40,28,18,0.3) 100%)",
          opacity: 0.5 * k,
        }}
      />
    </AbsoluteFill>
  );
};
