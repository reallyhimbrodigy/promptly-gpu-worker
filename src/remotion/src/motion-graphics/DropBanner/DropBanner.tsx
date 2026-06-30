import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import type { DropBannerPoint, DropBannerProps } from "./types";

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

// Extra height above the frame so the banner's bounce overshoot never reveals
// a gap at the very top.
const EXTRA = 170;
const CIRCLE_START = 15;
const CIRCLE_STAGGER = 6;
const CIRCLE_SIZE = 168;
const CONNECTOR_W = 70;
const LINE_THICK = 4;
const RING_STROKE = 8;
// Per-circle start tilt; all resolve to 0deg, coupled to the entrance progress.
const START_ROT = [-22, 18, -15, 12, -10];

// Column scroll begins after the circles settle + a short hold.
const FIRST_SCROLL = 55;
const STEP = 98; // frames between successive slide scrolls
const SETTLE = 20; // frames for a slide to settle before its caption types
const WORD_STEP = 4; // frames between successive words lighting up
const WORD_FADE = 5; // per-word grey -> black fade length

const DEFAULT_POINTS: DropBannerPoint[] = [
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

export const DropBanner: React.FC<DropBannerProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  subtitle,
  count = 3,
  points = DEFAULT_POINTS,
  cardColor = "#FFFFFF",
  titleColor = "#15151E",
  subtitleColor = "#5A5A5A",
  accentColor = "#F5A11E",
  spokenColor = "#15151E",
  mutedColor = "#C2C2CA",
  cardHeightPct = 0.47,
}) => {
  const { fps, height } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 24, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const cardHeight = Math.round(cardHeightPct * height);
  const totalH = cardHeight + EXTRA;
  const slideHeight = cardHeight;

  // Phase 1 — banner drops in from above with a slight settle/overshoot.
  const cardSpring = spring({
    fps,
    frame: localFrame,
    config: { damping: 12, mass: 0.85, stiffness: 120 },
  });
  const cardEnterY = interpolate(cardSpring, [0, 1], [-totalH, 0]);
  const cardExitY = exitProgress * -totalH;
  const cardY = cardEnterY + cardExitY;

  const titleOpacity = interpolate(localFrame, [4, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleOpacity = interpolate(localFrame, [8, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const n = Math.max(1, Math.min(count, START_ROT.length));

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

  // --- Slide 0: the numbered intro ---
  const introSlide = (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: "100%",
        padding: "0 80px",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          fontFamily: MG_FONTS.anton,
          fontSize: 72,
          fontWeight: 400,
          color: titleColor,
          letterSpacing: "-0.005em",
          textTransform: "uppercase",
          textAlign: "center",
          lineHeight: 1.02,
          opacity: titleOpacity,
        }}
      >
        {title}
      </div>

      {subtitle ? (
        <div
          style={{
            fontFamily: MG_FONTS.inter,
            fontSize: 32,
            fontWeight: 400,
            color: subtitleColor,
            textAlign: "center",
            lineHeight: 1.3,
            marginTop: 16,
            opacity: subtitleOpacity,
          }}
        >
          {subtitle}
        </div>
      ) : null}

      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          marginTop: 58,
        }}
      >
        {Array.from({ length: n }).map((_, j) => {
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
          const op = interpolate(localFrame, [startF, startF + 4], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          // Connector segment after this circle, drawing left -> right.
          const segStart = startF + 4;
          const segScale = interpolate(
            localFrame,
            [segStart, segStart + 11],
            [0, 1],
            {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            },
          );
          const segOpacity = interpolate(
            localFrame,
            [segStart, segStart + 4],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );

          return (
            <React.Fragment key={j}>
              <div
                style={{
                  width: CIRCLE_SIZE,
                  height: CIRCLE_SIZE,
                  flexShrink: 0,
                  borderRadius: "50%",
                  border: `${RING_STROKE}px solid ${accentColor}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  opacity: op,
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

              {j < n - 1 ? (
                <div
                  style={{
                    width: CONNECTOR_W,
                    height: LINE_THICK,
                    flexShrink: 0,
                    borderRadius: LINE_THICK / 2,
                    backgroundColor: accentColor,
                    opacity: segOpacity,
                    transform: `scaleX(${segScale.toFixed(3)})`,
                    transformOrigin: "left center",
                  }}
                />
              ) : null}
            </React.Fragment>
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
          padding: "0 88px",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
        }}
      >
        <div
          style={{
            fontFamily: MG_FONTS.anton,
            fontSize: 60,
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
            marginTop: 36,
            fontFamily: MG_FONTS.inter,
            fontSize: 44,
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
          top: -EXTRA,
          left: 0,
          width: "100%",
          height: totalH,
          backgroundColor: cardColor,
          borderBottomLeftRadius: 44,
          borderBottomRightRadius: 44,
          boxShadow: "0 16px 38px rgba(0,0,0,0.30)",
          overflow: "hidden",
          transform: `translateY(${cardY.toFixed(2)}px)`,
          willChange: "transform",
        }}
      >
        {/* The scrolling content column — slides stacked vertically. */}
        <div
          style={{
            position: "absolute",
            top: EXTRA,
            left: 0,
            width: "100%",
            transform: `translateY(${columnY.toFixed(2)}px)`,
          }}
        >
          {slides.map((node, i) => {
            // Distance of this slide's center from the viewport center
            // (EXTRA cancels out). Drives the responsive-scroll depth shrink.
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
