import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import type { DropCardPoint, DropCardProps, DropCardStep } from "./types";
import { useMGPhase } from "../shared/useMGPhase";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const clamp01 = (t: number): number => Math.max(0, Math.min(1, t));

const hexToRgb = (h: string): [number, number, number] => {
  const n = parseInt(h.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
// Lerp between two #RRGGBB colors (caption highlight: grey -> black).
const lerpColor = (a: string, b: string, t: number): string => {
  const A = hexToRgb(a);
  const B = hexToRgb(b);
  const c = A.map((v, i) => Math.round(v + (B[i] - v) * clamp01(t)));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
};

const TOP_MARGIN = 90; // resting distance from the top of the frame
const SIDE_MARGIN = 54; // inset on each side (floating card)
const CIRCLE_START = 15;
const CIRCLE_STAGGER = 6;
const CIRCLE_SIZE = 140;
const ITEM_W = 188;
const RAIL_GAP = 44;
const RING_STROKE = 7;
// Per-circle start tilt; all resolve to 0deg, coupled to the entrance progress.
const START_ROT = [-22, 18, -15, 12, -10];

// Column scroll begins after the circles settle + a short hold.
const FIRST_SCROLL = 55;
const STEP = 98; // frames between successive slide scrolls
const SETTLE = 20; // frames for a slide to settle before its caption types
const WORD_STEP = 4; // frames between successive words lighting up
const WORD_FADE = 5; // per-word grey -> black fade length

const DEFAULT_STEPS: DropCardStep[] = [
  { label: "Hook" },
  { label: "Tension" },
  { label: "Payoff" },
];

const DEFAULT_POINTS: DropCardPoint[] = [
  {
    title: "1. The Missing Piece",
    caption: "Tell them what they don’t know yet so they have to keep watching.",
  },
  {
    title: "2. The Open Loop",
    caption: "Tease the payoff early but hold the answer back until the very end.",
  },
  {
    title: "3. The Payoff",
    caption: "Deliver on the promise so the watch felt worth it and they share it.",
  },
];

export const DropCard: React.FC<DropCardProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  titleLead,
  subtitle,
  steps = DEFAULT_STEPS,
  points = DEFAULT_POINTS,
  cardColor = "#FFFFFF",
  titleColor = "#15151E",
  subtitleColor = "#5A5A5A",
  labelColor = "#2A2A30",
  accentColor = "#F5A11E",
  railColor,
  spokenColor = "#15151E",
  mutedColor = "#C2C2CA",
  cardHeightPct = 0.5,
}) => {
  const { fps, width, height } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 24, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const rows = steps.slice(0, START_ROT.length);
  const n = rows.length;
  const rail = railColor ?? accentColor;

  const slideHeight = Math.round(cardHeightPct * height);
  const OFFSCREEN = TOP_MARGIN + slideHeight + 80;

  // Phase 1 — card drops in from above with a slight settle/overshoot.
  const cardSpring = spring({
    fps,
    frame: localFrame,
    config: { damping: 13, mass: 0.8, stiffness: 130 },
  });
  const cardEnterY = interpolate(cardSpring, [0, 1], [-OFFSCREEN, 0]);
  const cardExitY = exitProgress * -OFFSCREEN;
  const cardY = cardEnterY + cardExitY;

  const titleOpacity = interpolate(localFrame, [4, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleOpacity = interpolate(localFrame, [8, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const railEnd = CIRCLE_START + Math.max(0, n - 1) * CIRCLE_STAGGER + 8;
  const railScale = interpolate(localFrame, [CIRCLE_START, railEnd], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const railOpacity = interpolate(
    localFrame,
    [CIRCLE_START, CIRCLE_START + 5],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Multi-step scroll: each point's spring carries the column up one more
  // slide-height (clean settle, no bounce). Total = sum of steps.
  let stepSum = 0;
  for (let k = 0; k < points.length; k++) {
    stepSum += spring({
      fps,
      frame: localFrame - (FIRST_SCROLL + k * STEP),
      config: { damping: 19, stiffness: 100 },
    });
  }
  const columnY = -slideHeight * stepSum;

  // --- Slide 0: the numbered intro (dashed rail + labels) ---
  const introSlide = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: "100%",
        padding: "0 50px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontFamily: MG_FONTS.anton,
          fontSize: 68,
          fontWeight: 400,
          letterSpacing: "-0.005em",
          textTransform: "uppercase",
          textAlign: "center",
          lineHeight: 1.02,
          opacity: titleOpacity,
        }}
      >
        {titleLead ? (
          <span style={{ color: accentColor }}>{titleLead} </span>
        ) : null}
        <span style={{ color: titleColor }}>{title}</span>
      </div>

      {subtitle ? (
        <div
          style={{
            fontFamily: MG_FONTS.inter,
            fontSize: 31,
            fontWeight: 400,
            color: subtitleColor,
            textAlign: "center",
            lineHeight: 1.3,
            marginTop: 14,
            opacity: subtitleOpacity,
          }}
        >
          {subtitle}
        </div>
      ) : null}

      <div
        style={{
          position: "relative",
          display: "flex",
          flexDirection: "row",
          justifyContent: "center",
          gap: RAIL_GAP,
          marginTop: 46,
        }}
      >
        {n > 1 ? (
          <div
            style={{
              position: "absolute",
              top: CIRCLE_SIZE / 2,
              left: ITEM_W / 2,
              right: ITEM_W / 2,
              height: 0,
              borderTop: `3px dashed ${rail}`,
              opacity: railOpacity,
              transform: `scaleX(${railScale.toFixed(3)})`,
              transformOrigin: "left center",
              zIndex: 0,
            }}
          />
        ) : null}

        {rows.map((step, j) => {
          const startF = CIRCLE_START + j * CIRCLE_STAGGER;
          // Single spring drives BOTH scale and rotation (the coupling).
          const cs = spring({
            fps,
            frame: localFrame - startF,
            config: { damping: 11, mass: 0.8, stiffness: 120 },
          });
          const sc = cs; // 0 -> overshoot -> 1 (small -> big bounce)
          const rot = interpolate(
            cs,
            [0, 1],
            [START_ROT[j % START_ROT.length], 0],
          );
          const circleOp = interpolate(localFrame, [startF, startF + 4], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const labelOp = interpolate(
            localFrame,
            [startF + 6, startF + 16],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
          const labelY = interpolate(
            localFrame,
            [startF + 6, startF + 18],
            [10, 0],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            },
          );

          return (
            <div
              key={j}
              style={{
                position: "relative",
                zIndex: 1,
                width: ITEM_W,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  width: CIRCLE_SIZE,
                  height: CIRCLE_SIZE,
                  borderRadius: "50%",
                  border: `${RING_STROKE}px solid ${accentColor}`,
                  backgroundColor: cardColor,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  opacity: circleOp,
                  transform: `scale(${sc.toFixed(3)}) rotate(${rot.toFixed(2)}deg)`,
                  transformOrigin: "center",
                }}
              >
                <span
                  style={{
                    fontFamily: MG_FONTS.inter,
                    fontSize: Math.round(CIRCLE_SIZE * 0.5),
                    fontWeight: 800,
                    color: accentColor,
                    lineHeight: 1,
                  }}
                >
                  {j + 1}
                </span>
              </div>

              {step.label ? (
                <div
                  style={{
                    fontFamily: MG_FONTS.inter,
                    fontSize: 23,
                    fontWeight: 700,
                    color: labelColor,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    textAlign: "center",
                    marginTop: 20,
                    opacity: labelOp,
                    transform: `translateY(${labelY.toFixed(2)}px)`,
                  }}
                >
                  {step.label}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );

  // --- Caption slides: one per point, word-by-word grey -> black ---
  const captionSlides = points.map((pt, k) => {
    const captionStart = FIRST_SCROLL + k * STEP + SETTLE;
    const words = pt.caption.split(" ");
    return (
      <div
        key={`pt-${k}`}
        style={{
          width: "100%",
          padding: "0 64px",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
        }}
      >
        <div
          style={{
            fontFamily: MG_FONTS.anton,
            fontSize: 56,
            fontWeight: 400,
            color: accentColor,
            textTransform: "uppercase",
            letterSpacing: "-0.01em",
            lineHeight: 1.0,
          }}
        >
          {pt.title}
        </div>

        <div
          style={{
            marginTop: 32,
            fontFamily: MG_FONTS.inter,
            fontSize: 42,
            fontWeight: 600,
            lineHeight: 1.34,
            textAlign: "left",
          }}
        >
          {words.map((w, j) => {
            const activation = captionStart + j * WORD_STEP;
            const t = (localFrame - activation) / WORD_FADE;
            return (
              <span key={j} style={{ color: lerpColor(mutedColor, spokenColor, t) }}>
                {w}
                {j < words.length - 1 ? " " : ""}
              </span>
            );
          })}
        </div>
      </div>
    );
  });

  const slides = [introSlide, ...captionSlides];

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          top: TOP_MARGIN,
          left: SIDE_MARGIN,
          width: width - SIDE_MARGIN * 2,
          height: slideHeight,
          backgroundColor: cardColor,
          borderRadius: 44,
          boxShadow:
            "0 32px 64px rgba(0,0,0,0.30), 0 10px 22px rgba(0,0,0,0.16)",
          overflow: "hidden",
          transform: `translateY(${cardY.toFixed(2)}px)`,
          willChange: "transform",
        }}
      >
        {/* The scrolling content column — slides stacked vertically. */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            transform: `translateY(${columnY.toFixed(2)}px)`,
          }}
        >
          {slides.map((node, i) => {
            const dist = Math.abs(i * slideHeight + columnY);
            const scale = interpolate(dist, [0, slideHeight], [1, 0.84], {
              extrapolateRight: "clamp",
            });
            const opacity = interpolate(dist, [0, slideHeight * 0.7], [1, 0], {
              extrapolateRight: "clamp",
            });
            return (
              <div
                key={i}
                style={{
                  height: slideHeight,
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  boxSizing: "border-box",
                  transform: `scale(${scale.toFixed(3)})`,
                  opacity,
                  transformOrigin: "center",
                }}
              >
                {node}
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
