import React from "react";
import {
  AbsoluteFill,
  Img,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { LowerThirdProps } from "./types";


const CARD_PADDING_X = 56;
const CARD_PADDING_Y = 34;
const ACCENT_WIDTH = 5;
const CARD_RADIUS = 4;
const AVATAR_SIZE = 96;
const AVATAR_GAP = 28;

const THEMES = {
  dark: {
    cardGradient:
      "linear-gradient(135deg, #0A0A0A 0%, #141416 55%, #1C1C1F 100%)",
    cardFallback: "#0F0F10",
    nameColor: "#FFFFFF",
    titleColor: "#B8B8B8",
  },
  light: {
    cardGradient:
      "linear-gradient(135deg, #F2E9D6 0%, #ECE2CB 55%, #E3D8BE 100%)",
    cardFallback: "#ECE2CB",
    nameColor: "#16120E",
    titleColor: "#5A4E3D",
  },
} as const;

export const LowerThird: React.FC<LowerThirdProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  name,
  title,
  accentColor = "#C8551F",
  avatarSrc,
  theme = "dark",
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const palette = THEMES[theme];
  const { containerStyle, wrapperStyle } = resolveMGPosition(
    { anchor, offsetX, offsetY, scale },
    { anchor: "bottom-left", offsetX: 80, offsetY: -180 },
  );
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 18, defaultExitFrames: 12 },
  );

  if (!visible) return null;

  const barSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 6,
  });
  const barFadeIn = interpolate(localFrame, [0, 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cardSpring = spring({
    fps,
    frame: localFrame - 4,
    config: SPRING_SNAPPY,
    durationInFrames: 10,
  });
  const cardX = interpolate(cardSpring, [0, 1], [-30, 0]);
  const cardFadeIn = interpolate(localFrame, [4, 14], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const nameSpring = spring({
    fps,
    frame: localFrame - 6,
    config: SPRING_SNAPPY,
    durationInFrames: 10,
  });
  const nameX = interpolate(nameSpring, [0, 1], [-20, 0]);
  const nameFadeIn = interpolate(localFrame, [6, 16], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const titleSpring = spring({
    fps,
    frame: localFrame - 10,
    config: SPRING_SNAPPY,
    durationInFrames: 8,
  });
  const titleX = interpolate(titleSpring, [0, 1], [-20, 0]);
  const titleFadeIn = interpolate(localFrame, [10, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const avatarSpring = spring({
    fps,
    frame: localFrame - 2,
    config: SPRING_SNAPPY,
    durationInFrames: 10,
  });
  const avatarScale = interpolate(avatarSpring, [0, 1], [0.85, 1]);
  const avatarFadeIn = interpolate(localFrame, [2, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const parallaxY = Math.sin(localFrame * 0.06) * 1;

  const exitDriftX = exitProgress * -25;
  const exitOpacity = 1 - exitProgress;
  const barExitScaleY = 1 - exitProgress;

  const barOpacity = barFadeIn;
  const cardOpacity = cardFadeIn;
  const nameOpacity = nameFadeIn;
  const titleOpacity = titleFadeIn;
  const avatarOpacity = avatarFadeIn;

  const isExiting = exitProgress > 0;
  const barScaleY = isExiting ? barExitScaleY : barSpring;
  const barOrigin = isExiting ? "top" : "bottom";

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          transform: `translate(${exitDriftX}px, ${parallaxY}px)`,
          opacity: exitOpacity,
        }}
      >
        {avatarSrc ? (
          <div
            style={{
              width: AVATAR_SIZE,
              height: AVATAR_SIZE,
              borderRadius: AVATAR_SIZE / 2,
              overflow: "hidden",
              marginRight: AVATAR_GAP,
              transform: `scale(${avatarScale})`,
              opacity: avatarOpacity,
              flexShrink: 0,
              boxShadow: "0 6px 18px rgba(0,0,0,0.35)",
            }}
          >
            <Img
              src={avatarSrc}
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: "block",
              }}
            />
          </div>
        ) : null}

        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "stretch",
            transform: `translateX(${cardX}px)`,
          }}
        >
          <div
            style={{
              width: ACCENT_WIDTH,
              backgroundColor: accentColor,
              borderTopLeftRadius: CARD_RADIUS,
              borderBottomLeftRadius: CARD_RADIUS,
              transform: `scaleY(${barScaleY})`,
              transformOrigin: barOrigin,
              opacity: barOpacity,
              flexShrink: 0,
            }}
          />

          <div
            style={{
              backgroundColor: palette.cardFallback,
              backgroundImage: palette.cardGradient,
              paddingTop: CARD_PADDING_Y,
              paddingBottom: CARD_PADDING_Y,
              paddingLeft: CARD_PADDING_X,
              paddingRight: CARD_PADDING_X,
              opacity: cardOpacity,
              borderTopRightRadius: CARD_RADIUS,
              borderBottomRightRadius: CARD_RADIUS,
              boxShadow:
                "0 14px 40px rgba(0,0,0,0.45), 0 2px 4px rgba(0,0,0,0.3)",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              minWidth: 280,
            }}
          >
            <div
              style={{
                fontFamily: MG_FONTS.dmSerifDisplay,
                fontSize: 68,
                fontWeight: 400,
                color: palette.nameColor,
                letterSpacing: "0.01em",
                lineHeight: 1,
                textTransform: "uppercase",
                transform: `translateX(${nameX}px)`,
                opacity: nameOpacity,
                whiteSpace: "nowrap",
              }}
            >
              {name}
            </div>

            <div
              style={{
                fontFamily: MG_FONTS.inter,
                fontSize: 32,
                fontWeight: 500,
                color: palette.titleColor,
                letterSpacing: "0.12em",
                lineHeight: 1.2,
                textTransform: "uppercase",
                marginTop: 14,
                transform: `translateX(${titleX}px)`,
                opacity: titleOpacity,
                whiteSpace: "nowrap",
              }}
            >
              {title}
            </div>
          </div>
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
