import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { PillClusterProps } from "./types";


const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

const DEFAULT_TEXT_SHADOW =
  "0 2px 10px rgba(0,0,0,0.55), 0 1px 2px rgba(0,0,0,0.5)";
const START = 6;
const STAGGER = 4;


// Deterministic 0..1 hash (no Math.random — render must be reproducible).
const hash01 = (i: number): number => {
  const x = Math.sin(i * 99.13 + 7.7) * 43758.5453;
  return x - Math.floor(x);
};

// ART DIRECTION (2026-08-20). Reference: the iOS glass "topic/keyword sticker"
// cluster — Control-Center / Apple-Music frosted pills and the story-sticker
// tag pile. What that look is made of, decided on purpose (not spec-compliance):
//   • MATERIAL: frosted glass (backdrop blur + a top light gradient + a hairline
//     inner highlight), so the pills read as physical chips over the footage, not
//     flat labels. Every third is the JOB ACCENT — a solid, glowing chip — for a
//     colour rhythm across the pile.
//   • ARRANGEMENT (§4, overlap reads as design): a DENSE pile, each pill at a
//     small organic ±3deg, popped in a shuffled order so it never reads L→R, then
//     a slow idle float. The density (tight gap + the tilt) is what makes it a
//     PILE, not a centred row of buttons. gap tightened 22→15 for that.
// INVARIANTS: palette-only colours (accent + text from the job), the contrast
// floor via the pill's own shadow + the glass ground, velocity handled by the
// per-pill stagger (small travel, no single-frame spike). NOTE: this component
// is deliberately NOT motion-blurred — CameraMotionBlur re-lays-out its subtree
// and cannot preserve the parent-centred, fixed-width, backdrop-filter cluster
// (proven by render, 2026-08-20); the pop travel is small and needs none.

export const PillCluster: React.FC<PillClusterProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  tags = [],
  accentColor = "#4F9DF7",
  accentEvery = 3,
  glass = true,
  // D4: fit the symmetric center box (max 680) — oversize dragged center right
  width = 680,
  fontSize = 42,
  textColor = "#FFFFFF",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  // v197 fail-closed: no invented content — empty props render nothing
  // (the DropCard DEFAULT_POINTS class; worker-side F5 now rejects these
  // upstream, this is the renderer belt).
  if (!tags || tags.length === 0) return null;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 24, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const rendered = tags.slice(0, 12);
  const N = rendered.length;
  if (N === 0) return null;

  // Shuffle the pop-in order deterministically so it doesn't read left→right.
  const orderBySeed = rendered
    .map((_, i) => i)
    .sort((a, b) => hash01(a) - hash01(b));
  const delayRank: number[] = [];
  orderBySeed.forEach((origIdx, pos) => {
    delayRank[origIdx] = pos;
  });

  const exitOpacity = 1 - exitProgress;
  const exitScale = 1 - 0.06 * exitProgress;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: 15,
            width,
            maxWidth: width,
            opacity: exitOpacity,
            transform: `scale(${exitScale.toFixed(4)})`,
            transformOrigin: "center",
          }}
        >
          {rendered.map((tag, i) => {
            const act = START + delayRank[i] * STAGGER;
            const isAccent = accentEvery > 0 && (i + 1) % accentEvery === 0;

            // Spring pop-in: 0 → overshoot → 1.
            const pop = interpolate(
              localFrame,
              [act, act + 6, act + 14],
              [0, 1.1, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
            const popO = interpolate(localFrame, [act, act + 6], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            // Subtle continuous float once landed.
            const landed = clamp01((localFrame - act - 10) / 12);
            const floatY =
              landed *
              (Math.sin(localFrame * 0.045 + i * 1.7) * 4 +
                Math.sin(localFrame * 0.075 + i * 0.9) * 2);
            const floatX = landed * Math.sin(localFrame * 0.038 + i * 2.3) * 2.5;

            // Accent pills get one soft pulse after landing.
            const pulse = isAccent
              ? interpolate(
                  localFrame,
                  [act + 14, act + 20, act + 30],
                  [1, 1.07, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                )
              : 1;

            const rot = (hash01(i + 31) * 2 - 1) * 3; // ±3deg

            const neutralBg = glass
              ? "linear-gradient(180deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0) 50%), rgba(17,19,25,0.38)"
              : "rgba(22,24,31,0.78)";
            const pillStyle: React.CSSProperties = isAccent
              ? {
                  background: `linear-gradient(180deg, ${accentColor} 0%, ${accentColor}d9 100%)`,
                  border: `1.5px solid ${accentColor}`,
                  boxShadow: `0 10px 26px rgba(0,0,0,0.4), 0 0 22px ${accentColor}55, inset 0 1px 0 rgba(255,255,255,0.4)`,
                }
              : {
                  background: neutralBg,
                  backdropFilter: glass ? "blur(16px) saturate(140%)" : undefined,
                  WebkitBackdropFilter: glass
                    ? "blur(16px) saturate(140%)"
                    : undefined,
                  border: "1.5px solid rgba(255,255,255,0.22)",
                  boxShadow:
                    "0 10px 26px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.18)",
                };

            return (
              <div
                key={i}
                style={{
                  transform: `translate(${floatX.toFixed(2)}px, ${floatY.toFixed(2)}px) scale(${(pop * pulse).toFixed(4)}) rotate(${rot.toFixed(2)}deg)`,
                  transformOrigin: "center",
                  opacity: popO,
                  padding: "18px 34px",
                  borderRadius: 999,
                  whiteSpace: "nowrap",
                  ...pillStyle,
                }}
              >
                <span
                  style={{
                    fontFamily: MG_FONTS.inter,
                    fontSize,
                    fontWeight: 600,
                    color: isAccent ? "#15151E" : textColor,
                    letterSpacing: "0.005em",
                    lineHeight: 1,
                    textShadow: isAccent ? undefined : textShadow,
                  }}
                >
                  {tag}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
