import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { VisualEffect } from "../types";

/**
 * Particle burst — confetti, sparkles, or dust that explode from a point.
 * Used on emphasis moments for celebration/impact.
 */

interface Particle {
  x: number; // start x (0-1)
  y: number; // start y (0-1)
  vx: number; // velocity x
  vy: number; // velocity y
  size: number;
  rotation: number;
  rotSpeed: number;
  color: string;
  delay: number; // stagger
  gravity: number;
}

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

export const ParticleBurst: React.FC<{ effect: VisualEffect }> = ({ effect }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const { start, end } = effect;
  const params = effect.params || {};
  const style = (params.style as string) || "confetti";
  const count = (params.count as number) || 30;
  const originX = (params.originX as number) || 0.5;
  const originY = (params.originY as number) || 0.4;

  const dur = end - start;
  const age = t - start;

  const alpha = interpolate(
    t,
    [start, start + 0.05, end - dur * 0.3, end],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const particles = useMemo(() => {
    const rand = seededRandom(Math.round(start * 1000));
    const colors: Record<string, string[]> = {
      confetti: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6", "#FF6B6B", "#4ADE80"],
      sparkle: ["#FFFFFF", "#FFE600", "#FFF5CC", "#FFFBE6"],
      dust: ["rgba(255,255,255,0.6)", "rgba(200,200,200,0.4)", "rgba(180,180,180,0.3)"],
      fire: ["#FF4500", "#FF6347", "#FFD700", "#FF8C00", "#FF0000"],
    };
    const palette = colors[style] || colors.confetti;

    return Array.from({ length: count }, (): Particle => {
      const angle = rand() * Math.PI * 2;
      const speed = 0.3 + rand() * 0.8;
      return {
        x: originX,
        y: originY,
        vx: Math.cos(angle) * speed * (0.5 + rand() * 0.5),
        vy: Math.sin(angle) * speed * (0.3 + rand() * 0.7) - 0.3,
        size: style === "sparkle" ? 3 + rand() * 6 : 6 + rand() * 10,
        rotation: rand() * 360,
        rotSpeed: (rand() - 0.5) * 720,
        color: palette[Math.floor(rand() * palette.length)],
        delay: rand() * 0.08,
        gravity: style === "dust" ? 0.02 : 0.15 + rand() * 0.1,
      };
    });
  }, [start, style, count, originX, originY]);

  if (alpha <= 0 || age < 0) return null;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", opacity: alpha }}>
      {particles.map((p, i) => {
        const pAge = Math.max(0, age - p.delay);
        if (pAge <= 0) return null;

        const px = (p.x + p.vx * pAge) * width;
        const py = (p.y + p.vy * pAge + p.gravity * pAge * pAge) * height;
        const rot = p.rotation + p.rotSpeed * pAge;
        const pAlpha = interpolate(pAge, [0, 0.05, dur * 0.6, dur], [0, 1, 0.8, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

        if (pAlpha <= 0) return null;

        if (style === "sparkle") {
          // Star shape via CSS
          const sparkleScale = 0.5 + Math.sin(pAge * 12) * 0.5;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: px,
                top: py,
                width: p.size,
                height: p.size,
                backgroundColor: p.color,
                borderRadius: "50%",
                boxShadow: `0 0 ${p.size * 2}px ${p.color}, 0 0 ${p.size * 4}px ${p.color}`,
                transform: `scale(${sparkleScale}) rotate(${rot}deg)`,
                opacity: pAlpha,
              }}
            />
          );
        }

        // Confetti rectangles
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: px,
              top: py,
              width: p.size,
              height: p.size * 0.6,
              backgroundColor: p.color,
              borderRadius: 2,
              transform: `rotate(${rot}deg) scaleY(${0.3 + Math.abs(Math.sin(pAge * 8)) * 0.7})`,
              opacity: pAlpha,
            }}
          />
        );
      })}
    </div>
  );
};
