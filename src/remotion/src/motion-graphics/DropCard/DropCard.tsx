import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { inkFor, isLightSurface } from "../shared/ink";
import type { DropCardPoint, DropCardProps, DropCardStep } from "./types";
import { useMGPhase } from "../shared/useMGPhase";
import { asText } from "../../shared/asText";

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
const RAIL_GAP = 56;
const RING_STROKE = 9;
// Per-circle start tilt; all resolve to 0deg, coupled to the entrance progress.
const START_ROT = [-22, 18, -15, 12, -10];

// F5 (final-wave review): the catalog-example fallback content that used to
// live here ("1. The Missing Piece" genre advice) was the ACTUAL mechanism
// behind ungrounded cards reaching real videos — the model omits points and
// the renderer invented them. A card with no points renders its grounded
// title/steps only; nothing is ever invented.

export const DropCard: React.FC<DropCardProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  titleLead,
  subtitle,
  steps = [],
  points = [],
  cardColor = "#FFFFFF",
  titleColor,
  subtitleColor,
  labelColor,
  accentColor = "#F5A11E",
  railColor,
  spokenColor,
  mutedColor,
  cardHeightPct = 0.44,
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

  // 2026-08-26 coupled-defaults audit: like `rail` above, the text family
  // tracks its cardColor partner — the dark constants were authored for the
  // white card, and a cardColor-only dark override rendered an invisible
  // title/labels plus captions that fade OUT as spoken. Explicit overrides
  // pass through; the light-card path keeps today's constants.
  const lightCard = isLightSurface(cardColor);
  const effTitleColor = titleColor ?? inkFor(cardColor); // "#15151E" on light
  const effSpokenColor = spokenColor ?? inkFor(cardColor);
  const effSubtitleColor = subtitleColor ?? (lightCard ? "#5A5A5A" : "#B0B0B8");
  const effLabelColor = labelColor ?? (lightCard ? "#2A2A30" : "#D6D6DC");
  const effMutedColor = mutedColor ?? (lightCard ? "#C2C2CA" : "#55555E");

  // Pass #7c (craft lane): the schedule is fps-relative and DURATION-AWARE.
  // The old absolute-frame constants (FIRST_SCROLL=55, STEP=98) meant a live
  // 2.5s card at 30fps reached its only caption exactly as the card exited —
  // the payoff was unreachable in the durations the model actually sends.
  // The scroll starts by 30% of the card's life and every point's caption
  // finishes lighting by ~85%, whatever the fps or duration.
  const totalFrames = Math.max(
    1,
    Math.round(((durationMs ?? 4000) / 1000) * fps),
  );
  const CIRCLE_START = Math.round(0.25 * fps);
  const CIRCLE_STAGGER = Math.max(1, Math.round(0.1 * fps));
  const SETTLE = Math.round(0.33 * fps);
  const WORD_STEP = Math.max(1, Math.round(0.067 * fps));
  const WORD_FADE = Math.max(1, Math.round(0.083 * fps));
  const FIRST_SCROLL = Math.min(
    Math.round(0.92 * fps),
    Math.round(0.3 * totalFrames),
  );
  const STEP = Math.min(
    Math.round(1.63 * fps),
    Math.max(
      Math.round(0.5 * fps),
      Math.round(
        (0.85 * totalFrames - FIRST_SCROLL) / Math.max(1, points.length),
      ),
    ),
  );

  // The rail fills the card instead of floating in it (interior takeover —
  // the before sat at ~67% of the card's width, ~40% of its height). Width
  // adapts so a 4-5 step rail never bleeds off the card: graphics may crop
  // the FRAME, but chrome bleeding off a floating white card reads broken.
  const cardW = width - SIDE_MARGIN * 2;
  const ITEM_W =
    n > 0
      ? Math.min(250, Math.floor((cardW - 80 - RAIL_GAP * (n - 1)) / n))
      : 250;
  const CIRCLE_SIZE = Math.min(190, Math.round(ITEM_W * 0.76));

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

  const railEnd =
    CIRCLE_START + Math.max(0, n - 1) * CIRCLE_STAGGER + Math.round(0.13 * fps);
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

  // User/model text routes by script + emoji tail (font census 2026-08-26);
  // the circle digits keep bare MG_FONTS (chrome).
  const titleText = titleLead ? `${titleLead} ${title}` : title;
  const titleMetrics = mgTextMetrics(titleText);

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
          fontFamily: mgTextFont(titleText, "anton"),
          // Interior takeover (pass #7c): 68px on a ~850px card read as a
          // caption, not a claim. The title is the card's voice.
          fontSize: 104,
          fontWeight: 400,
          letterSpacing: "-0.005em",
          textTransform: titleMetrics.uppercaseSafe ? "uppercase" : "none",
          textAlign: "center",
          lineHeight: Math.max(1.02, titleMetrics.lineHeight),
          opacity: titleOpacity,
        }}
      >
        {titleLead ? (
          <span style={{ color: accentColor }}>{titleLead} </span>
        ) : null}
        <span style={{ color: effTitleColor }}>{title}</span>
      </div>

      {subtitle ? (
        <div
          style={{
            fontFamily: mgTextFont(subtitle, "inter"),
            fontSize: 40,
            fontWeight: 400,
            color: effSubtitleColor,
            textAlign: "center",
            lineHeight: 1.3,
            marginTop: 18,
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
          marginTop: 56,
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
                // Step labels are model text (font census 2026-08-26).
                <div
                  style={{
                    fontFamily: mgTextFont(step.label, "inter"),
                    fontSize: 30,
                    fontWeight: 700,
                    color: effLabelColor,
                    textTransform: mgTextMetrics(step.label).uppercaseSafe
                      ? "uppercase"
                      : "none",
                    letterSpacing: "0.06em",
                    textAlign: "center",
                    marginTop: 24,
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
    const captionText = asText(pt.caption);
    const words = captionText.split(" ");
    // Point title + caption are model text (font census 2026-08-26).
    const ptTitleMetrics = mgTextMetrics(pt.title);
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
            fontFamily: mgTextFont(pt.title, "anton"),
            // The payoff slide is the beat's HIT — it carries the accent and
            // the scale (pass #7c; was 56px floating in a ~850px void).
            fontSize: 96,
            fontWeight: 400,
            color: accentColor,
            textTransform: ptTitleMetrics.uppercaseSafe ? "uppercase" : "none",
            letterSpacing: "-0.01em",
            lineHeight: Math.max(1.0, ptTitleMetrics.lineHeight),
          }}
        >
          {pt.title}
        </div>

        <div
          style={{
            marginTop: 36,
            fontFamily: mgTextFont(captionText, "inter"),
            fontSize: 58,
            fontWeight: 600,
            lineHeight: 1.28,
            textAlign: "left",
          }}
        >
          {words.map((w, j) => {
            const activation = captionStart + j * WORD_STEP;
            const t = (localFrame - activation) / WORD_FADE;
            return (
              <span key={j} style={{ color: lerpColor(effMutedColor, effSpokenColor, t) }}>
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
