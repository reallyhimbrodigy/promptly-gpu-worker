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
// §4 pass (2026-08-25): the numeral is the BEHIND plane — oversized, tilted,
// and OCCLUDED by the label slab in front (occlusion of the graphic, never of
// text). Rows tuck slightly into each other and alternate a restrained tilt
// (lists die past ~2.5°). Was: a clean left-aligned vertical list — a slide.
const RANK_SIZE = 168;
const ROW_GAP = -6;


export const RankedList: React.FC<RankedListProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  items = [],
  order = "topDown",
  highlightTop = true,
  accentColor = "#FFC53D",
  // D4: fit the symmetric center box (max 680) — oversize dragged center right
  width = 680,
  rankFontSize = RANK_SIZE,   // kept in the props contract; RANK_SIZE is the §4 default
  labelColor = "#FFFFFF",
  valueColor = "rgba(255,255,255,0.66)",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  // v197 fail-closed: no invented content (DEFAULT_POINTS class).
  if (!items || items.length === 0) return null;
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
            const rowTilt = (i % 2 === 0 ? -1 : 1) * (1.2 + (i % 3) * 0.6);
            const rankFS = isTop ? RANK_SIZE * 1.12 : RANK_SIZE;
            const rankShadow = isTop
              ? `${textShadow}, 0 0 ${(18 * bloom).toFixed(1)}px ${accentColor}, 0 0 ${(38 * bloom).toFixed(1)}px ${accentColor}66`
              : textShadow;

            return (
              <div
                key={i}
                style={{
                  position: "relative",
                  opacity: rowOpacity,
                  translate: `${rowX.toFixed(2)}px 0px`,
                  scale: String(topScale.toFixed(4)),
                  rotate: `${rowTilt.toFixed(1)}deg`,
                  transformOrigin: "left center",
                  minHeight: rankFS * 0.98,
                  zIndex: isTop ? 2 : 1,
                }}
              >
                {/* BEHIND plane: the oversized numeral, occluded by the label slab */}
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: -rankFS * 0.14,
                    fontFamily: MG_FONTS.anton,
                    fontSize: rankFS,
                    fontWeight: 400,
                    lineHeight: 0.9,
                    letterSpacing: "-0.02em",
                    color: rankColor,
                    fontVariantNumeric: "tabular-nums",
                    scale: String(rankPop.toFixed(4)),
                    rotate: `${(i % 2 === 0 ? 1 : -1) * 2.4}deg`,
                    transformOrigin: "left bottom",
                    textShadow: rankShadow,
                    zIndex: 1,
                  }}
                >
                  {item.rank ?? String(i + 1)}
                </div>

                {/* FRONT plane: label slab overlapping the numeral's right half */}
                <div
                  style={{
                    position: "relative",
                    marginLeft: rankFS * 0.52,
                    zIndex: 2,
                    display: "flex",
                    flexDirection: "column",
                    paddingTop: 10,
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline" }}>
                    <div
                      style={{
                        flexGrow: 1,
                        fontFamily: MG_FONTS.inter,
                        fontSize: 52,
                        fontWeight: 800,
                        color: labelColor,
                        letterSpacing: "-0.01em",
                        lineHeight: 1.05,
                        textShadow,
                      }}
                    >
                      {item.label}
                    </div>

                    {item.value ? (
                      <div
                        style={{
                          flexShrink: 0,
                          marginLeft: 20,
                          padding: "8px 18px",
                          borderRadius: 12,
                          rotate: `${(i % 2 === 0 ? 1 : -1) * 3}deg`,
                          background: isTop ? accentColor : "rgba(255,255,255,0.12)",
                          color: isTop ? "#15151E" : valueColor,
                          fontFamily: MG_FONTS.inter,
                          fontSize: 38,
                          fontWeight: 800,
                          letterSpacing: "0.01em",
                          lineHeight: 1,
                          fontVariantNumeric: "tabular-nums",
                          boxShadow: "0 6px 18px rgba(0,0,0,0.35)",
                          textShadow: isTop ? undefined : textShadow,
                        }}
                      >
                        {item.value}
                      </div>
                    ) : null}
                  </div>

                  <div
                    style={{
                      marginTop: 12,
                      height: isTop ? 3 : 2,
                      borderRadius: 2,
                      background: isTop
                        ? accentColor
                        : "rgba(255,255,255,0.26)",
                      scale: `${ruleScale.toFixed(3)} 1`,
                      transformOrigin: "left center",
                      boxShadow: isTop ? `0 0 ${(10 * bloom).toFixed(1)}px ${accentColor}` : undefined,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
