import React from "react";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { TimelineProps, TimelineStep } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

// Titles sit on a solid slab, so no shadow is needed for legibility by default.
const DEFAULT_TEXT_SHADOW = "none";
const START = 8;
const SEG = 18; // frames to advance the rail one node-to-node segment
const POP = 16; // node spring length
const RAIL_W = 6;

const DEFAULT_STEPS: TimelineStep[] = [
  { label: "Research", description: "Find the real problem" },
  { label: "Design", description: "Shape the solution" },
  { label: "Ship", description: "Put it in the world" },
];

export const Timeline: React.FC<TimelineProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  steps = DEFAULT_STEPS,
  accentColor = "#FF8A1E",
  trackColor = "rgba(255,255,255,0.16)",
  nodeSize = 84,
  width = 880,
  rowGap = 210,
  labelColor = "#15171E",
  indexColor = "#FFFFFF",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center", offsetY: 0 },
  );
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 22 },
  );

  if (!visible) return null;

  const rendered = steps.slice(0, 5);
  const N = rendered.length;
  if (N === 0) return null;

  const R = nodeSize / 2;
  const inactiveColor = "rgba(255,255,255,0.5)";
  const railX = R; // rail centre line, x within the block
  const yFor = (i: number): number => R + i * rowGap; // node centre Y
  const railLen = (N - 1) * rowGap; // node0 centre → nodeN-1 centre
  const indexSize = Math.round(nodeSize * 0.36);

  const cardLeft = nodeSize + 44;
  const cardWidth = width - cardLeft;
  const blockHeight = railLen + nodeSize + 60;

  // Rail fill travels node-to-node, easing each segment.
  const reach = (i: number): number => START + i * SEG;
  const segCount = N - 1;
  let fillDist = 0;
  if (segCount > 0) {
    const sIndex = Math.max(
      0,
      Math.min(segCount - 1, Math.floor((localFrame - START) / SEG)),
    );
    const tSeg = clamp01((localFrame - reach(sIndex)) / SEG);
    fillDist = rowGap * (sIndex + easeInOutCubic(tSeg));
  }
  const headY = R + fillDist;
  const lastReach = reach(N - 1);

  // Rail draw-on, then group entrance/exit.
  const railDraw = interpolate(localFrame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const enterOpacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Matched exit: accelerating fade with a gentle scale-down + upward drift.
  const eExit = exitProgress * exitProgress;
  const exitOpacity = 1 - eExit;
  const exitScale = 1 - 0.07 * eExit;
  const exitY = -34 * eExit;

  // Comet head visible only while the fill is travelling.
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
            opacity: enterOpacity * exitOpacity,
            transform: `translateY(${exitY.toFixed(2)}px) scale(${exitScale.toFixed(4)})`,
            transformOrigin: "center",
          }}
        >
          {/* Rail */}
          <div
            style={{
              position: "absolute",
              left: railX - RAIL_W / 2,
              top: R,
              width: RAIL_W,
              height: railLen,
              borderRadius: RAIL_W / 2,
              backgroundColor: trackColor,
              transform: `scaleY(${railDraw.toFixed(3)})`,
              transformOrigin: "top center",
              boxShadow:
                "inset 0 1px 2px rgba(0,0,0,0.35), 0 2px 8px rgba(0,0,0,0.28)",
              zIndex: 0,
            }}
          />

          {/* Accent fill */}
          <div
            style={{
              position: "absolute",
              left: railX - RAIL_W / 2,
              top: R,
              width: RAIL_W,
              height: fillDist,
              borderRadius: RAIL_W / 2,
              backgroundColor: accentColor,
              backgroundImage: `linear-gradient(90deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.10) 42%, rgba(0,0,0,0.12) 100%)`,
              boxShadow: `0 0 16px ${accentColor}aa, 0 1px 4px rgba(0,0,0,0.3)`,
              zIndex: 1,
              willChange: "height",
            }}
          />

          {/* Comet head — bright core + soft glow + trailing tail */}
          {headOpacity > 0 ? (
            <div
              style={{
                position: "absolute",
                left: railX,
                top: 0,
                opacity: headOpacity,
                zIndex: 2,
                pointerEvents: "none",
              }}
            >
              {/* Tail */}
              <div
                style={{
                  position: "absolute",
                  left: -RAIL_W / 2,
                  top: headY - 90,
                  width: RAIL_W,
                  height: 90,
                  borderRadius: RAIL_W / 2,
                  background: `linear-gradient(180deg, ${accentColor}00 0%, ${accentColor}cc 100%)`,
                }}
              />
              {/* Soft glow */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: headY,
                  width: 40,
                  height: 40,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  background: `radial-gradient(circle, ${accentColor}ee 0%, ${accentColor}00 70%)`,
                }}
              />
              {/* Bright core */}
              <div
                style={{
                  position: "absolute",
                  left: 0,
                  top: headY,
                  width: 13,
                  height: 13,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "50%",
                  background: "#FFFFFF",
                  boxShadow: `0 0 10px ${accentColor}, 0 0 18px ${accentColor}`,
                }}
              />
            </div>
          ) : null}

          {/* Cards — flat poster blocks: a solid accent slab offset behind a
              flat dark slab. No blur, hard graphic edges. */}
          {rendered.map((step, i) => {
            const act = reach(i);
            const cardOpacity = interpolate(
              localFrame,
              [act + 3, act + 16],
              [0, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: easeOutCubic,
              },
            );
            const cardX = interpolate(localFrame, [act + 3, act + 22], [50, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutBack,
            });
            // The accent slab settles out from behind for a lively "stacking" beat.
            const offset = interpolate(localFrame, [act + 6, act + 22], [0, 14], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutBack,
            });
            // Title rises up behind a clip mask; subline + ghost numeral stagger in.
            const titleRise = interpolate(localFrame, [act + 5, act + 24], [108, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const descOpacity = interpolate(localFrame, [act + 16, act + 28], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const descY = interpolate(localFrame, [act + 16, act + 30], [14, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const ruleGrow = interpolate(localFrame, [act + 10, act + 26], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const ghostOpacity = interpolate(localFrame, [act + 8, act + 26], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const ghostX = interpolate(localFrame, [act + 8, act + 28], [40, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const ghostNum = step.index ?? String(i + 1).padStart(2, "0");
            return (
              <div
                key={`card-${i}`}
                style={{
                  position: "absolute",
                  left: cardLeft,
                  top: yFor(i),
                  width: cardWidth,
                  height: 138,
                  transform: `translate(${cardX.toFixed(2)}px, -50%)`,
                  opacity: cardOpacity,
                  zIndex: 3,
                }}
              >
                {/* Offset accent slab — gradient for depth */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    transform: `translate(${offset.toFixed(2)}px, ${offset.toFixed(2)}px)`,
                    background: `linear-gradient(135deg, ${accentColor} 0%, ${accentColor} 58%, rgba(0,0,0,0.22) 100%)`,
                    borderRadius: 8,
                  }}
                />
                {/* Front flat slab */}
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    overflow: "hidden",
                    background: "#FFFFFF",
                    borderRadius: 8,
                    borderLeft: `7px solid ${accentColor}`,
                    boxShadow: "0 12px 30px rgba(0,0,0,0.42)",
                  }}
                >
                  {/* Oversized editorial ghost numeral filling the right space */}
                  <span
                    style={{
                      position: "absolute",
                      right: -6,
                      top: "50%",
                      transform: `translate(${ghostX.toFixed(1)}px, -50%)`,
                      fontFamily: MG_FONTS.inter,
                      fontSize: 168,
                      fontWeight: 900,
                      lineHeight: 1,
                      color: "rgba(20,22,28,0.05)",
                      letterSpacing: "-0.04em",
                      opacity: ghostOpacity,
                      pointerEvents: "none",
                      userSelect: "none",
                    }}
                  >
                    {ghostNum}
                  </span>

                  {/* Text column */}
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      gap: step.description ? 8 : 0,
                      padding: "0 30px",
                    }}
                  >
                    {/* Title — clip-mask rise */}
                    <span style={{ display: "block", overflow: "hidden", paddingBottom: 2 }}>
                      <span
                        style={{
                          display: "block",
                          transform: `translateY(${titleRise.toFixed(2)}%)`,
                          fontFamily: MG_FONTS.inter,
                          fontSize: 48,
                          fontWeight: 800,
                          color: labelColor,
                          letterSpacing: "-0.015em",
                          lineHeight: 1.0,
                          textTransform: "uppercase",
                          textShadow,
                        }}
                      >
                        {step.label}
                      </span>
                    </span>

                    {/* Accent rule under the title */}
                    <div
                      style={{
                        width: 56,
                        height: 5,
                        borderRadius: 3,
                        background: accentColor,
                        transform: `scaleX(${ruleGrow.toFixed(3)})`,
                        transformOrigin: "left center",
                      }}
                    />

                    {step.description ? (
                      <span
                        style={{
                          fontFamily: MG_FONTS.inter,
                          fontSize: 26,
                          fontWeight: 500,
                          color: "rgba(20,22,28,0.6)",
                          letterSpacing: "0.005em",
                          lineHeight: 1.2,
                          opacity: descOpacity,
                          transform: `translateY(${descY.toFixed(2)}px)`,
                        }}
                      >
                        {step.description}
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Nodes — flat rotated-diamond markers (drawn above cards so the rail
              reads as continuous). Solid accent on reach, ghost outline before. */}
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
            // The solid fill rotates into alignment with the ghost diamond.
            const fillRot = reached
              ? interpolate(localFrame, [act, act + POP], [0, 45], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: easeOutBack,
                })
              : 0;

            // Arrival square ring-pulse on every node when it lights up.
            const ringScale = interpolate(localFrame, [act, act + 20], [0.9, 1.9], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const ringOpacity = reached
              ? interpolate(localFrame, [act, act + 4, act + 22], [0, 0.5, 0], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              : 0;

            const shapeSize = nodeSize * 0.72;
            const shapeInset = (nodeSize - shapeSize) / 2;

            return (
              <div
                key={`node-${i}`}
                style={{
                  position: "absolute",
                  left: railX - R,
                  top: yFor(i) - R,
                  width: nodeSize,
                  height: nodeSize,
                  transform: `scale(${nodeScale.toFixed(4)})`,
                  transformOrigin: "center",
                  opacity: nodeOpacity,
                  zIndex: 4,
                  willChange: "transform",
                }}
              >
                {/* Arrival diamond ring-pulse */}
                {ringOpacity > 0 ? (
                  <div
                    style={{
                      position: "absolute",
                      left: shapeInset,
                      top: shapeInset,
                      width: shapeSize,
                      height: shapeSize,
                      border: `2px solid ${accentColor}`,
                      transform: `rotate(45deg) scale(${ringScale})`,
                      opacity: ringOpacity,
                      pointerEvents: "none",
                    }}
                  />
                ) : null}

                {/* Ghost diamond outline */}
                <div
                  style={{
                    position: "absolute",
                    left: shapeInset,
                    top: shapeInset,
                    width: shapeSize,
                    height: shapeSize,
                    transform: "rotate(45deg)",
                    border: `3px solid ${ringColor}`,
                    background: "rgba(10,11,15,0.30)",
                    boxShadow: "0 8px 20px rgba(0,0,0,0.45)",
                  }}
                />

                {/* Solid accent diamond fill on reach */}
                <div
                  style={{
                    position: "absolute",
                    left: shapeInset,
                    top: shapeInset,
                    width: shapeSize,
                    height: shapeSize,
                    transform: `rotate(${fillRot.toFixed(2)}deg) scale(${fillScale.toFixed(4)})`,
                    transformOrigin: "center",
                    background: accentColor,
                  }}
                />

                {/* Index numeral (kept upright) */}
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
                      textShadow: "0 1px 3px rgba(0,0,0,0.5)",
                    }}
                  >
                    {step.index ?? String(i + 1).padStart(2, "0")}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
