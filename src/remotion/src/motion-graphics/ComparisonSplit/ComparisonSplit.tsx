import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { Video } from "@remotion/media";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { useMGPhase } from "../shared/useMGPhase";
import type { ComparisonContent, ComparisonSplitProps } from "./types";


const LABEL_SIZE = 26;
const LABEL_EDGE_OFFSET = 72;
const LABEL_TEXT_SHADOW =
  "0 2px 10px rgba(0,0,0,0.85), 0 1px 3px rgba(0,0,0,0.7)";

const DIVIDER_THICKNESS = 3;

const STAT_COUNT_START = 18;
const STAT_COUNT_END = 38;
const STAT_PULSE_KEYFRAMES = [38, 41, 44] as const;

const easeOutCubic = (t: number): number => 1 - Math.pow(1 - t, 3);

interface Palette {
  gradient: string;
  fallback: string;
  textColor: string;
  subtleColor: string;
}

const THEMES: Record<"dark" | "light", Palette> = {
  dark: {
    gradient:
      "linear-gradient(135deg, #0A0A0A 0%, #141416 55%, #1C1C1F 100%)",
    fallback: "#0F0F10",
    textColor: "#F2E9D6",
    subtleColor: "#B8B0A1",
  },
  light: {
    gradient:
      "linear-gradient(135deg, #F2E9D6 0%, #ECE2CB 55%, #E3D8BE 100%)",
    fallback: "#ECE2CB",
    textColor: "#16120E",
    subtleColor: "#5A4E3D",
  },
};


interface SideContentProps {
  content: ComparisonContent;
  palette: Palette;
  accentColor: string;
  localFrame: number;
  statFontSize: number;
}

const SideContent: React.FC<SideContentProps> = ({
  content,
  palette,
  accentColor,
  localFrame,
  statFontSize,
}) => {
  if (content.type === "image") {
    return (
      <Img
        src={content.src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />
    );
  }
  if (content.type === "video") {
    return (
      <Video
        src={content.src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          display: "block",
        }}
      />
    );
  }
  if (content.type === "color") {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: content.color,
        }}
      />
    );
  }
  if (content.type === "text") {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: palette.fallback,
          backgroundImage: palette.gradient,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 40px",
        }}
      >
        <div
          style={{
            fontFamily: MG_FONTS.dmSerifDisplay,
            fontSize: 108,
            fontWeight: 400,
            color: palette.textColor,
            textTransform: "uppercase",
            letterSpacing: "0.01em",
            lineHeight: 1,
            textAlign: "center",
          }}
        >
          {content.text}
        </div>
      </div>
    );
  }

  const from = content.fromValue ?? 0;
  const countProgress = interpolate(
    localFrame,
    [STAT_COUNT_START, STAT_COUNT_END],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const eased = easeOutCubic(countProgress);
  const currentValue = from + (content.value - from) * eased;
  const display =
    content.decimals !== undefined
      ? currentValue.toFixed(content.decimals)
      : Math.round(currentValue).toLocaleString();
  const pulseScale = interpolate(
    localFrame,
    STAT_PULSE_KEYFRAMES as unknown as number[],
    [1, 1.08, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: palette.fallback,
        backgroundImage: palette.gradient,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 24px",
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "baseline",
          justifyContent: "center",
          color: palette.textColor,
          lineHeight: 1,
          fontVariantNumeric: "tabular-nums",
          transform: `scale(${pulseScale})`,
          transformOrigin: "center",
        }}
      >
        {content.prefix ? (
          <span
            style={{
              fontFamily: MG_FONTS.anton,
              fontSize: statFontSize * 0.6,
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 1,
              opacity: 0.9,
              marginRight: 6,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {content.prefix}
          </span>
        ) : null}
        <span
          style={{
            fontFamily: MG_FONTS.anton,
            fontSize: statFontSize,
            fontWeight: 400,
            letterSpacing: "-0.02em",
            lineHeight: 1,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {display}
        </span>
        {content.suffix ? (
          <span
            style={{
              fontFamily: MG_FONTS.anton,
              fontSize: statFontSize * 0.6,
              fontWeight: 400,
              letterSpacing: "-0.02em",
              lineHeight: 1,
              opacity: 0.9,
              marginLeft: 6,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {content.suffix}
          </span>
        ) : null}
      </div>
      <div
        style={{
          width: 36,
          height: 2,
          backgroundColor: accentColor,
          marginTop: 18,
          marginBottom: 14,
        }}
      />
      <div
        style={{
          fontFamily: MG_FONTS.inter,
          fontSize: 22,
          fontWeight: 600,
          color: palette.subtleColor,
          letterSpacing: "0.22em",
          textTransform: "uppercase",
          textAlign: "center",
          lineHeight: 1.3,
        }}
      >
        {content.label}
      </div>
    </div>
  );
};

export const ComparisonSplit: React.FC<ComparisonSplitProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  orientation = "vertical",
  sides,
  labels,
  accentColor = "#C8551F",
  theme = "dark",
  dividerColor,
  statFontSize = 148,
}) => {
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 44, defaultExitFrames: 16 },
  );

  if (!visible) return null;

  const palette = THEMES[theme];
  const resolvedDividerColor = dividerColor ?? accentColor;
  const isVertical = orientation === "vertical";

  const dividerEnterSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 8,
  });
  const dividerExitScale = interpolate(exitProgress, [0.5, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dividerScale =
    exitProgress > 0 ? dividerExitScale : dividerEnterSpring;

  const sideSpring = spring({
    fps,
    frame: localFrame - 6,
    config: SPRING_SNAPPY,
    durationInFrames: 12,
  });
  const sideEnterProgress = interpolate(sideSpring, [0, 1], [0, 1]);
  const sideFadeIn = interpolate(localFrame, [6, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const sideExitProgress = interpolate(exitProgress, [0.25, 0.875], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const leadingOffsetPct =
    (sideEnterProgress - 1) * 100 - sideExitProgress * 100;
  const trailingOffsetPct =
    (1 - sideEnterProgress) * 100 + sideExitProgress * 100;
  const sideOpacity =
    sideFadeIn *
    interpolate(exitProgress, [0.25, 0.875], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });

  const labelSpring = spring({
    fps,
    frame: localFrame - 16,
    config: SPRING_SNAPPY,
    durationInFrames: 8,
  });
  const labelEnterY = interpolate(labelSpring, [0, 1], [-30, 0]);
  const labelFadeIn = interpolate(localFrame, [16, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelExitY = interpolate(exitProgress, [0, 0.5], [0, -20], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelExitFade = interpolate(exitProgress, [0, 0.5], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelY = labelEnterY + labelExitY;
  const labelOpacity = labelFadeIn * labelExitFade;

  const leadingSideStyle: React.CSSProperties = isVertical
    ? { top: 0, left: 0, width: "50%", height: "100%" }
    : { top: 0, left: 0, width: "100%", height: "50%" };
  const trailingSideStyle: React.CSSProperties = isVertical
    ? { top: 0, right: 0, width: "50%", height: "100%" }
    : { bottom: 0, left: 0, width: "100%", height: "50%" };

  const leadingTransform = isVertical
    ? `translateX(${leadingOffsetPct}%)`
    : `translateY(${leadingOffsetPct}%)`;
  const trailingTransform = isVertical
    ? `translateX(${trailingOffsetPct}%)`
    : `translateY(${trailingOffsetPct}%)`;

  const dividerStyle: React.CSSProperties = isVertical
    ? {
        position: "absolute",
        top: 0,
        left: `calc(50% - ${DIVIDER_THICKNESS / 2}px)`,
        width: DIVIDER_THICKNESS,
        height: "100%",
        backgroundColor: resolvedDividerColor,
        transform: `scaleY(${dividerScale})`,
        transformOrigin: "center",
      }
    : {
        position: "absolute",
        left: 0,
        top: `calc(50% - ${DIVIDER_THICKNESS / 2}px)`,
        height: DIVIDER_THICKNESS,
        width: "100%",
        backgroundColor: resolvedDividerColor,
        transform: `scaleX(${dividerScale})`,
        transformOrigin: "center",
      };

  const leadingLabelWrapperStyle: React.CSSProperties = isVertical
    ? {
        position: "absolute",
        top: LABEL_EDGE_OFFSET,
        left: 0,
        width: "50%",
        display: "flex",
        justifyContent: "center",
      }
    : {
        position: "absolute",
        top: LABEL_EDGE_OFFSET,
        left: 0,
        width: "100%",
        display: "flex",
        justifyContent: "center",
      };
  const trailingLabelWrapperStyle: React.CSSProperties = isVertical
    ? {
        position: "absolute",
        top: LABEL_EDGE_OFFSET,
        right: 0,
        width: "50%",
        display: "flex",
        justifyContent: "center",
      }
    : {
        position: "absolute",
        bottom: LABEL_EDGE_OFFSET,
        left: 0,
        width: "100%",
        display: "flex",
        justifyContent: "center",
      };

  const labelStyle: React.CSSProperties = {
    fontFamily: MG_FONTS.inter,
    fontSize: LABEL_SIZE,
    fontWeight: 600,
    color: accentColor,
    textTransform: "uppercase",
    letterSpacing: "0.28em",
    lineHeight: 1,
    textShadow: LABEL_TEXT_SHADOW,
    whiteSpace: "nowrap",
  };

  const [leadingContent, trailingContent] = sides;
  const [leadingLabel, trailingLabel] = labels;
  const desatFilter = "saturate(0.4) brightness(0.85)";

  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute",
          overflow: "hidden",
          ...leadingSideStyle,
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: leadingTransform,
            opacity: sideOpacity,
            filter: leadingContent.desaturate ? desatFilter : undefined,
          }}
        >
          <SideContent
            content={leadingContent}
            palette={palette}
            accentColor={accentColor}
            localFrame={localFrame}
            statFontSize={statFontSize}
          />
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          overflow: "hidden",
          ...trailingSideStyle,
        }}
      >
        <div
          style={{
            width: "100%",
            height: "100%",
            transform: trailingTransform,
            opacity: sideOpacity,
            filter: trailingContent.desaturate ? desatFilter : undefined,
          }}
        >
          <SideContent
            content={trailingContent}
            palette={palette}
            accentColor={accentColor}
            localFrame={localFrame}
            statFontSize={statFontSize}
          />
        </div>
      </div>

      <div style={dividerStyle} />

      <div style={leadingLabelWrapperStyle}>
        <div
          style={{
            ...labelStyle,
            transform: `translateY(${labelY}px)`,
            opacity: labelOpacity,
          }}
        >
          {leadingLabel}
        </div>
      </div>

      <div style={trailingLabelWrapperStyle}>
        <div
          style={{
            ...labelStyle,
            transform: `translateY(${labelY}px)`,
            opacity: labelOpacity,
          }}
        >
          {trailingLabel}
        </div>
      </div>
    </AbsoluteFill>
  );
};
