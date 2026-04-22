import React from "react";
import { AbsoluteFill } from "remotion";
import { useColorPhase, ColorEffectLayer } from "./shared";
import type { ColorTimingMode } from "./shared";

export interface NeoNoirProps {
  children: React.ReactNode;
  intensity?: number;
  timing?: ColorTimingMode;
}

// Fincher-style neo-noir grade (Se7en, Gone Girl, The Social Network).
// Signature: heavy desaturation, crushed blacks, cold sickly cast in
// midtones (that faint greenish-cyan that makes everything feel
// unhealthy), and a high-contrast roll-off. Not B&W (we have CineMono
// for that) — this is still technically color footage, just emotionally
// drained of color. Different from BleachBypass (silver/metallic sheen)
// — NeoNoir feels *cold*, not *aged*.
export const NeoNoir: React.FC<NeoNoirProps> = ({
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

  const saturation = 1 - 0.55 * k;
  const contrast = 1 + 0.22 * k;
  const brightness = 1 - 0.06 * k;

  return (
    <AbsoluteFill>
      <AbsoluteFill
        style={{
          filter: `saturate(${saturation}) contrast(${contrast}) brightness(${brightness})`,
        }}
      >
        {children}
      </AbsoluteFill>

      {/* Cold teal shadow push — multiply with a deep navy-teal crushes
          shadows toward cold. */}
      <ColorEffectLayer
        style={{
          background: "#0f2a32",
          mixBlendMode: "multiply",
          opacity: 0.35 * k,
        }}
      />

      {/* Sickly green midtone cast — the Fincher fingerprint. Soft-light
          with desat olive-green makes skin look slightly unhealthy and
          environments feel wrong. Keep it subtle — too much and it reads
          as hospital scene. */}
      <ColorEffectLayer
        style={{
          background: "#7d8a5e",
          mixBlendMode: "soft-light",
          opacity: 0.28 * k,
        }}
      />

      {/* Muted yellow-beige highlight pull — sallow skin, aged paper,
          cigarette-smoke mids. Not warm, not clean — dirty. */}
      <ColorEffectLayer
        style={{
          background: "#b8a878",
          mixBlendMode: "soft-light",
          opacity: 0.2 * k,
        }}
      />

      {/* Deep vignette — noir wouldn't be noir without it */}
      <ColorEffectLayer
        style={{
          background:
            "radial-gradient(ellipse at 50% 50%, transparent 45%, rgba(0,4,8,0.6) 100%)",
          opacity: 0.8 * k,
        }}
      />
    </AbsoluteFill>
  );
};
