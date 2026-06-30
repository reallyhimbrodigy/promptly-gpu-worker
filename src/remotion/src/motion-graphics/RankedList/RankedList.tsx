import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { RankedListItem, RankedListProps } from "./types";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const clamp01 = (x: number): number => Math.max(0, Math.min(1, x));

const DEFAULT_TEXT_SHADOW =
  "0 2px 14px rgba(0,0,0,0.6), 0 1px 3px rgba(0,0,0,0.5)";
const START = 6;
const STAGGER = 11;
const REVEAL = 16;
const RANK_COL = 150;
const ROW_GAP = 30;

const DEFAULT_ITEMS: RankedListItem[] = [
  { label: "Consistency", value: "98" },
  { label: "Strong hooks", value: "91" },
  { label: "Storytelling", value: "84" },
  { label: "Clean editing", value: "76" },
];

export const RankedList: React.FC<RankedListProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  items = DEFAULT_ITEMS,
  order = "topDown",
  highlightTop = true,
  accentColor = "#FFC53D",
  width = 880,
  rankFontSize = 116,
  labelColor = "#FFFFFF",
  valueColor = "rgba(255,255,255,0.66)",
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
    { defaultEnterFrames: 20, defaultExitFrames: 18 },
  );

  if (!visible) return null;

  const rendered = items.slice(0, 5);
  const N = rendered.length;
  if (N === 0) return null;

  const exitOpacity = 1 - exitProgress;
  const exitY = -10 * exitProgress;

  // The last row to arrive (used to time the #1 bloom).
  const lastReveal = START + (N - 1) * STAGGER;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            width,
            display: "flex",
            flexDirection: "column",
            gap: ROW_GAP,
            opacity: exitOpacity,
            transform: `translateY(${exitY.toFixed(2)}px)`,
          }}
        >
          {rendered.map((item, i) => {
            const isTop = i === 0 && highlightTop;
            // Reveal sequencing — topDown reveals #1 first, bottomUp saves it.
            const seq = order === "bottomUp" ? N - 1 - i : i;
            const act = START + seq * STAGGER;

            const rowOpacity = interpolate(localFrame, [act, act + 9], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            });
            const rowX = interpolate(localFrame, [act, act + REVEAL], [-24, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const rankPop = interpolate(
              localFrame,
              [act, act + 7, act + REVEAL],
              [0.8, 1.06, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
            const ruleScale = interpolate(
              localFrame,
              [act + 4, act + REVEAL + 4],
              [0, 1],
              {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: easeOutCubic,
              },
            );

            // #1 bloom after every row has landed.
            const bloom = isTop
              ? interpolate(
                  localFrame,
                  [lastReveal + 4, lastReveal + 12, lastReveal + 28],
                  [0, 1, 0.4],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                )
              : 0;
            const topScale = isTop ? 1 + 0.04 * clamp01(bloom * 2) : 1;

            const rankColor = isTop ? accentColor : "#FFFFFF";
            const rankShadow = isTop
              ? `${textShadow}, 0 0 ${(18 * bloom).toFixed(1)}px ${accentColor}, 0 0 ${(38 * bloom).toFixed(1)}px ${accentColor}66`
              : textShadow;

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  opacity: rowOpacity,
                  transform: `translateX(${rowX.toFixed(2)}px) scale(${topScale.toFixed(4)})`,
                  transformOrigin: "left center",
                }}
              >
                <div style={{ display: "flex", alignItems: "baseline" }}>
                  {/* Hero rank numeral */}
                  <div
                    style={{
                      width: RANK_COL,
                      flexShrink: 0,
                      textAlign: "right",
                      paddingRight: 28,
                      fontFamily: MG_FONTS.anton,
                      fontSize: rankFontSize,
                      fontWeight: 400,
                      lineHeight: 0.9,
                      letterSpacing: "-0.02em",
                      color: rankColor,
                      fontVariantNumeric: "tabular-nums",
                      transform: `scale(${rankPop.toFixed(4)})`,
                      transformOrigin: "right bottom",
                      textShadow: rankShadow,
                    }}
                  >
                    {item.rank ?? String(i + 1)}
                  </div>

                  {/* Label */}
                  <div
                    style={{
                      flexGrow: 1,
                      fontFamily: MG_FONTS.inter,
                      fontSize: 50,
                      fontWeight: 700,
                      color: labelColor,
                      letterSpacing: "-0.01em",
                      lineHeight: 1.05,
                      textShadow,
                    }}
                  >
                    {item.label}
                  </div>

                  {/* Optional value */}
                  {item.value ? (
                    <div
                      style={{
                        flexShrink: 0,
                        marginLeft: 24,
                        fontFamily: MG_FONTS.inter,
                        fontSize: 46,
                        fontWeight: 700,
                        color: isTop ? accentColor : valueColor,
                        letterSpacing: "0.01em",
                        lineHeight: 1,
                        fontVariantNumeric: "tabular-nums",
                        textShadow,
                      }}
                    >
                      {item.value}
                    </div>
                  ) : null}
                </div>

                {/* Accent rule under the row */}
                <div
                  style={{
                    marginTop: 16,
                    marginLeft: RANK_COL,
                    height: isTop ? 3 : 2,
                    borderRadius: 2,
                    background: isTop
                      ? accentColor
                      : "rgba(255,255,255,0.26)",
                    transform: `scaleX(${ruleScale.toFixed(3)})`,
                    transformOrigin: "left center",
                    boxShadow: isTop ? `0 0 ${(10 * bloom).toFixed(1)}px ${accentColor}` : undefined,
                  }}
                />
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
