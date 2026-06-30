import React from "react";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { TimelineRoadmapProps, TimelineRoadmapStep } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

const DEFAULT_TEXT_SHADOW =
  "0 3px 16px rgba(0,0,0,0.7), 0 1px 3px rgba(0,0,0,0.6)";
const START = 8;
const SEG = 18; // frames per node-to-node curve segment
const POP = 16;
const SPINE_W = 9;
const LABEL_OFFSET = 30;
const TICK = 30;

const DEFAULT_STEPS: TimelineRoadmapStep[] = [
  { label: "Discovery", sublabel: "Week 1" },
  { label: "Design", sublabel: "Week 2" },
  { label: "Build", sublabel: "Weeks 3–5" },
  { label: "Launch", sublabel: "Week 6" },
];

interface Pt {
  x: number;
  y: number;
}
interface Seg {
  p0: Pt;
  c1: Pt;
  c2: Pt;
  p1: Pt;
}
// Evaluate a cubic bezier segment at t (used to ride the comet along the curve).
const bez = (s: Seg, t: number): Pt => {
  const u = 1 - t;
  return {
    x:
      u * u * u * s.p0.x +
      3 * u * u * t * s.c1.x +
      3 * u * t * t * s.c2.x +
      t * t * t * s.p1.x,
    y:
      u * u * u * s.p0.y +
      3 * u * u * t * s.c1.y +
      3 * u * t * t * s.c2.y +
      t * t * t * s.p1.y,
  };
};

export const TimelineRoadmap: React.FC<TimelineRoadmapProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  steps = DEFAULT_STEPS,
  accentColor = "#FF8A1E",
  trackColor = "rgba(255,255,255,0.18)",
  nodeSize = 96,
  width = 1040,
  rowHeight = 312,
  firstSide = "right",
  labelColor = "#FFFFFF",
  indexColor = "#FFFFFF",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 54 },
  );
  const gradId = `rmGrad${React.useId().replace(/:/g, "")}`;

  if (!visible) return null;

  const rendered = steps.slice(0, 6);
  const N = rendered.length;
  if (N === 0) return null;

  const R = nodeSize / 2;
  const inactiveColor = "rgba(255,255,255,0.5)";
  const indexSize = Math.round(nodeSize * 0.4);
  const blockHeight = (N - 1) * rowHeight + nodeSize;

  // Node x alternates side-to-side → the snake. Label sits opposite the node.
  const xLeft = width * 0.27;
  const xRight = width * 0.73;
  const labelOnRight = (i: number): boolean =>
    firstSide === "right" ? i % 2 === 0 : i % 2 === 1;
  const yFor = (i: number): number => R + i * rowHeight;
  const nodeXFor = (i: number): number => (labelOnRight(i) ? xLeft : xRight);
  const pts: Pt[] = rendered.map((_, i) => ({ x: nodeXFor(i), y: yFor(i) }));

  // Build the serpentine path: vertical tangents at each node give a smooth,
  // continuous S-flow (a deep handle makes the bends round, not kinked). Keep
  // each segment's control points so the comet rides the curve exactly.
  const SWING = 0.62; // how far the curve bulges vertically into each bend
  const segs: Seg[] = [];
  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 1; i < N; i++) {
    const p0 = pts[i - 1];
    const p1 = pts[i];
    const dy = p1.y - p0.y;
    const c1 = { x: p0.x, y: p0.y + dy * SWING };
    const c2 = { x: p1.x, y: p1.y - dy * SWING };
    d += ` C ${c1.x.toFixed(2)} ${c1.y.toFixed(2)} ${c2.x.toFixed(2)} ${c2.y.toFixed(2)} ${p1.x.toFixed(2)} ${p1.y.toFixed(2)}`;
    segs.push({ p0, c1, c2, p1 });
  }

  // Draw fraction along the curve: grows segment-by-segment on entrance, then
  // RETRACTS back toward the start on exit so the beam un-draws itself.
  const reach = (i: number): number => START + i * SEG;
  const segCount = N - 1;
  let entUnits = 0;
  if (segCount > 0) {
    const si = Math.max(
      0,
      Math.min(segCount - 1, Math.floor((localFrame - START) / SEG)),
    );
    const ts = clamp01((localFrame - reach(si)) / SEG);
    entUnits = si + easeInOutCubic(ts);
  }
  const entFrac =
    segCount > 0 ? clamp01(entUnits / segCount) : localFrame >= START ? 1 : 0;

  // The drawn beam is the window [sFrac, eFrac]. On entrance the head (eFrac)
  // advances. On exit the TAIL (sFrac) advances forward to the end, so the whole
  // line flows off in the same direction it was drawn (it doesn't rewind).
  const sweep = easeInOutCubic(clamp01(exitProgress));
  const eFrac = entFrac;
  const sFrac = sweep;
  const visLen = Math.max(0, eFrac - sFrac);

  // The moving edge: drawing head on entrance, sweeping tail on exit.
  const tipFrac = sweep > 0 ? sFrac : eFrac;
  let sIndex = 0;
  let tSeg = 0;
  if (segCount > 0) {
    const units = tipFrac * segCount;
    sIndex = Math.max(0, Math.min(segCount - 1, Math.floor(units)));
    tSeg = clamp01(units - sIndex);
  }
  const comet = segs.length ? bez(segs[sIndex], tSeg) : pts[0];
  const hp = clamp01(comet.y / blockHeight); // tip position for the gradient
  const lastReach = reach(N - 1);

  const enterOpacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Comet only rides the drawing head on entrance — no head dot during the
  // exit sweep (it read as a stray pulsing dot at the tail).
  const headOpacity =
    segCount > 0
      ? interpolate(
          localFrame,
          [START, START + 5, lastReach, lastReach + 12],
          [0, 1, 1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        )
      : 0;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            width,
            height: blockHeight,
            opacity: enterOpacity,
            transformOrigin: "center",
          }}
        >
          {/* Serpentine beam (SVG): flowing dotted "route ahead" + a glowing
              accent draw-on with a white-hot gradient tip and a gloss core. */}
          <svg
            width={width}
            height={blockHeight}
            viewBox={`0 0 ${width} ${blockHeight}`}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              overflow: "visible",
              zIndex: 0,
            }}
          >
            <defs>
              {/* White-hot zone tracks the comet's vertical position, fading to
                  accent behind it — reads as energy flowing to the leading tip. */}
              <linearGradient
                id={gradId}
                gradientUnits="userSpaceOnUse"
                x1={0}
                y1={0}
                x2={0}
                y2={blockHeight}
              >
                {sweep > 0 ? (
                  // Exit: flat accent — no white-hot tip (it pooled into a
                  // glowing dot at the sweeping tail / start node).
                  <>
                    <stop offset={0} stopColor={accentColor} />
                    <stop offset={1} stopColor={accentColor} />
                  </>
                ) : (
                  <>
                    <stop offset={0} stopColor={accentColor} />
                    <stop offset={Math.max(0, hp - 0.16)} stopColor={accentColor} />
                    <stop offset={Math.max(0.001, hp - 0.04)} stopColor="#FFE9C7" />
                    <stop offset={hp} stopColor="#FFFFFF" />
                    <stop offset={Math.min(1, hp + 0.015)} stopColor={accentColor} />
                    <stop offset={1} stopColor={accentColor} />
                  </>
                )}
              </linearGradient>
            </defs>

            {/* Route ahead — flowing dots (fade off as the line sweeps away) */}
            <path
              d={d}
              fill="none"
              stroke="rgba(255,255,255,0.30)"
              strokeWidth={SPINE_W * 0.7}
              strokeLinecap="round"
              strokeDasharray="0.2 22"
              strokeDashoffset={-localFrame * 1.1}
              style={{ opacity: clamp01(1 - sweep * 5) }}
            />
            {/* Soft accent glow underlay */}
            <path
              d={d}
              fill="none"
              stroke={accentColor}
              strokeWidth={SPINE_W * 2.8}
              strokeLinecap="round"
              pathLength={1}
              strokeDasharray={`${visLen.toFixed(4)} 2`}
              strokeDashoffset={-sFrac}
              style={{ filter: "blur(8px)", opacity: 0.6 }}
            />
            {/* Gradient core (white-hot tip → accent) */}
            <path
              d={d}
              fill="none"
              stroke={`url(#${gradId})`}
              strokeWidth={SPINE_W}
              strokeLinecap="round"
              pathLength={1}
              strokeDasharray={`${visLen.toFixed(4)} 2`}
              strokeDashoffset={-sFrac}
            />
            {/* Gloss center line */}
            <path
              d={d}
              fill="none"
              stroke="rgba(255,255,255,0.6)"
              strokeWidth={1.6}
              strokeLinecap="round"
              pathLength={1}
              strokeDasharray={`${visLen.toFixed(4)} 2`}
              strokeDashoffset={-sFrac}
            />
          </svg>

          {/* Comet head riding the curve */}
          {headOpacity > 0 ? (
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 0,
                opacity: headOpacity,
                zIndex: 2,
                pointerEvents: "none",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: comet.x,
                  top: comet.y,
                  width: 46,
                  height: 46,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  background: `radial-gradient(circle, ${accentColor}ee 0%, ${accentColor}00 70%)`,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: comet.x,
                  top: comet.y,
                  width: 14,
                  height: 14,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  background: "#FFFFFF",
                  boxShadow: `0 0 10px ${accentColor}, 0 0 20px ${accentColor}`,
                }}
              />
            </div>
          ) : null}

          {/* Nodes — flat glowing waypoints (no glass) */}
          {rendered.map((step, i) => {
            const act = reach(i);
            const reached = localFrame >= act;
            const nodeScale = reached
              ? interpolate(localFrame, [act, act + POP], [0.5, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: easeOutBack,
                })
              : 0.5;
            const nodeOpacity = reached
              ? interpolate(localFrame, [act, act + 6], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              : interpolate(localFrame, [act - 10, act], [0, 0.4], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
            const colorT = reached ? clamp01((localFrame - act) / 12) : 0;
            const ringColor = interpolateColors(
              colorT,
              [0, 1],
              [inactiveColor, accentColor],
            );
            const idxColor = interpolateColors(
              colorT,
              [0, 1],
              [inactiveColor, indexColor],
            );
            const fillScale = reached
              ? easeOutBack(clamp01((localFrame - act) / POP))
              : 0;
            // Idle glow pulse — settle to a steady (non-pulsing) glow once the
            // exit sweep starts so a node doesn't read as a pulsing dot while it
            // waits to fade off.
            const idleAmt = reached ? clamp01((localFrame - act - 14) / 14) : 0;
            const idleGlow =
              idleAmt *
              (10 + 10 * (0.5 + 0.5 * Math.sin((localFrame - act) * 0.09)) * (1 - sweep));

            // Arrival orbit-ring pulse.
            const ringScale = interpolate(localFrame, [act, act + 22], [0.7, 1.8], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const ringOpacity = reached
              ? interpolate(localFrame, [act, act + 4, act + 24], [0, 0.55, 0], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              : 0;

            // Exit: each node fades + drifts along the flow direction as the
            // sweeping tail passes it (start node leaves first — same as flow).
            const nodeFrac = segCount > 0 ? i / segCount : 0;
            const gone = clamp01((sweep - nodeFrac * 0.8) / 0.18);
            const fa = pts[Math.max(0, i - 1)];
            const fb = pts[Math.min(N - 1, i + 1)];
            const flv = Math.hypot(fb.x - fa.x, fb.y - fa.y) || 1;
            const exitDX = ((fb.x - fa.x) / flv) * 80 * gone;
            const exitDY = ((fb.y - fa.y) / flv) * 80 * gone;
            const exitScaleN = 1 - 0.4 * gone;

            return (
              <div
                key={`node-${i}`}
                style={{
                  position: "absolute",
                  left: nodeXFor(i) - R,
                  top: yFor(i) - R,
                  width: nodeSize,
                  height: nodeSize,
                  transform: `translate(${exitDX.toFixed(2)}px, ${exitDY.toFixed(2)}px) scale(${(nodeScale * exitScaleN).toFixed(4)})`,
                  transformOrigin: "center",
                  opacity: nodeOpacity * (1 - gone),
                  zIndex: 4,
                  willChange: "transform",
                }}
              >
                {/* Arrival orbit ring */}
                {ringOpacity > 0 ? (
                  <div
                    style={{
                      position: "absolute",
                      inset: -6,
                      borderRadius: "50%",
                      border: `2px solid ${accentColor}`,
                      transform: `scale(${ringScale})`,
                      opacity: ringOpacity,
                      pointerEvents: "none",
                    }}
                  />
                ) : null}

                {/* Base disc — solid dark, accent ring, glow on activation */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: "50%",
                    background: "#0E1117",
                    border: `3px solid ${ringColor}`,
                    boxShadow: `0 10px 24px rgba(0,0,0,0.55), 0 0 ${(idleGlow + 8 * fillScale).toFixed(2)}px ${accentColor}`,
                  }}
                />

                {/* Solid accent fill on reach */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: "50%",
                    background: `radial-gradient(circle at 38% 32%, ${accentColor}, ${accentColor}d8)`,
                    transform: `scale(${fillScale.toFixed(4)})`,
                    transformOrigin: "center",
                  }}
                />

                {/* Index numeral */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <span
                    style={{
                      fontFamily: MG_FONTS.jetBrainsMono,
                      fontSize: indexSize,
                      fontWeight: 700,
                      color: idxColor,
                      letterSpacing: "-0.02em",
                      lineHeight: 1,
                      fontVariantNumeric: "tabular-nums",
                      textShadow: "0 1px 3px rgba(0,0,0,0.55)",
                    }}
                  >
                    {step.index ?? String(i + 1).padStart(2, "0")}
                  </span>
                </div>
              </div>
            );
          })}

          {/* Labels — light editorial text + accent connector tick + sublabel pill */}
          {rendered.map((step, i) => {
            const act = reach(i);
            const onRight = labelOnRight(i);
            const nodeX = nodeXFor(i);
            const labelOpacity = interpolate(localFrame, [act + 5, act + 18], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const slide = interpolate(localFrame, [act + 5, act + 22], [26, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const tickGrow = interpolate(localFrame, [act + 2, act + 16], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const pillPop = interpolate(localFrame, [act + 12, act + 24], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutBack,
            });
            const dir = onRight ? 1 : -1;

            // Exit: same cascade as the nodes — fade + drift along the flow.
            const nodeFrac = segCount > 0 ? i / segCount : 0;
            const gone = clamp01((sweep - nodeFrac * 0.8) / 0.18);
            const fa = pts[Math.max(0, i - 1)];
            const fb = pts[Math.min(N - 1, i + 1)];
            const flv = Math.hypot(fb.x - fa.x, fb.y - fa.y) || 1;
            const exitDX = ((fb.x - fa.x) / flv) * 80 * gone;
            const exitDY = ((fb.y - fa.y) / flv) * 80 * gone;

            const anchorStyle: React.CSSProperties = onRight
              ? { left: nodeX + R }
              : { right: width - (nodeX - R) };

            return (
              <div
                key={`label-${i}`}
                style={{
                  position: "absolute",
                  top: yFor(i),
                  ...anchorStyle,
                  transform: `translateY(-50%) translateX(${(dir * slide).toFixed(2)}px) translate(${exitDX.toFixed(2)}px, ${exitDY.toFixed(2)}px)`,
                  opacity: labelOpacity * (1 - gone),
                  zIndex: 3,
                  display: "flex",
                  flexDirection: onRight ? "row" : "row-reverse",
                  alignItems: "center",
                  gap: LABEL_OFFSET - TICK + 14,
                }}
              >
                {/* Connector tick */}
                <div
                  style={{
                    flex: "0 0 auto",
                    width: TICK,
                    height: 4,
                    borderRadius: 2,
                    background: accentColor,
                    boxShadow: `0 0 10px ${accentColor}aa`,
                    transform: `scaleX(${tickGrow.toFixed(3)})`,
                    transformOrigin: onRight ? "left center" : "right center",
                  }}
                />

                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: onRight ? "flex-start" : "flex-end",
                    gap: 10,
                  }}
                >
                  <div
                    style={{
                      fontFamily: MG_FONTS.inter,
                      fontSize: 58,
                      fontWeight: 800,
                      color: labelColor,
                      letterSpacing: "-0.015em",
                      lineHeight: 1.02,
                      textTransform: "uppercase",
                      whiteSpace: "nowrap",
                      textAlign: onRight ? "left" : "right",
                      textShadow,
                    }}
                  >
                    {step.label}
                  </div>
                  {step.sublabel ? (
                    <div
                      style={{
                        transform: `scale(${pillPop.toFixed(3)})`,
                        transformOrigin: onRight ? "left center" : "right center",
                        padding: "6px 18px",
                        borderRadius: 999,
                        background: accentColor,
                        fontFamily: MG_FONTS.inter,
                        fontSize: 28,
                        fontWeight: 700,
                        color: "#10131A",
                        letterSpacing: "0.03em",
                        lineHeight: 1.1,
                        textTransform: "uppercase",
                        whiteSpace: "nowrap",
                        boxShadow: `0 4px 14px ${accentColor}66`,
                      }}
                    >
                      {step.sublabel}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
