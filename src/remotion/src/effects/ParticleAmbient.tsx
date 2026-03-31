import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Ambient floating particles — bokeh dots, dust motes, or fireflies
 * that drift continuously. Adds cinematic atmosphere to any footage.
 */

interface FloatingParticle {
  x: number;
  y: number;
  size: number;
  speed: number;
  drift: number;
  phase: number;
  opacity: number;
  blur: number;
}

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export const ParticleAmbient: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const style = (params.style as string) || "bokeh";
  const count = (params.count as number) || 20;
  const intensity = (params.intensity as number) || 0.5;

  const dur = end - start;
  const alpha = interpolate(
    t,
    [start, start + 0.5, end - 0.5, end],
    [0, intensity, intensity, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const particles = useMemo(() => {
    const rand = seededRandom(Math.round(start * 100) + 42);
    return Array.from({ length: count }, (): FloatingParticle => ({
      x: rand(),
      y: rand(),
      size: style === "bokeh" ? 10 + rand() * 30 : 2 + rand() * 4,
      speed: 0.01 + rand() * 0.03,
      drift: (rand() - 0.5) * 0.02,
      phase: rand() * Math.PI * 2,
      opacity: 0.1 + rand() * 0.4,
      blur: style === "bokeh" ? 2 + rand() * 8 : 0,
    }));
  }, [start, style, count]);

  if (alpha <= 0) return null;

  const age = t - start;

  const colors: Record<string, string> = {
    bokeh: "rgba(255,255,255,VAL)",
    dust: "rgba(255,240,200,VAL)",
    firefly: "rgba(255,255,150,VAL)",
    snow: "rgba(255,255,255,VAL)",
  };
  const colorTemplate = colors[style] || colors.bokeh;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {particles.map((p, i) => {
        const px = ((p.x + p.drift * age + Math.sin(age * 0.5 + p.phase) * 0.03) % 1) * width;
        const py = ((p.y - p.speed * age + Math.cos(age * 0.3 + p.phase) * 0.02) % 1 + 1) % 1 * height;
        const pAlpha = p.opacity * alpha * (0.5 + Math.sin(age * 2 + p.phase) * 0.5);
        const colorStr = colorTemplate.replace("VAL", pAlpha.toFixed(3));

        if (style === "firefly") {
          const glow = p.size * 3;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: px,
                top: py,
                width: p.size,
                height: p.size,
                borderRadius: "50%",
                backgroundColor: colorStr,
                boxShadow: `0 0 ${glow}px rgba(255,255,100,${pAlpha * 0.8})`,
              }}
            />
          );
        }

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: px,
              top: py,
              width: p.size,
              height: p.size,
              borderRadius: "50%",
              backgroundColor: colorStr,
              filter: p.blur > 0 ? `blur(${p.blur}px)` : undefined,
            }}
          />
        );
      })}
    </div>
  );
};
