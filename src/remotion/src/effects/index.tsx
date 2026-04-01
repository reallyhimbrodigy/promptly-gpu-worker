import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import { noise2D } from "@remotion/noise";
import type { VisualEffect } from "../types";

/**
 * Compact, high-impact visual effects using Remotion primitives + noise.
 * Replaces 13 hand-rolled components with 4 clean inline effects.
 *
 * Design principle: each effect is a simple CSS overlay.
 * No complex canvas drawing, no particle systems.
 * Just opacity, color, blur, and transform — what actually reads on screen.
 */

// ─── Impact Flash ────────────────────────────────────────────────────────────
// Brief white/color flash overlay. The most visible, most important effect.
const ImpactFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;
  // Sharp attack, smooth decay
  const intensity = progress < 0.2
    ? interpolate(progress, [0, 0.2], [0, 1])
    : interpolate(progress, [0.2, 1], [1, 0]);

  const baseIntensity = (effect.params?.intensity as number) || 0.7;
  const color = (effect.params?.color as string) || "white";
  const alpha = intensity * baseIntensity;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: color === "white" ? `rgba(255,255,255,${alpha})` :
                         color === "warm" ? `rgba(255,200,100,${alpha * 0.8})` :
                         `rgba(255,255,255,${alpha})`,
        mixBlendMode: "screen",
      }}
    />
  );
};

// ─── Vignette Pulse ──────────────────────────────────────────────────────────
// Darkening edges that pulse on emphasis. Focuses attention on center.
const VignettePulse: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;
  const pulse = progress < 0.3
    ? interpolate(progress, [0, 0.3], [0, 1])
    : interpolate(progress, [0.3, 1], [1, 0]);

  const intensity = ((effect.params?.intensity as number) || 0.6) * pulse;

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,${intensity}) 100%)`,
      }}
    />
  );
};

// ─── Color Flash ─────────────────────────────────────────────────────────────
// Brief color tint overlay for reactions/reveals.
const ColorFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;
  const fade = progress < 0.15
    ? interpolate(progress, [0, 0.15], [0, 1])
    : interpolate(progress, [0.15, 1], [1, 0]);

  const colorMap: Record<string, string> = {
    cyan: "0, 210, 255",
    blue: "59, 130, 246",
    gold: "255, 215, 0",
    pink: "255, 60, 150",
    red: "220, 40, 40",
    purple: "168, 85, 247",
    orange: "255, 140, 0",
    teal: "0, 180, 170",
    green: "0, 200, 100",
  };
  const colorKey = (effect.params?.color as string) || "cyan";
  const rgb = colorMap[colorKey] || colorMap.cyan;
  const intensity = ((effect.params?.intensity as number) || 0.35) * fade;

  return (
    <AbsoluteFill
      style={{
        backgroundColor: `rgba(${rgb}, ${intensity})`,
        mixBlendMode: "screen",
      }}
    />
  );
};

// ─── Glitch ──────────────────────────────────────────────────────────────────
// Quick RGB shift + noise displacement. Organic via noise2D.
const Glitch: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;
  const intensity = ((effect.params?.intensity as number) || 0.7) *
    (progress < 0.3 ? interpolate(progress, [0, 0.3], [0, 1]) : interpolate(progress, [0.3, 1], [1, 0]));

  // Noise-driven scanline position and RGB offset
  const scanY = noise2D("glitch-scan", frame * 0.3, 0) * 0.5 + 0.5;
  const rgbShift = noise2D("glitch-rgb", 0, frame * 0.5) * 8 * intensity;
  const barHeight = 40 + Math.abs(noise2D("glitch-bar", frame * 0.2, 1)) * 80;

  return (
    <AbsoluteFill style={{ overflow: "hidden", mixBlendMode: "screen" }}>
      {/* Horizontal glitch bar */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${scanY * 100}%`,
          height: barHeight,
          background: `rgba(255, 255, 255, ${0.08 * intensity})`,
          transform: `translateX(${rgbShift * 3}px)`,
        }}
      />
      {/* RGB channel ghosts */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${scanY * 100 - 2}%`,
          height: barHeight * 0.5,
          background: `rgba(255, 0, 50, ${0.12 * intensity})`,
          transform: `translateX(${rgbShift}px)`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${scanY * 100 + 2}%`,
          height: barHeight * 0.5,
          background: `rgba(0, 200, 255, ${0.12 * intensity})`,
          transform: `translateX(${-rgbShift}px)`,
        }}
      />
    </AbsoluteFill>
  );
};

// ─── Effect Registry ─────────────────────────────────────────────────────────

const EFFECT_COMPONENTS: Record<string, React.FC<{ effect: VisualEffect }>> = {
  impact_flash: ImpactFlash,
  vignette_pulse: VignettePulse,
  color_flash: ColorFlash,
  glitch: Glitch,
  // Legacy names map to closest equivalent
  light_leak: ColorFlash,
  edge_glow: VignettePulse,
  whip_pan: Glitch,
  zoom_blur_transition: ImpactFlash,
  particle_burst: ImpactFlash,
  particle_ambient: () => null,  // ambient particles removed — too subtle to matter
  emoji_pop: () => null,         // emojis removed — unprofessional
  vhs_grain: () => null,         // grain handled by FFmpeg
  letterbox_cinematic: () => null, // letterbox handled by FFmpeg
};

/**
 * Renders all visual effects as stacked transparent layers.
 */
export const EffectsLayer: React.FC<{ effects: VisualEffect[] }> = ({ effects }) => {
  return (
    <>
      {effects.map((effect, i) => {
        const Component = EFFECT_COMPONENTS[effect.type];
        if (!Component) return null;
        return <Component key={`${effect.type}-${i}`} effect={effect} />;
      })}
    </>
  );
};
