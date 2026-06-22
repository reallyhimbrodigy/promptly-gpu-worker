import React from "react";
import { AbsoluteFill, Easing, interpolate, OffthreadVideo } from "remotion";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadDMSerifDisplay } from "@remotion/google-fonts/DMSerifDisplay";
import type { SceneTitleProps } from "../types";
import { TIKTOK_SAFE_RIGHT } from "../../shared/safeZone";

const inter = loadInter();
const dmSerifDisplay = loadDMSerifDisplay();

export const SCENE_TITLE_PEAK_PROGRESS = 0.5;

const TITLE_SIZE = 130;
const LABEL_SIZE = 34;
const DIVIDER_WIDTH = 100;
const DIVIDER_HEIGHT = 2;
const LABEL_TO_DIVIDER_GAP = 28;
const DIVIDER_TO_TITLE_GAP = 32;

const THEMES = {
  dark: {
    panelGradient:
      "linear-gradient(135deg, #0A0A0A 0%, #141416 55%, #1C1C1F 100%)",
    panelFallback: "#0F0F10",
    titleColor: "#F2E9D6",
    labelColor: "#E8DFD0",
  },
  light: {
    panelGradient:
      "linear-gradient(135deg, #F2E9D6 0%, #ECE2CB 55%, #E3D8BE 100%)",
    panelFallback: "#ECE2CB",
    titleColor: "#16120E",
    labelColor: "#5A4E3D",
  },
} as const;

/**
 * SceneTitle — chapter-break transition. A typographic title panel wipes
 * across the frame, holds long enough to read, and wipes back out to reveal
 * clip B. The A → B cut is buried behind the panel at peak coverage.
 *
 * Progress choreography (0 → 1):
 *   0    → 0.20  panel wipes in (clipPath inset 100 → 0, cubic ease-out)
 *   0.10 → 0.28  label drops in (translateY −20 → 0) + fades
 *   0.12 → 0.28  divider scaleX 0 → 1
 *   0.16 → 0.32  title slides up (translateY +20 → 0) + fades
 *   0.50        A → B cut happens under the panel
 *   0.68 → 0.84  title, divider, label drift out + fade
 *   0.78 → 1.00  panel wipes out (cubic ease-in)
 */
export const SceneTitle: React.FC<SceneTitleProps> = ({
  clipA,
  clipB,
  progress,
  style,
  title,
  label,
  variant = "full",
  theme = "dark",
  accentColor = "#C8551F",
  titleColor,
  labelColor,
  showDivider = true,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const palette = THEMES[theme];
  const resolvedTitleColor = titleColor ?? palette.titleColor;
  const resolvedLabelColor = labelColor ?? palette.labelColor;
  const hasLabel = Boolean(label);
  const renderDivider = hasLabel && showDivider;

  const showClipB = progress >= SCENE_TITLE_PEAK_PROGRESS;

  const enterInset = interpolate(progress, [0, 0.2], [100, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exitInset = interpolate(progress, [0.78, 1], [0, 100], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const isExiting = progress > 0.78;
  const clipPath: string = (() => {
    if (variant === "half-bottom") {
      if (isExiting) return `inset(0% 0 ${exitInset}% 0)`;
      return `inset(${enterInset}% 0 0% 0)`;
    }
    if (isExiting) return `inset(${exitInset}% 0 0% 0)`;
    return `inset(0% 0 ${enterInset}% 0)`;
  })();

  const panelStyle: React.CSSProperties = (() => {
    if (variant === "half-top") {
      return { top: 0, left: 0, right: 0, height: "50%" };
    }
    if (variant === "half-bottom") {
      return { bottom: 0, left: 0, right: 0, height: "50%" };
    }
    return { top: 0, left: 0, right: 0, bottom: 0 };
  })();

  const labelEnterY = interpolate(progress, [0.1, 0.28], [-20, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelEnterOpacity = interpolate(progress, [0.1, 0.28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelExitY = interpolate(progress, [0.68, 0.84], [0, -15], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelExitOpacity = interpolate(progress, [0.68, 0.84], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const labelY = labelEnterY + labelExitY;
  const labelOpacity = labelEnterOpacity * labelExitOpacity;

  const dividerScale = interpolate(progress, [0.12, 0.28], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const dividerOpacity = labelOpacity;
  const dividerY = labelExitY;

  const titleEnterY = interpolate(progress, [0.16, 0.32], [20, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleEnterOpacity = interpolate(progress, [0.16, 0.32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleExitY = interpolate(progress, [0.68, 0.84], [0, 20], {
    easing: Easing.in(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleExitOpacity = interpolate(progress, [0.68, 0.84], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleY = titleEnterY + titleExitY;
  const titleOpacity = titleEnterOpacity * titleExitOpacity;

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      <AbsoluteFill>
        <OffthreadVideo
          src={showClipB ? clipB : clipA}
          startFrom={showClipB ? startFromB : startFromA}
          playbackRate={showClipB ? playbackRateB : playbackRateA}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>

      <div
        style={{
          position: "absolute",
          ...panelStyle,
          backgroundColor: palette.panelFallback,
          backgroundImage: palette.panelGradient,
          clipPath,
          WebkitClipPath: clipPath,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          // CARVE-OUT: the panel (wash) fills the full frame by design, but
          // the TITLE TEXT must clear the TikTok action rail — pad both sides
          // by the rail width so the centered title wraps inside the safe rect
          // while the wash behind it still covers the frame.
          padding: `0 ${TIKTOK_SAFE_RIGHT}px`,
          boxSizing: "border-box",
        }}
      >
        {hasLabel && (
          <div
            style={{
              fontFamily: inter.fontFamily,
              fontSize: LABEL_SIZE,
              fontWeight: 600,
              color: resolvedLabelColor,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              lineHeight: 1,
              transform: `translateY(${labelY}px)`,
              opacity: labelOpacity,
              marginBottom: renderDivider ? LABEL_TO_DIVIDER_GAP : 40,
              // Letter-spacing optically offsets the word; nudge it back.
              paddingLeft: "0.28em",
            }}
          >
            {label}
          </div>
        )}

        {renderDivider && (
          <div
            style={{
              width: DIVIDER_WIDTH,
              height: DIVIDER_HEIGHT,
              backgroundColor: accentColor,
              transform: `translateY(${dividerY}px) scaleX(${dividerScale})`,
              transformOrigin: "center",
              opacity: dividerOpacity,
              marginBottom: DIVIDER_TO_TITLE_GAP,
            }}
          />
        )}

        <div
          style={{
            fontFamily: dmSerifDisplay.fontFamily,
            fontSize: TITLE_SIZE,
            fontWeight: 400,
            color: resolvedTitleColor,
            lineHeight: 0.98,
            letterSpacing: "0.01em",
            textTransform: "uppercase",
            textAlign: "center",
            whiteSpace: "pre-line",
            transform: `translateY(${titleY}px)`,
            opacity: titleOpacity,
          }}
        >
          {title}
        </div>
      </div>
    </AbsoluteFill>
  );
};
