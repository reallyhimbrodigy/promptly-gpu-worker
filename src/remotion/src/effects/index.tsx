import React from "react";
import type { VisualEffect } from "../types";
import { LightLeak } from "./LightLeak";
import { GlitchFlash } from "./GlitchFlash";
import { ImpactFlash } from "./ImpactFlash";
import { ParticleBurst } from "./ParticleBurst";
import { ParticleAmbient } from "./ParticleAmbient";
import { EmojiPop } from "./EmojiPop";
import { ZoomBlurTransition } from "./ZoomBlurTransition";
import { WhipPan } from "./WhipPan";
import { VignettePulse } from "./VignettePulse";
import { ColorFlash } from "./ColorFlash";
import { LetterboxCinematic } from "./LetterboxCinematic";
import { EdgeGlow } from "./EdgeGlow";
import { VHSGrain } from "./VHSGrain";

/**
 * Registry of all visual effect components.
 * Each effect renders as a transparent overlay layer.
 */
const EFFECT_COMPONENTS: Record<string, React.FC<{ effect: VisualEffect }>> = {
  light_leak: LightLeak,
  glitch: GlitchFlash,
  impact_flash: ImpactFlash,
  particle_burst: ParticleBurst,
  particle_ambient: ParticleAmbient,
  emoji_pop: EmojiPop,
  zoom_blur_transition: ZoomBlurTransition,
  whip_pan: WhipPan,
  vignette_pulse: VignettePulse,
  color_flash: ColorFlash,
  letterbox_cinematic: LetterboxCinematic,
  edge_glow: EdgeGlow,
  vhs_grain: VHSGrain,
};

/**
 * Renders a single visual effect by type.
 */
export const EffectRenderer: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const Component = EFFECT_COMPONENTS[effect.type];
  if (!Component) return null;
  return <Component effect={effect} />;
};

/**
 * Renders all visual effects as stacked transparent layers.
 * Effects are rendered in order — later effects render on top.
 */
export const EffectsLayer: React.FC<{ effects: VisualEffect[] }> = ({ effects }) => {
  return (
    <>
      {effects.map((effect, i) => (
        <EffectRenderer key={`${effect.type}-${i}`} effect={effect} />
      ))}
    </>
  );
};
