import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { StepDividerFontKey, StepDividerProps } from "./types";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

const TEXT_SHADOW =
  "0 2px 12px rgba(0,0,0,0.62), 0 14px 48px rgba(0,0,0,0.45)";
const CONTENT_MAX = 900;
const SEG_W = 52;
const SEG_H = 11;
const SEG_GAP = 12;

const FONT_FAMILY: Record<StepDividerFontKey, string> = {
  anton: MG_FONTS.anton,
  oswald: MG_FONTS.oswald,
  inter: MG_FONTS.inter,
};

const withAlpha = (hex: string, a: number): string => {
  const x = hex.replace("#", "");
  const f = x.length === 3 ? x.split("").map((c) => c + c).join("") : x;
  const r = parseInt(f.slice(0, 2), 16);
  const g = parseInt(f.slice(2, 4), 16);
  const b = parseInt(f.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
};

export const StepDivider: React.FC<StepDividerProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  title,
  step = 1,
  totalSteps = 5,
  kicker = "STEP",
  showProgress = true,
  showCount = true,
  fontKey = "anton",
  titleFontSize = 122,
  uppercase = true,
  titleColor = "#FFFFFF",
  kickerColor = "#FFFFFF",
  accentColor = "#4F9DF7",
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "center" },
  );
  const { visible, localFrame, exitProgress, phase } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 48, defaultExitFrames: 22 },
  );

  if (!visible) return null;

  const lf = localFrame;
  const steps = Math.max(1, totalSteps);
  const cur = Math.max(1, Math.min(step, steps));
  const holding = phase === "holding";
  const lines = title.split("\n");

  const exitFade = interpolate(exitProgress, [0, 0.7], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blockY = interpolate(exitProgress, [0, 1], [0, -12], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Kicker timing follows the progress segments.
  const kStart = steps * 3 + 6;
  const kickerO =
    interpolate(lf, [kStart, kStart + 12], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }) * exitFade;
  const kickerY = interpolate(lf, [kStart, kStart + 14], [12, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            width: CONTENT_MAX,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            transform: `translateY(${blockY.toFixed(2)}px)`,
          }}
        >
          {/* Segmented step progress */}
          {showProgress ? (
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                gap: SEG_GAP,
                marginBottom: 40,
              }}
            >
              {Array.from({ length: steps }).map((_, i) => {
                const segStart = i * 3;
                const sx = interpolate(lf, [segStart, segStart + 10], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: easeOutCubic,
                });
                const so = interpolate(lf, [segStart, segStart + 6], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
                const isCur = i === cur - 1;
                const isDone = i < cur - 1;
                const color = isCur
                  ? accentColor
                  : isDone
                    ? withAlpha(accentColor, 0.5)
                    : "rgba(255,255,255,0.16)";
                const glow = isCur
                  ? interpolate(
                      lf,
                      [steps * 3 + 4, steps * 3 + 12, steps * 3 + 24],
                      [0, 1, 0.45],
                      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
                    )
                  : 0;
                return (
                  <div
                    key={i}
                    style={{
                      width: SEG_W,
                      height: SEG_H,
                      borderRadius: SEG_H / 2,
                      background: color,
                      opacity: so * exitFade,
                      transform: `scaleX(${sx.toFixed(3)})`,
                      transformOrigin: "left center",
                      boxShadow: isCur
                        ? `0 0 ${(14 * glow).toFixed(1)}px ${accentColor}`
                        : undefined,
                    }}
                  />
                );
              })}
            </div>
          ) : null}

          {/* Kicker — "STEP 02 / 05" */}
          <div
            style={{
              fontFamily: MG_FONTS.inter,
              fontSize: 32,
              fontWeight: 700,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              marginBottom: 26,
              opacity: kickerO,
              transform: `translateY(${kickerY.toFixed(2)}px)`,
              textShadow: TEXT_SHADOW,
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ color: kickerColor }}>{kicker} </span>
            <span style={{ color: accentColor }}>
              {String(cur).padStart(2, "0")}
            </span>
            {showCount ? (
              <span style={{ color: "rgba(255,255,255,0.5)" }}>
                {" / "}
                {String(steps).padStart(2, "0")}
              </span>
            ) : null}
          </div>

          {/* Title (mask-reveal per line) */}
          {lines.map((line, li) => {
            const tStart = kStart + 10 + li * 7;
            const revealP = interpolate(lf, [tStart, tStart + 18], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeOutCubic,
            });
            const enterTY = (1 - revealP) * 100;
            const exitTYp = interpolate(exitProgress, [0, 0.7], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: easeInOutCubic,
            });
            const lineTY = enterTY - 100 * exitTYp;
            const lineO =
              interpolate(lf, [tStart, tStart + 9], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }) *
              interpolate(exitProgress, [0.4, 0.78], [1, 0], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
            return (
              <div
                key={li}
                style={{
                  overflow: holding ? "visible" : "hidden",
                  maxWidth: CONTENT_MAX,
                }}
              >
                <div
                  style={{
                    fontFamily: FONT_FAMILY[fontKey],
                    fontSize: titleFontSize,
                    fontWeight: 400,
                    color: titleColor,
                    letterSpacing: "-0.01em",
                    lineHeight: 1.02,
                    textTransform: uppercase ? "uppercase" : "none",
                    textAlign: "center",
                    opacity: lineO,
                    transform: `translateY(${lineTY.toFixed(2)}%)`,
                    textShadow: TEXT_SHADOW,
                  }}
                >
                  {line}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
