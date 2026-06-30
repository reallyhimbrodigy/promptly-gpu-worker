import React from "react";
import { AbsoluteFill, interpolate, interpolateColors } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { RaceBarItem, BarRaceProps } from "./types";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
// Overshooting ease for the crown pop.
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
// 0..1 → 2-digit hex alpha, for fading colour glows smoothly.
const hexA = (a: number): string =>
  Math.round(clamp01(a) * 255)
    .toString(16)
    .padStart(2, "0");

const DEFAULT_TEXT_SHADOW =
  "0 2px 12px rgba(0,0,0,0.6), 0 1px 3px rgba(0,0,0,0.5)";
const START = 8;
const STAGGER = 7; // compare-mode start offset per bar
const GROW = 32; // grow duration
const ROW_H = 162;
const BAR_H = 56;
const LABEL_H = 52;
const LABEL_GAP = 16; // breathing room between label and bar
const VALUE_RESERVE = 148; // right space reserved for the tip value
const SHEEN_W = 82; // width of the traveling light sweep
const BADGE = 48; // rank badge diameter
const NEUTRAL = "#FFFFFF"; // runners-up fill; leader uses accentColor

const DEFAULT_BARS: RaceBarItem[] = [
  { label: "Organic", value: 82 },
  { label: "Referral", value: 64 },
  { label: "Paid ads", value: 41 },
];

export const BarRace: React.FC<BarRaceProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  bars = DEFAULT_BARS,
  maxValue,
  mode = "compare",
  valuePrefix = "",
  valueSuffix = "",
  accentColor = "#FFB23E",
  width = 880,
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
    { defaultEnterFrames: 22, defaultExitFrames: 18 },
  );

  if (!visible) return null;

  const rendered = bars.slice(0, 4);
  const N = rendered.length;
  if (N === 0) return null;

  const maxVal = Math.max(
    1,
    maxValue ?? Math.max(...rendered.map((b) => b.value)),
  );
  const barAreaW = width - VALUE_RESERVE;
  const blockHeight = N * ROW_H;
  const eps = maxVal * 0.05;

  const exitOpacity = 1 - exitProgress;
  const exitY = -10 * exitProgress;

  // Current animated value of bar i.
  const curValue = (i: number): number => {
    const act = mode === "race" ? START : START + i * STAGGER;
    const grow = easeOutCubic(clamp01((localFrame - act) / GROW));
    return rendered[i].value * grow;
  };

  const leaderFinalIndex = rendered.reduce(
    (best, b, i) => (b.value > rendered[best].value ? i : best),
    0,
  );
  const settleFrame = START + (N - 1) * STAGGER + GROW;

  // Final rank (1-based) by value, for the compare-mode badges.
  const compareRank: number[] = [];
  rendered
    .map((_, i) => i)
    .sort((a, b) => rendered[b].value - rendered[a].value)
    .forEach((idx, r) => {
      compareRank[idx] = r + 1;
    });

  // Continuous vertical rank for race mode (smooth crossovers).
  const fracRank = (i: number): number => {
    const ci = curValue(i);
    let r = 0;
    for (let j = 0; j < N; j++) {
      if (j === i) continue;
      const cj = curValue(j);
      r += clamp01((cj - ci) / eps + 0.5);
    }
    return r;
  };

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            width,
            height: blockHeight,
            opacity: exitOpacity,
            transform: `translateY(${exitY.toFixed(2)}px)`,
          }}
        >
          {rendered.map((bar, i) => {
            const cur = curValue(i);
            const fillW = barAreaW * clamp01(cur / maxVal);

            // Leader signal (0..1): compare → eases in over ~20 frames on
            // settle so the gold washes in; race → continuous from the live
            // rank. Either way it never snaps from a hard threshold.
            const emphasis =
              mode === "race"
                ? clamp01(1 - fracRank(i))
                : i === leaderFinalIndex
                  ? interpolate(
                      localFrame,
                      [settleFrame - 4, settleFrame + 18],
                      [0, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                        easing: easeInOutCubic,
                      },
                    )
                  : 0;
            // Which row owns the crown + glow (independent of the blend amount).
            const isLeaderRow =
              mode === "race" ? fracRank(i) < 0.5 : i === leaderFinalIndex;

            const rank =
              mode === "race" ? Math.round(fracRank(i)) + 1 : compareRank[i];
            // Fill blends white → accent as the leader signal rises (no snap).
            const fillColor =
              bar.color ??
              interpolateColors(emphasis, [0, 1], [NEUTRAL, accentColor]);
            const glowColor = bar.color ?? accentColor;

            // Single leader pulse on settle (compare only).
            const pulse =
              mode === "compare" && i === leaderFinalIndex
                ? interpolate(
                    localFrame,
                    [settleFrame, settleFrame + 5, settleFrame + 13],
                    [1, 1.04, 1],
                    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                  )
                : 1;

            const act = mode === "race" ? START : START + i * STAGGER;
            const rowOpacity = interpolate(localFrame, [act, act + 8], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });

            // One-shot light sweep that travels the bar once it finishes growing.
            const sweepStart = act + GROW - 6;
            const sweep = clamp01((localFrame - sweepStart) / 22);
            const sweepX = sweep * (fillW + SHEEN_W) - SHEEN_W;
            const sweepOpacity =
              sweep > 0 && sweep < 1
                ? Math.sin(sweep * Math.PI) * 0.9
                : 0;

            const y = mode === "race" ? fracRank(i) * ROW_H : i * ROW_H;
            const valueColor =
              bar.color ??
              interpolateColors(emphasis, [0, 1], ["#FFFFFF", accentColor]);

            // Crown on the leader's value: pops in with the leader emphasis,
            // then idly bobs + tilts once it has settled.
            const settleAmt = clamp01((emphasis - 0.6) / 0.4);
            const crownScale = easeOutBack(clamp01(emphasis));
            const crownOpacity = clamp01(emphasis * 1.4);
            const crownY =
              -14 * (1 - clamp01(emphasis)) +
              Math.sin(localFrame * 0.16) * 5 * settleAmt;
            const crownRot = Math.sin(localFrame * 0.12) * 5 * settleAmt;

            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: 0,
                  top: y,
                  width,
                  height: ROW_H,
                  opacity: rowOpacity,
                  willChange: "top",
                }}
              >
                {/* Label row: rank badge + name */}
                <div
                  style={{
                    height: LABEL_H,
                    display: "flex",
                    alignItems: "center",
                    gap: 16,
                  }}
                >
                  <div
                    style={{
                      width: BADGE,
                      height: BADGE,
                      borderRadius: BADGE / 2,
                      flexShrink: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: MG_FONTS.inter,
                      fontSize: 25,
                      fontWeight: 800,
                      color: "#0B1220",
                      backgroundColor: fillColor,
                      boxShadow: `0 5px 18px ${glowColor}${hexA(emphasis * 0.66)}`,
                    }}
                  >
                    {rank}
                  </div>
                  <div
                    style={{
                      fontFamily: MG_FONTS.inter,
                      fontSize: 40,
                      fontWeight: 700,
                      // Blends white → accent in step with the bar fill.
                      color: valueColor,
                      letterSpacing: "0.005em",
                      lineHeight: 1,
                      textShadow,
                    }}
                  >
                    {bar.label}
                  </div>
                </div>

                {/* Track */}
                <div
                  style={{
                    position: "relative",
                    marginTop: LABEL_GAP,
                    width: barAreaW,
                    height: BAR_H,
                    borderRadius: BAR_H / 2,
                    backgroundColor: "transparent",
                  }}
                >
                  {/* Fill */}
                  <div
                    style={{
                      position: "absolute",
                      left: 0,
                      top: 0,
                      width: fillW,
                      height: BAR_H,
                      borderRadius: BAR_H / 2,
                      overflow: "hidden",
                      backgroundColor: fillColor,
                      // Tip-brightening horizontal pass + a vertical gloss.
                      backgroundImage:
                        "linear-gradient(90deg, rgba(0,0,0,0.16) 0%, rgba(0,0,0,0) 50%, rgba(255,255,255,0.26) 100%), linear-gradient(180deg, rgba(255,255,255,0.40) 0%, rgba(255,255,255,0) 50%, rgba(0,0,0,0.22) 100%)",
                      transform: `scaleY(${pulse.toFixed(4)})`,
                      transformOrigin: "center",
                      // Warm glow fades in with the leader signal (no snap).
                      boxShadow: `0 0 ${(44 * emphasis).toFixed(1)}px ${glowColor}${hexA(emphasis * 0.73)}, inset 0 1px 0 rgba(255,255,255,${(0.5 + 0.15 * emphasis).toFixed(2)})`,
                      willChange: "width",
                    }}
                  >
                    {/* Traveling sheen */}
                    {sweepOpacity > 0 ? (
                      <div
                        style={{
                          position: "absolute",
                          top: 0,
                          left: sweepX,
                          width: SHEEN_W,
                          height: BAR_H,
                          transform: "skewX(-18deg)",
                          background:
                            "linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.85) 50%, rgba(255,255,255,0) 100%)",
                          opacity: sweepOpacity,
                        }}
                      />
                    ) : null}
                  </div>

                  {/* Tip value */}
                  <div
                    style={{
                      position: "absolute",
                      left: fillW + 18,
                      top: "50%",
                      transform: "translateY(-50%)",
                      display: "flex",
                      alignItems: "baseline",
                      fontFamily: MG_FONTS.inter,
                      lineHeight: 1,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {/* Crown above the leader's percentage */}
                    {isLeaderRow && crownOpacity > 0.01 ? (
                      <div
                        style={{
                          position: "absolute",
                          left: 8,
                          bottom: "100%",
                          marginBottom: 10,
                          opacity: crownOpacity,
                          transformOrigin: "center bottom",
                          transform: `translateY(${crownY.toFixed(2)}px) scale(${crownScale.toFixed(3)}) rotate(${crownRot.toFixed(2)}deg)`,
                          filter: `drop-shadow(0 4px 9px ${glowColor}aa)`,
                        }}
                      >
                        <svg
                          width="58"
                          height="46"
                          viewBox="0 0 64 50"
                          fill="none"
                        >
                          <path
                            d="M8 43 L4 13 L22 26 L32 7 L42 26 L60 13 L56 43 Z"
                            fill={glowColor}
                            stroke="rgba(0,0,0,0.28)"
                            strokeWidth="2.5"
                            strokeLinejoin="round"
                          />
                          <rect
                            x="8"
                            y="39"
                            width="48"
                            height="8"
                            rx="2.5"
                            fill={glowColor}
                            stroke="rgba(0,0,0,0.28)"
                            strokeWidth="2.5"
                          />
                          <circle cx="4" cy="13" r="3.4" fill="#FFF6DC" />
                          <circle cx="32" cy="7" r="3.8" fill="#FFF6DC" />
                          <circle cx="60" cy="13" r="3.4" fill="#FFF6DC" />
                        </svg>
                      </div>
                    ) : null}
                    <span
                      style={{
                        fontSize: 42,
                        fontWeight: 800,
                        color: valueColor,
                        letterSpacing: "0.01em",
                        fontVariantNumeric: "tabular-nums",
                        textShadow,
                      }}
                    >
                      {valuePrefix}
                      {Math.round(cur)}
                    </span>
                    {valueSuffix ? (
                      <span
                        style={{
                          fontSize: 26,
                          fontWeight: 700,
                          marginLeft: 2,
                          color: valueColor,
                          opacity: 0.72,
                          textShadow,
                        }}
                      >
                        {valueSuffix}
                      </span>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
