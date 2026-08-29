import React from "react";
import { AbsoluteFill, interpolate, useVideoConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { mgSchedule } from "../shared/schedule";
import type { StepDividerProps } from "./types";
import { asText } from "../../shared/asText";

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeInOutCubic = (t: number): number =>
  t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

const TEXT_SHADOW =
  "0 2px 12px rgba(0,0,0,0.62), 0 14px 48px rgba(0,0,0,0.45)";
// 680 = the position resolver's symmetric safe box (1080 − 2×200); the old 900
// exceeded it, so wide lines ran under the TikTok action rail (pass #9).
const CONTENT_MAX = 680;
const SEG_W = 52;
const SEG_H = 11;
const SEG_GAP = 12;

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
  totalSteps,
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
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress, exitStartFrame } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 48, defaultExitFrames: 22 },
  );

  if (!visible) return null;

  const lf = localFrame;
  // Coupled-defaults audit (2026-08-26): the defaulted total of 5 clamped an
  // overridden step to a wrong "STEP 05 / 05" from beat 6 on. An unspecified
  // totalSteps now grows with the step; an explicit totalSteps keeps today's
  // clamp (and the plain default stays 5).
  const steps = Math.max(1, totalSteps ?? Math.max(5, step));
  const cur = Math.max(1, Math.min(step, steps));
  const titleText = asText(title);
  const lines = titleText.split("\n");

  // Font census (2026-08-26): title + kicker are user/model text — routed
  // stacks (+ emoji tail); the padded step digits stay chrome (bare Inter).
  const titleMetrics = mgTextMetrics(titleText);
  const titleFont = mgTextFont(titleText, fontKey);
  const kickerFont = mgTextFont(kicker, "inter");
  const kickerUppercaseSafe = mgTextMetrics(kicker).uppercaseSafe;

  // Width-driven autofit (pass #9, takeover law): the fixed 122px title sat at
  // ~32% of the frame — a divider that lands alone owns its axis. The title
  // now fills the resolver's 680px safe box; the advance estimate (0.52em/char
  // for the condensed faces, measured ~0.47) over-estimates so text can never
  // crop.
  let maxChars = 1;
  for (const l of lines) maxChars = Math.max(maxChars, [...l].length);
  // Latin keeps the measured constants; non-latin uses the census's
  // render-proven advanceEm (deliberate over-estimate — never crops).
  const advance =
    titleMetrics.script === "latin"
      ? fontKey === "inter"
        ? 0.62
        : 0.52
      : titleMetrics.advanceEm;
  const fitTitleSize = Math.round(
    Math.max(56, Math.min(CONTENT_MAX / (maxChars * advance), 240)),
  );

  // Duration-aware fps-relative schedule (mgSchedule, the DropCard recipe):
  // the raw-frame choreography scaled with totalSteps and could still be
  // mid-reveal at exit onset for short live windows.
  const authoredKStart = steps * 3 + 6;
  const K = mgSchedule({
    fps,
    window: exitStartFrame,
    authoredEnd: authoredKStart + 10 + 7 * (lines.length - 1) + 18,
  });

  const exitFade = interpolate(exitProgress, [0, 0.7], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const blockY = interpolate(exitProgress, [0, 1], [0, -12], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Kicker timing follows the progress segments.
  const kickerO =
    interpolate(lf, [K(authoredKStart), K(authoredKStart + 12)], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }) * exitFade;
  const kickerY = interpolate(lf, [K(authoredKStart), K(authoredKStart + 14)], [12, 0], {
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
                const sx = interpolate(lf, [K(segStart), K(segStart + 10)], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                  easing: easeOutCubic,
                });
                const so = interpolate(lf, [K(segStart), K(segStart + 6)], [0, 1], {
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
                      [K(steps * 3 + 4), K(steps * 3 + 12), K(steps * 3 + 24)],
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
              textTransform: kickerUppercaseSafe ? "uppercase" : "none",
              marginBottom: 26,
              opacity: kickerO,
              transform: `translateY(${kickerY.toFixed(2)}px)`,
              textShadow: TEXT_SHADOW,
              whiteSpace: "nowrap",
            }}
          >
            <span style={{ color: kickerColor, fontFamily: kickerFont }}>
              {kicker}{" "}
            </span>
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
            const tStart = authoredKStart + 10 + li * 7;
            const revealP = interpolate(lf, [K(tStart), K(tStart + 18)], [0, 1], {
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
              interpolate(lf, [K(tStart), K(tStart + 9)], [0, 1], {
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
                  // Keyed off REVEAL COMPLETION, not the phase label (pass #9):
                  // the smooth-path enter window (48f authored → 1600ms) kept
                  // the mask on ~50 frames after the choreography settled —
                  // the heavy text-shadow clipped into visible rectangular
                  // plates around the settled title (render-caught).
                  overflow: revealP >= 1 ? "visible" : "hidden",
                  maxWidth: CONTENT_MAX,
                }}
              >
                <div
                  style={{
                    fontFamily: titleFont,
                    fontSize: fitTitleSize,
                    fontWeight: 400,
                    color: titleColor,
                    letterSpacing: "-0.01em",
                    lineHeight: Math.max(1.02, titleMetrics.lineHeight),
                    textTransform:
                      uppercase && titleMetrics.uppercaseSafe
                        ? "uppercase"
                        : "none",
                    textAlign: "center",
                    whiteSpace: "nowrap",
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
