import React from "react";
import { AbsoluteFill, interpolate } from "remotion";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { StatCardProps } from "./types";


const NUMBER_SIZE = 240;
const AFFIX_SIZE = 132;
const AFFIX_GAP = 10;
const LABEL_SIZE = 34;
const RULE_WIDTH = 48;
const RULE_HEIGHT = 2;
const NUMBER_TO_RULE = 22;
const RULE_TO_LABEL = 18;

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

const DEFAULT_TEXT_SHADOW =
  "0 2px 8px rgba(0,0,0,0.85), 0 12px 40px rgba(0,0,0,0.6)";

export const StatCard: React.FC<StatCardProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  value,
  fromValue = 0,
  prefix,
  suffix,
  decimals,
  label,
  numberColor = "#FFFFFF",
  labelColor = "#FFFFFF",
  accentColor = "#C8551F",
  textShadow = DEFAULT_TEXT_SHADOW,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const { containerStyle, wrapperStyle } = resolveMGPosition({
    anchor,
    offsetX,
    offsetY,
    scale,
  });
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 32, defaultExitFrames: 12 },
  );

  if (!visible) return null;

  const numberEnterScale = interpolate(localFrame, [0, 8], [0.92, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: easeOutCubic,
  });
  const numberFadeIn = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const countProgress = interpolate(localFrame, [4, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const easedCount = easeOutCubic(countProgress);
  const currentValue = fromValue + (value - fromValue) * easedCount;
  const display =
    decimals !== undefined
      ? currentValue.toFixed(decimals)
      : Math.round(currentValue).toLocaleString();

  const pulseScale = interpolate(
    localFrame,
    [24, 27, 30],
    [1, 1.08, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const ruleScaleX = interpolate(localFrame, [24, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const labelFadeIn = interpolate(localFrame, [26, 32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelY = interpolate(localFrame, [26, 32], [8, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const exitDriftY = exitProgress * -10;
  const exitOpacity = 1 - exitProgress;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          transform: `translateY(${exitDriftY}px)`,
          opacity: exitOpacity,
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "baseline",
            justifyContent: "center",
            transform: `scale(${numberEnterScale * pulseScale})`,
            transformOrigin: "center",
            opacity: numberFadeIn,
            fontVariantNumeric: "tabular-nums",
            color: numberColor,
            lineHeight: 1,
            textShadow,
          }}
        >
          {prefix ? (
            <span
              style={{
                fontFamily: MG_FONTS.anton,
                fontSize: AFFIX_SIZE,
                fontWeight: 400,
                letterSpacing: "-0.02em",
                lineHeight: 1,
                opacity: 0.9,
                marginRight: AFFIX_GAP,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {prefix}
            </span>
          ) : null}

          <span
            style={{
              fontFamily: MG_FONTS.anton,
              fontSize: NUMBER_SIZE,
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 1,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {display}
          </span>

          {suffix ? (
            <span
              style={{
                fontFamily: MG_FONTS.anton,
                fontSize: AFFIX_SIZE,
                fontWeight: 400,
                letterSpacing: "-0.02em",
                lineHeight: 1,
                opacity: 0.9,
                marginLeft: AFFIX_GAP,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {suffix}
            </span>
          ) : null}
        </div>

        <div
          style={{
            width: RULE_WIDTH,
            height: RULE_HEIGHT,
            backgroundColor: accentColor,
            marginTop: NUMBER_TO_RULE,
            marginBottom: RULE_TO_LABEL,
            transform: `scaleX(${ruleScaleX})`,
            transformOrigin: "center",
            boxShadow: "0 2px 6px rgba(0,0,0,0.5)",
          }}
        />

        <div
          style={{
            fontFamily: MG_FONTS.inter,
            fontSize: LABEL_SIZE,
            fontWeight: 600,
            color: labelColor,
            letterSpacing: "0.22em",
            textTransform: "uppercase",
            textAlign: "center",
            lineHeight: 1.2,
            opacity: labelFadeIn,
            transform: `translateY(${labelY}px)`,
            textShadow,
          }}
        >
          {label}
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
