import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { ProgressBarProps } from "./types";


const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

const DEFAULT_TEXT_SHADOW_LARGE =
  "0 4px 20px rgba(0,0,0,0.65), 0 2px 4px rgba(0,0,0,0.5)";
const DEFAULT_TEXT_SHADOW_SMALL =
  "0 2px 10px rgba(0,0,0,0.75), 0 1px 2px rgba(0,0,0,0.55)";

const FILL_START = 8;
const FILL_END = 34;
const PULSE_END = 40;

export const ProgressBar: React.FC<ProgressBarProps> = (props) => {
  const {
    startMs,
    durationMs,
    enterFrames,
    exitFrames,
    label,
    width = 860,
    trackHeight = 18,
    fillColor = "#FFFFFF",
    accentColor = "#D4A12A",
    trackColor = "rgba(255,255,255,0.14)",
    milestones = [],
    formatValue,
    textShadowLarge = DEFAULT_TEXT_SHADOW_LARGE,
    textShadowSmall = DEFAULT_TEXT_SHADOW_SMALL,
    anchor,
    offsetX,
    offsetY,
    scale,
  } = props;
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    undefined,
    "ProgressBar",
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 40, defaultExitFrames: 12 },
  );

  if (!visible) return null;

  const isValueMode = "value" in props && props.value !== undefined;
  const targetPercent = isValueMode
    ? Math.max(0, Math.min(1, props.value / props.total))
    : Math.max(0, Math.min(1, (props.percentage ?? 0) / 100));

  const trackSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 8,
  });
  const trackScaleX = trackSpring;
  const eyebrowFadeIn = interpolate(localFrame, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const heroFadeIn = interpolate(localFrame, [6, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const fillRaw = interpolate(localFrame, [FILL_START, FILL_END], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fillEased = easeOutCubic(fillRaw);
  const currentPercent = targetPercent * fillEased;

  const currentValue = isValueMode
    ? props.value * fillEased
    : (props.percentage ?? 0) * fillEased;

  const heroText = isValueMode
    ? formatValue
      ? formatValue(currentValue)
      : Math.round(currentValue).toLocaleString()
    : `${Math.round(currentValue)}%`;

  const totalText = isValueMode
    ? formatValue
      ? formatValue(props.total)
      : Math.round(props.total).toLocaleString()
    : null;

  const pulsePhase = interpolate(localFrame, [FILL_END, PULSE_END], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const pulseTri = pulsePhase < 0.5 ? pulsePhase * 2 : (1 - pulsePhase) * 2;
  const fillScaleY = 1 + pulseTri * 0.08;

  const exitOpacity = 1 - exitProgress;
  const exitDriftY = exitProgress * -8;

  const fillWidth = width * currentPercent;
  const radius = trackHeight / 2;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          opacity: exitOpacity,
          transform: `translateY(${exitDriftY}px)`,
          width,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}
      >
        {label ? (
          <div
            style={{
              fontFamily: MG_FONTS.inter,
              fontSize: 24,
              fontWeight: 600,
              color: accentColor,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              lineHeight: 1,
              opacity: eyebrowFadeIn,
              textShadow: textShadowSmall,
              whiteSpace: "nowrap",
              marginBottom: 22,
            }}
          >
            {label}
          </div>
        ) : null}

        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "baseline",
            justifyContent: "center",
            opacity: heroFadeIn,
            color: "#FFFFFF",
            lineHeight: 0.9,
            fontVariantNumeric: "tabular-nums",
            textShadow: textShadowLarge,
            whiteSpace: "nowrap",
          }}
        >
          <span
            style={{
              fontFamily: MG_FONTS.anton,
              fontSize: 140,
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 0.9,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {heroText}
          </span>
          {totalText ? (
            <span
              style={{
                fontFamily: MG_FONTS.anton,
                fontSize: 60,
                fontWeight: 400,
                letterSpacing: "-0.01em",
                color: "rgba(255,255,255,0.55)",
                marginLeft: 18,
                lineHeight: 0.9,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              / {totalText}
            </span>
          ) : null}
        </div>

        <div
          style={{
            width: 48,
            height: 2,
            backgroundColor: accentColor,
            marginTop: 22,
            marginBottom: 24,
            opacity: heroFadeIn,
            boxShadow: "0 2px 6px rgba(0,0,0,0.5)",
          }}
        />

        <div
          style={{
            position: "relative",
            width: "100%",
            height: trackHeight,
            transform: `scaleX(${trackScaleX})`,
            transformOrigin: "left center",
            opacity: eyebrowFadeIn,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              backgroundColor: trackColor,
              borderRadius: radius,
              boxShadow: "inset 0 1px 2px rgba(0,0,0,0.35)",
            }}
          />

          <div
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              height: trackHeight,
              width: fillWidth,
              backgroundColor: fillColor,
              borderRadius: radius,
              transform: `scaleY(${fillScaleY})`,
              transformOrigin: "center",
              boxShadow: `0 4px 12px ${withAlpha(fillColor, 0.35)}`,
            }}
          />

          {milestones.map((m, i) => {
            const x = width * m.at;
            const reached = currentPercent >= m.at;
            return (
              <React.Fragment key={i}>
                <div
                  style={{
                    position: "absolute",
                    left: x - 1,
                    top: -4,
                    width: 2,
                    height: trackHeight + 8,
                    backgroundColor: reached
                      ? "#FFFFFF"
                      : "rgba(255,255,255,0.3)",
                    borderRadius: 1,
                  }}
                />
                {m.label ? (
                  <div
                    style={{
                      position: "absolute",
                      left: x,
                      bottom: -38,
                      transform: "translateX(-50%)",
                      fontFamily: MG_FONTS.inter,
                      fontSize: 18,
                      fontWeight: 600,
                      color: reached
                        ? "#FFFFFF"
                        : "rgba(255,255,255,0.5)",
                      letterSpacing: "0.2em",
                      textTransform: "uppercase",
                      whiteSpace: "nowrap",
                      textShadow: textShadowSmall,
                    }}
                  >
                    {m.label}
                  </div>
                ) : null}
              </React.Fragment>
            );
          })}
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};


function withAlpha(color: string, alpha: number): string {
  if (color.startsWith("#")) {
    const h = color.replace("#", "");
    const full =
      h.length === 3
        ? h
            .split("")
            .map((c) => c + c)
            .join("")
        : h;
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }
  if (color.startsWith("rgb(")) {
    return color.replace("rgb(", "rgba(").replace(")", `, ${alpha})`);
  }
  return color;
}
