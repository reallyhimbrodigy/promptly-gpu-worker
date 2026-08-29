import React from "react";
import { AbsoluteFill, interpolate, interpolateColors, useVideoConfig } from "remotion";
import { mgTextFont, mgTextMetrics } from "../shared/text-font";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { ReticleProps } from "./types";
import { useSmoothGraphics } from "../shared/smooth-graphics-flag";
import { cappedEntranceProgress } from "../shared/entrance-cap";


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
  "0 2px 10px rgba(0,0,0,0.7), 0 1px 2px rgba(0,0,0,0.55)";
const SPREAD0 = 130; // how far the brackets start outside the corners
const LOCK = 18; // frame the focus lands
const REC_COLOR = "#FF3B30"; // pulsing REC dot

type Corner = "tl" | "tr" | "bl" | "br";
const CORNERS: Corner[] = ["tl", "tr", "bl", "br"];

export const Reticle: React.FC<ReticleProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  label,
  regionWidth = 620,
  regionHeight = 720,
  bracketColor = "#FFFFFF",
  accentColor = "#36E27A",
  showScanline = true,
  showCrosshair = false,
  armLength = 64,
  thickness = 5,
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
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 16, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  // Focus pull: brackets sweep inward from SPREAD0 → 0 with a slight inward
  // overshoot (easeOutBack pushes focus past 1), then settle exactly on the corners.
  // ENTRANCE VELOCITY CAP: easeOutBack OVERSHOOTS, which is precisely a velocity
  // spike (measured peak_step 0.67 => ~1.5 effective positions, the worst in the
  // set). OFF => today's exact overshoot.
  const smoothEntrance = useSmoothGraphics();
  const focus = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: LOCK })
    : easeOutBack(clamp01(localFrame / LOCK));
  // Out = reverse focus-pull: brackets release back outward as the shot ends.
  const exitDefocus = easeOutCubic(exitProgress);
  const spread = (1 - focus) * SPREAD0 + exitDefocus * SPREAD0;
  // The bracket OPACITY ramp dominates presence; capping only the focus pull
  // left it at 0.71. Cap the appearing channel too.
  const bracketsOpacity = smoothEntrance
    ? cappedEntranceProgress({ localFrame, fps, authoredFrames: 10 })
    : interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Lock double-pulse on the whole region.
  const lockPulse = interpolate(
    localFrame,
    [LOCK - 1, LOCK + 1, LOCK + 3, LOCK + 5, LOCK + 7],
    [1, 0.96, 1, 0.985, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  // Brackets flush white → accent as the lock lands, then release back to
  // white on the way out (focus dropping).
  const lockT = clamp01((localFrame - LOCK) / 6);
  const lockedColor = interpolateColors(
    lockT,
    [0, 1],
    [bracketColor, accentColor],
  );
  const liveColor = interpolateColors(
    clamp01(exitProgress * 1.3),
    [0, 1],
    [lockedColor, bracketColor],
  );
  const lockGlow = interpolate(
    localFrame,
    [LOCK, LOCK + 3, LOCK + 14],
    [0, 14, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // User/model text routes by script + emoji tail (font census 2026-08-26).
  const tagFont = mgTextFont(label ?? "", "inter");
  const tagMetrics = mgTextMetrics(label ?? "");

  // Tag spring-in at the corner (eased gently so it doesn't snap-pop).
  const tagScale = easeOutBack(clamp01((localFrame - LOCK) / 28));
  const tagOpacity = interpolate(localFrame, [LOCK, LOCK + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  // Smooth pulsing REC dot.
  const recPulse = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(localFrame * 0.11));

  // Scanline sweeps down, then rises back up once before it vanishes.
  const scanY = interpolate(localFrame, [10, 48, 86], [0, regionHeight, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeInOutCubic,
  });
  const scanOpacity = showScanline
    ? interpolate(localFrame, [10, 16, 78, 86], [0, 0.55, 0.55, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const crossOpacity = showCrosshair
    ? interpolate(localFrame, [6, 14], [0, 0.8], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  // Bloom out slightly as focus releases, fading a touch ahead of the spread.
  const exitOpacity = 1 - clamp01(exitProgress * 1.15);
  const exitScale = 1 + 0.05 * exitDefocus;

  // Coupled-defaults audit (2026-08-26): armLength 64 was authored for the
  // 620x720 default region; a tight region override (< ~128px) crossed the
  // opposing corner arms into solid bars. Clamp the arm to the region's
  // half-extents — inert at the defaults (min(64, 305, 355) = 64).
  const arm = Math.max(
    0,
    Math.min(
      armLength,
      regionWidth / 2 - thickness,
      regionHeight / 2 - thickness,
    ),
  );

  const cornerStyle = (c: Corner): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: "absolute",
      width: arm,
      height: arm,
      boxSizing: "border-box",
    };
    const dx = c === "tl" || c === "bl" ? -spread : spread;
    const dy = c === "tl" || c === "tr" ? -spread : spread;
    const border = `${thickness}px solid ${liveColor}`;
    const edges: React.CSSProperties =
      c === "tl"
        ? { left: 0, top: 0, borderTop: border, borderLeft: border }
        : c === "tr"
          ? { right: 0, top: 0, borderTop: border, borderRight: border }
          : c === "bl"
            ? { left: 0, bottom: 0, borderBottom: border, borderLeft: border }
            : { right: 0, bottom: 0, borderBottom: border, borderRight: border };
    return {
      ...base,
      ...edges,
      transform: `translate(${dx.toFixed(2)}px, ${dy.toFixed(2)}px)`,
      filter: lockGlow > 0.1 ? `drop-shadow(0 0 ${lockGlow.toFixed(1)}px ${accentColor})` : undefined,
    };
  };

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            position: "relative",
            width: regionWidth,
            height: regionHeight,
            opacity: exitOpacity,
            transform: `scale(${(lockPulse * exitScale).toFixed(4)})`,
            transformOrigin: "center",
          }}
        >
          {/* §4-for-footage (2026-08-25): the WINDOW plane. A viewfinder is
              axis-aligned by nature — tilt/overlap read as error here. The
              depth device for this family is selection: everything OUTSIDE
              the region dims as the lock lands (box-shadow spill — one node,
              no four-rect math), so the HUD occludes the footage around the
              subject and the region reads as a window, not four floating
              corners. Releases with the exit defocus. */}
          <div
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: 10,
              boxShadow: `0 0 0 9999px rgba(0,0,0,${(0.26 * lockT * (1 - exitDefocus)).toFixed(3)})`,
              pointerEvents: "none",
            }}
          />

          {/* Corner brackets */}
          <div style={{ position: "absolute", inset: 0, opacity: bracketsOpacity }}>
            {CORNERS.map((c) => (
              <div key={c} style={cornerStyle(c)} />
            ))}
            {/* Restrained HUD furniture: midpoint edge ticks — the marks a
                real viewfinder carries. Corpus register is fragments, so the
                furniture stays minimal: four ticks, no readouts. */}
            {[
              { left: "50%", top: -1, width: 2, height: 14, translate: "-50% 0" },
              { left: "50%", bottom: -1, width: 2, height: 14, translate: "-50% 0" },
              { left: -1, top: "50%", width: 14, height: 2, translate: "0 -50%" },
              { right: -1, top: "50%", width: 14, height: 2, translate: "0 -50%" },
            ].map((t, i) => (
              <div
                key={`tick-${i}`}
                style={{
                  position: "absolute",
                  ...t,
                  backgroundColor: liveColor,
                  opacity: 0.75,
                }}
              />
            ))}
          </div>

          {/* Scanline */}
          {scanOpacity > 0 ? (
            <div
              style={{
                position: "absolute",
                left: 0,
                top: scanY,
                width: "100%",
                height: 2,
                background: `linear-gradient(90deg, ${accentColor}00, ${accentColor}, ${accentColor}00)`,
                boxShadow: `0 0 12px ${accentColor}`,
                opacity: scanOpacity,
                pointerEvents: "none",
              }}
            />
          ) : null}

          {/* Center crosshair */}
          {crossOpacity > 0 ? (
            <div
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                transform: "translate(-50%, -50%)",
                opacity: crossOpacity,
                pointerEvents: "none",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: -16,
                  top: -1,
                  width: 32,
                  height: 2,
                  backgroundColor: liveColor,
                }}
              />
              <div
                style={{
                  position: "absolute",
                  left: -1,
                  top: -16,
                  width: 2,
                  height: 32,
                  backgroundColor: liveColor,
                }}
              />
            </div>
          ) : null}

          {/* REC tag at the top-left corner */}
          {label ? (
            <div
              style={{
                position: "absolute",
                left: -thickness / 2,
                top: 0,
                transform: `translateY(calc(-100% - 14px)) scale(${tagScale.toFixed(4)})`,
                transformOrigin: "bottom left",
                opacity: tagOpacity,
                display: "inline-flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 22px",
                borderRadius: 14,
                background:
                  "linear-gradient(180deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0) 50%), rgba(16,18,24,0.42)",
                backdropFilter: "blur(18px) saturate(150%)",
                WebkitBackdropFilter: "blur(18px) saturate(150%)",
                border: "1.5px solid rgba(255,255,255,0.18)",
                boxShadow: "0 12px 30px rgba(0,0,0,0.42)",
                whiteSpace: "nowrap",
              }}
            >
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  backgroundColor: REC_COLOR,
                  boxShadow: `0 0 12px ${REC_COLOR}`,
                  opacity: recPulse,
                }}
              />
              <span
                style={{
                  fontFamily: tagFont,
                  fontSize: 30,
                  fontWeight: 700,
                  color: "#FFFFFF",
                  letterSpacing: "0.12em",
                  textTransform: tagMetrics.uppercaseSafe
                    ? "uppercase"
                    : "none",
                  lineHeight: Math.max(1, tagMetrics.lineHeight),
                  textShadow,
                }}
              >
                {label}
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </AbsoluteFill>
  );
};
