import React from "react";
import { AbsoluteFill, interpolate, spring, useVideoConfig } from "remotion";
import { SPRING_SNAPPY } from "../shared/springs";
import { MG_FONTS } from "../shared/fonts";
import { resolveMGPosition } from "../shared/positioning";
import { useMGPhase } from "../shared/useMGPhase";
import type { QuoteCardProps } from "./types";


const CARD_PADDING_X = 72;
const CARD_PADDING_Y = 60;
const DEFAULT_CARD_WIDTH = 756; // ~70% of 1080 — smaller footprint
const CARD_RADIUS = 8;
const GIANT_MARK_SIZE = 260;
const ATTRIBUTION_GAP = 24;

const THEMES = {
  dark: {
    cardGradient:
      "linear-gradient(135deg, #0A0A0A 0%, #141416 55%, #1C1C1F 100%)",
    cardFallback: "#0F0F10",
    quoteColor: "#F2E9D6",
    attributionColor: "#A89888",
    defaultAccent: "#F2E9D6",
    markOpacity: 0.15,
  },
  light: {
    cardGradient:
      "linear-gradient(135deg, #F2E9D6 0%, #ECE2CB 55%, #E3D8BE 100%)",
    cardFallback: "#ECE2CB",
    quoteColor: "#16120E",
    attributionColor: "#5A4E3D",
    defaultAccent: "#C8551F",
    markOpacity: 1,
  },
} as const;

export const QuoteCard: React.FC<QuoteCardProps> = ({
  startMs,
  durationMs,
  enterFrames,
  exitFrames,
  quote,
  attribution,
  theme = "dark",
  cardColor,
  quoteColor,
  attributionColor,
  accentColor,
  quoteFont,
  quoteFontSize = 52,
  width = DEFAULT_CARD_WIDTH,
  anchor,
  offsetX,
  offsetY,
  scale,
}) => {
  const palette = THEMES[theme];
  const resolvedQuoteColor = quoteColor ?? palette.quoteColor;
  const resolvedAttributionColor = attributionColor ?? palette.attributionColor;
  const resolvedAccentColor = accentColor ?? palette.defaultAccent;
  const { containerStyle, wrapperStyle } = resolveMGPosition({
    anchor,
    offsetX,
    offsetY,
    scale,
  });
  const { fps } = useVideoConfig();
  const { visible, localFrame, exitProgress } = useMGPhase(
    { startMs, durationMs, enterFrames, exitFrames },
    { defaultEnterFrames: 22, defaultExitFrames: 14 },
  );

  if (!visible) return null;

  const resolvedQuoteFont = quoteFont ?? MG_FONTS.playfairDisplay;

  const cardSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 14,
  });
  const cardScale = interpolate(cardSpring, [0, 1], [0.96, 1]);
  const cardFadeIn = interpolate(localFrame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const marksSpring = spring({
    fps,
    frame: localFrame,
    config: SPRING_SNAPPY,
    durationInFrames: 10,
  });
  const marksScale = interpolate(marksSpring, [0, 1], [0.8, 1]);
  const marksFadeIn = interpolate(localFrame, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const quoteSpring = spring({
    fps,
    frame: localFrame - 6,
    config: SPRING_SNAPPY,
    durationInFrames: 14,
  });
  const quoteY = interpolate(quoteSpring, [0, 1], [8, 0]);
  const quoteFadeIn = interpolate(localFrame, [6, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const attributionFadeIn = interpolate(localFrame, [14, 22], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const marksParallaxY = Math.sin(localFrame * 0.05) * 1;

  const exitDriftY = exitProgress * 12;
  const exitOpacity = 1 - exitProgress;

  const quoteExitOpacity = interpolate(exitProgress, [0, 0.714], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const cardOpacity = cardFadeIn * exitOpacity;
  const marksOpacity = marksFadeIn * palette.markOpacity * exitOpacity;
  const quoteOpacity = quoteFadeIn * quoteExitOpacity;
  const attributionOpacity = attributionFadeIn * exitOpacity;

  return (
    <AbsoluteFill style={containerStyle}>
      <div style={wrapperStyle}>
      <div
        style={{
          position: "relative",
          width,
          backgroundColor: cardColor ?? palette.cardFallback,
          backgroundImage: cardColor ? undefined : palette.cardGradient,
          borderRadius: CARD_RADIUS,
          paddingLeft: CARD_PADDING_X,
          paddingRight: CARD_PADDING_X,
          paddingTop: CARD_PADDING_Y,
          paddingBottom: CARD_PADDING_Y,
          boxShadow:
            "0 18px 54px rgba(0,0,0,0.45), 0 2px 6px rgba(0,0,0,0.3)",
          overflow: "visible",
          transform: `translateY(${exitDriftY}px) scale(${cardScale})`,
          opacity: cardOpacity,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: -70,
            left: 32,
            fontFamily: resolvedQuoteFont,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: GIANT_MARK_SIZE,
            lineHeight: 1,
            color: resolvedAccentColor,
            opacity: marksOpacity,
            transform: `scale(${marksScale}) translateY(${marksParallaxY}px)`,
            transformOrigin: "top left",
            pointerEvents: "none",
            userSelect: "none",
            zIndex: 1,
          }}
        >
          &ldquo;
        </div>

        <div
          style={{
            position: "relative",
            zIndex: 2,
            fontFamily: resolvedQuoteFont,
            fontStyle: "italic",
            fontWeight: 400,
            fontSize: quoteFontSize,
            lineHeight: 1.25,
            letterSpacing: "-0.005em",
            color: resolvedQuoteColor,
            textAlign: "left",
            transform: `translateY(${quoteY}px)`,
            opacity: quoteOpacity,
          }}
        >
          {quote}
        </div>

        <div
          style={{
            position: "relative",
            zIndex: 2,
            marginTop: ATTRIBUTION_GAP,
            fontFamily: MG_FONTS.inter,
            fontWeight: 500,
            fontSize: 24,
            letterSpacing: "0.08em",
            color: resolvedAttributionColor,
            textAlign: "left",
            opacity: attributionOpacity,
          }}
        >
          {"\u2014 " + attribution}
        </div>
      </div>
      </div>
    </AbsoluteFill>
  );
};
