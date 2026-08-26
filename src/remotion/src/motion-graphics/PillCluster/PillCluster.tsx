import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
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
//   • ARRANGEMENT (§4 pass 2026-08-24, the depth ruling): a COMPOSED pile.
//     The previous pass was a flex row with a gap — overlap was impossible BY
//     CONSTRUCTION, and floating chips at ±3° still read as "centred
//     non-overlapping boxes", the named §4 defect. Now each pill is placed
//     absolutely: ~22% horizontal overlap onto the previous pill, rows overlap
//     ~38% vertically, tilts alternate ±(3.5–7)°, and Z-ORDER FOLLOWS POP
//     ORDER, so every landing pill occludes an earlier one — the entrance
//     (a sticker slapped down from above) and the composition tell the same
//     physical story. Presence up (fontSize 42→54, canvas 680→940): D4's
//     symmetric-box cap is deliberately outranked by the §4 presence ruling;
//     the planner's anchor still moves the whole composed cluster as one
//     object.
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
  // Corpus law 1 (pass #7b): panel measured letterforms at ~2.5% frame height
  // vs the corpus's 5-6% — the cluster read as UI, not a graphic beat.
  // Outermost pills may crop at the frame edges (edge-crop is corpus-legal).
  width = 1160,
  fontSize = 78,
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

  // User/model text routes by script + emoji tail (font census 2026-08-26);
  // computed once per tag — layout advance + span style both read these.
  const tagFonts = rendered.map((t) => mgTextFont(t, "inter"));
  const tagMetrics = rendered.map((t) => mgTextMetrics(t));

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

  // ── §4 pile layout: serpentine placement with overlap on both axes ──
  const PAD_X = 40;
  const PAD_Y = 21;
  const pillH = fontSize + PAD_Y * 2;
  const rowStep = Math.round(pillH * 0.78); // rows overlap ~22% of pill height — edges tuck, text stays clear
  // 0.56 stays the latin advance; non-Latin uses the census estimate.
  const estW = (t: string, ti: number): number =>
    PAD_X * 2 +
    Math.max(3, t.length) *
      fontSize *
      (tagMetrics[ti].script === "latin" ? 0.56 : tagMetrics[ti].advanceEm);
  const placed: { x: number; y: number; rot: number }[] = [];
  {
    let x = 0;
    let row = 0;
    rendered.forEach((tag, i) => {
      const w = Math.min(estW(tag, i), width);
      if (x > 0 && x + w > width) {
        row += 1;
        // Alternating row indent so the left edge staggers like a real pile.
        x = row % 2 === 1
          ? Math.round(44 + hash01(row) * 36)
          : Math.round(hash01(row + 7) * 24);
      }
      const rot = (i % 2 === 0 ? -1 : 1) * (3.5 + hash01(i + 31) * 3.5);
      placed.push({ x, y: row * rowStep, rot });
      x += Math.round(w * 0.88); // next pill tucks 12% under — overlap reads as design, never eats a word (first pass at 22% swallowed 'focus' → 'ocus', render-proven)
    });
  }
  const clusterW = Math.min(
    width,
    Math.max(...rendered.map((t, i) => placed[i].x + estW(t, i))),
  );
  const clusterH = placed[placed.length - 1].y + pillH;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            width: clusterW,
            height: clusterH,
            opacity: exitOpacity,
            transform: `scale(${exitScale.toFixed(4)})`,
            transformOrigin: "center",
          }}
        >
          {rendered.map((tag, i) => {
            const act = START + delayRank[i] * STAGGER;
            // Corpus law 2: the corpus color-codes exactly ONE word per
            // beat ("aggressive red on the pain word, back to white on the
            // resolution") — two co-equal accent pills fused into a block on
            // the panel's frames. Exactly one pill carries the accent.
            const isAccent = accentEvery > 0 && i === Math.min(accentEvery - 1, N - 1);

            // Sticker slap: oversized above the surface, presses DOWN onto the
            // pile (1.28 → 0.97 squash → 1). The z-order makes the landing
            // occlude earlier pills, so entrance and composition agree.
            const pop = interpolate(
              localFrame,
              [act, act + 7, act + 13],
              [1.28, 0.97, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
            const dropY = interpolate(localFrame, [act, act + 7], [-16, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const popO = interpolate(localFrame, [act, act + 5], [0, 1], {
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

            const { x: px, y: py, rot } = placed[i];

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
                  position: "absolute",
                  left: px,
                  top: py,
                  zIndex: 1 + delayRank[i],
                  transform: `translate(${floatX.toFixed(2)}px, ${(floatY + dropY).toFixed(2)}px) scale(${(pop * pulse).toFixed(4)}) rotate(${rot.toFixed(2)}deg)`,
                  transformOrigin: "center",
                  opacity: popO,
                  padding: `${PAD_Y}px ${PAD_X}px`,
                  borderRadius: 999,
                  whiteSpace: "nowrap",
                  ...pillStyle,
                }}
              >
                <span
                  style={{
                    fontFamily: tagFonts[i],
                    fontSize,
                    fontWeight: 600,
                    color: isAccent ? "#15151E" : textColor,
                    letterSpacing: "0.005em",
                    lineHeight: Math.max(1, tagMetrics[i].lineHeight),
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
