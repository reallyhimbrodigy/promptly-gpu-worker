import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
} from "remotion";
import { noise2D } from "@remotion/noise";
import type { VisualEffect } from "../types";
import { CascadeEcho } from "../CascadeEcho";
import { ImpactText } from "../ImpactText";
import { BlurCard } from "../BlurCard";

/**
 * Visual effects layer — Captions AI quality.
 *
 * Effects observed across V1-V4:
 * - Impact flash (white/warm flash on cuts and emphasis)
 * - Color flash (tinted overlay for reactions/reveals)
 * - Warm flash / light leak (orange/amber flash as scene divider — V1 frame 101)
 * - Whip pan blur (horizontal motion blur simulating fast camera movement — V3)
 * - Vignette pulse (darkened edges on emphasis)
 * - Glitch (RGB shift + scanline displacement)
 * - Cascade echo (word repeated 4-7x with decreasing opacity — V1 SKEPTIC/RESULT)
 * - Impact text (full-screen large bold text — V2 EASY EDITING, V4 dynamic transitions)
 * - Blur card (heavy blur + sharp text overlay — V4)
 */

// ─── Impact Flash ────────────────────────────────────────────────────────────
const ImpactFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;
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

// ─── Warm Flash / Light Leak ────────────────────────────────────────────────
// Observed in V1 (frame ~101): warm orange/amber flash used as scene divider.
// Covers entire frame, washes to bright amber then fades back.
const WarmFlash: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;

  // Sharp attack to peak at 25%, then smooth exponential decay
  const envelope = progress < 0.25
    ? interpolate(progress, [0, 0.25], [0, 1])
    : interpolate(progress, [0.25, 1], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });

  const baseIntensity = (effect.params?.intensity as number) || 0.85;
  const alpha = envelope * baseIntensity;

  // Warm amber/orange color — the V1 signature light leak
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 50% 40%,
          rgba(255, 180, 60, ${alpha}) 0%,
          rgba(255, 140, 30, ${alpha * 0.7}) 40%,
          rgba(255, 100, 20, ${alpha * 0.4}) 70%,
          rgba(200, 60, 10, ${alpha * 0.15}) 100%
        )`,
        mixBlendMode: "screen",
      }}
    />
  );
};

// ─── Whip Pan Blur ───────────────────────────────────────────────────────────
// Observed in V3: extreme horizontal motion blur simulating a fast camera whip.
// Renders as horizontal streaks with directional noise.
const WhipPanBlur: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const start = effect.start;
  const end = effect.end;
  if (t < start || t > end) return null;

  const duration = end - start;
  const progress = (t - start) / duration;

  // Quick envelope: peak in the middle
  const envelope = progress < 0.4
    ? interpolate(progress, [0, 0.4], [0, 1])
    : interpolate(progress, [0.4, 1], [1, 0]);

  const intensity = ((effect.params?.intensity as number) || 0.8) * envelope;
  const direction = (effect.params?.direction as string) || "right";
  const xOffset = direction === "left" ? -1 : 1;

  // Render horizontal streak bars at noise-driven positions
  const streakCount = 8;
  const streaks = Array.from({ length: streakCount }, (_, i) => {
    const yPos = noise2D("whip-y", i * 0.5, frame * 0.3) * 0.5 + 0.5;
    const barHeight = 20 + Math.abs(noise2D("whip-h", i, frame * 0.2)) * 60;
    const xShift = noise2D("whip-x", i * 0.3, frame * 0.5) * width * 0.3 * xOffset;

    return (
      <div
        key={i}
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${yPos * 100}%`,
          height: barHeight * intensity,
          background: `linear-gradient(${direction === "left" ? "to left" : "to right"},
            transparent,
            rgba(255,255,255,${0.06 * intensity}),
            rgba(255,255,255,${0.12 * intensity}),
            rgba(255,255,255,${0.06 * intensity}),
            transparent
          )`,
          transform: `translateX(${xShift}px)`,
        }}
      />
    );
  });

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        opacity: intensity,
        mixBlendMode: "screen",
      }}
    >
      {streaks}
      {/* Overall directional tint */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(${direction === "left" ? "to left" : "to right"},
            transparent 20%,
            rgba(255,255,255,${0.04 * intensity}) 50%,
            transparent 80%
          )`,
        }}
      />
    </AbsoluteFill>
  );
};

// ─── Vignette Pulse ──────────────────────────────────────────────────────────
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

  const scanY = noise2D("glitch-scan", frame * 0.3, 0) * 0.5 + 0.5;
  const rgbShift = noise2D("glitch-rgb", 0, frame * 0.5) * 8 * intensity;
  const barHeight = 40 + Math.abs(noise2D("glitch-bar", frame * 0.2, 1)) * 80;

  return (
    <AbsoluteFill style={{ overflow: "hidden", mixBlendMode: "screen" }}>
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
  warm_flash: WarmFlash,
  whip_pan_blur: WhipPanBlur,
  vignette_pulse: VignettePulse,
  color_flash: ColorFlash,
  glitch: Glitch,
  // Emphasis overlays
  cascade_echo: CascadeEcho,
  impact_text: ImpactText,
  blur_card: BlurCard,
  // Legacy names map to closest equivalent
  light_leak: WarmFlash,
  edge_glow: VignettePulse,
  whip_pan: WhipPanBlur,
  zoom_blur_transition: ImpactFlash,
  particle_burst: ImpactFlash,
  particle_ambient: () => null,
  emoji_pop: () => null,
  vhs_grain: () => null,
  letterbox_cinematic: () => null,
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
