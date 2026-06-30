import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import type { SpringConfig } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import { ICONS } from "./icons";
import type { IconLabelFontKey, IconLabelProps } from "./types";


const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);
const easeOutBack = (t: number): number => {
  const c1 = 1.70158;
  const c3 = c1 + 1;
  return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2);
};
const easeInQuad = (t: number): number => t * t;

const ICON_SPRING: SpringConfig = {
  mass: 0.6,
  damping: 11,
  stiffness: 190,
  overshootClamping: false,
};
const ICON_SPRING_DURATION = 24;

const DEFAULT_TEXT_SHADOW =
  "0 2px 8px rgba(0,0,0,0.85), 0 12px 40px rgba(0,0,0,0.6)";
const DEFAULT_ICON_FILTER = "drop-shadow(0 2px 6px rgba(0,0,0,0.55))";

const FONT_FAMILY: Record<IconLabelFontKey, string> = {
  inter: MG_FONTS.inter,
  anton: MG_FONTS.anton,
  oswald: MG_FONTS.oswald,
};
const FONT_WEIGHT: Record<IconLabelFontKey, number> = {
  inter: 800,
  anton: 400,
  oswald: 700,
};

export const IconLabel: React.FC<IconLabelProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  icon,
  label,
  layout = "row",
  iconColor = "#FFFFFF",
  labelColor = "#FFFFFF",
  fontKey = "inter",
  fontSize = 56,
  iconSize = 96,
  strokeWidth = 2,
  showPill = false,
  pillColor = "rgba(18,18,22,0.5)",
  showRing = true,
  ringColor,
  textShadow = DEFAULT_TEXT_SHADOW,
  idle = false,
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
    { defaultEnterFrames: 26, defaultExitFrames: 14 },
  );

  if (!visible) return null;

  const Icon = ICONS[icon] ?? ICONS.check;
  const hasLabel = Boolean(label && label.length > 0);
  const isRow = layout === "row";

  // Pill entrance
  const pillScale = interpolate(localFrame, [0, 12], [0.7, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack,
  });
  const pillOpacity = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Icon spring pop
  const iconSpring = spring({
    fps,
    frame: localFrame,
    config: ICON_SPRING,
    durationInFrames: ICON_SPRING_DURATION,
  });
  const idleBreath =
    localFrame > 24
      ? 1 + (idle ? 0.022 : 0.013) * Math.sin((localFrame - 24) * 0.16)
      : 1;
  const iconScale = iconSpring * idleBreath;
  const iconRotate = interpolate(localFrame, [0, 18], [-10, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack,
  });
  const iconOpacity = interpolate(localFrame, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Ping ring
  const ringScale = interpolate(localFrame, [8, 30], [0.5, 1.9], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ringOpacity = interpolate(localFrame, [8, 11, 30], [0, 0.5, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ringScale2 = interpolate(localFrame, [12, 36], [0.5, 2.2], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const ringOpacity2 = interpolate(localFrame, [12, 16, 36], [0, 0.32, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Accent glow halo behind the icon — pops on land, then breathes.
  const haloIn = interpolate(localFrame, [2, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const haloScale =
    (0.6 + 0.55 * haloIn) * (1 + 0.05 * Math.sin(localFrame * 0.08));
  const haloOpacity = haloIn * 0.5 * (0.82 + 0.18 * Math.sin(localFrame * 0.08));

  // Label reveal (wipe out of the icon)
  const labelClip = interpolate(localFrame, [10, 26], [100, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelTrans = interpolate(localFrame, [10, 26], [isRow ? -18 : 14, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutBack,
  });
  const labelOpacity = interpolate(localFrame, [10, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Exit collapse + fade
  const exitEase = easeInQuad(exitProgress);
  const exitScale = 1 - 0.16 * exitEase;
  const exitTY = -8 * exitEase;
  const exitOpacity = interpolate(exitProgress, [0, 0.85], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const ringDiameter = iconSize * 0.92;
  const pillPadding = !hasLabel
    ? "24px"
    : isRow
      ? "22px 34px"
      : "26px 36px";
  const pillRadius = !hasLabel ? "50%" : isRow ? 999 : 44;

  const chromeStyle: React.CSSProperties = showPill
    ? {
        display: "flex",
        flexDirection: isRow ? "row" : "column",
        alignItems: "center",
        gap: hasLabel ? (isRow ? 20 : 14) : 0,
        padding: pillPadding,
        borderRadius: pillRadius,
        background: pillColor,
        backdropFilter: "blur(20px) saturate(150%)",
        WebkitBackdropFilter: "blur(20px) saturate(150%)",
        border: "1px solid rgba(255,255,255,0.12)",
        boxShadow: "0 10px 34px rgba(0,0,0,0.4)",
        transform: `scale(${pillScale})`,
        transformOrigin: "center",
        opacity: pillOpacity,
      }
    : {
        display: "flex",
        flexDirection: isRow ? "row" : "column",
        alignItems: "center",
        gap: hasLabel ? (isRow ? 20 : 14) : 0,
      };

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
        <div
          style={{
            transform: `translateY(${exitTY}px) scale(${exitScale})`,
            transformOrigin: "center",
            opacity: exitOpacity,
          }}
        >
          <div style={chromeStyle}>
            {/* Icon */}
            <div
              style={{
                position: "relative",
                color: iconColor,
                filter: DEFAULT_ICON_FILTER,
                transform: `scale(${iconScale}) rotate(${iconRotate}deg)`,
                transformOrigin: "center",
                opacity: iconOpacity,
                lineHeight: 0,
              }}
            >
              {/* Accent glow halo */}
              <div
                style={{
                  position: "absolute",
                  top: "50%",
                  left: "50%",
                  width: iconSize * 1.7,
                  height: iconSize * 1.7,
                  borderRadius: "50%",
                  background: `radial-gradient(circle, ${ringColor ?? iconColor} 0%, transparent 62%)`,
                  transform: `translate(-50%, -50%) scale(${haloScale.toFixed(3)})`,
                  opacity: haloOpacity,
                  zIndex: 0,
                  pointerEvents: "none",
                }}
              />
              {showRing ? (
                <>
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      width: ringDiameter,
                      height: ringDiameter,
                      borderRadius: "50%",
                      border: `3px solid ${ringColor ?? iconColor}`,
                      transform: `translate(-50%, -50%) scale(${ringScale})`,
                      opacity: ringOpacity,
                      zIndex: 0,
                    }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      width: ringDiameter,
                      height: ringDiameter,
                      borderRadius: "50%",
                      border: `2px solid ${ringColor ?? iconColor}`,
                      transform: `translate(-50%, -50%) scale(${ringScale2})`,
                      opacity: ringOpacity2,
                      zIndex: 0,
                    }}
                  />
                </>
              ) : null}
              <div style={{ position: "relative", zIndex: 1, lineHeight: 0 }}>
                <Icon size={iconSize} strokeWidth={strokeWidth} />
              </div>
            </div>

            {/* Label */}
            {hasLabel ? (
              <div
                style={{
                  clipPath: isRow
                    ? `inset(0 ${labelClip}% 0 0)`
                    : `inset(${labelClip}% 0 0 0)`,
                  transform: isRow
                    ? `translateX(${labelTrans}px)`
                    : `translateY(${labelTrans}px)`,
                  opacity: labelOpacity,
                }}
              >
                <span
                  style={{
                    fontFamily: FONT_FAMILY[fontKey],
                    fontWeight: FONT_WEIGHT[fontKey],
                    fontSize,
                    color: labelColor,
                    textTransform: "uppercase",
                    letterSpacing: "0.02em",
                    lineHeight: 1,
                    whiteSpace: "nowrap",
                    textShadow,
                    display: "block",
                    textAlign: "center",
                  }}
                >
                  {label}
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
