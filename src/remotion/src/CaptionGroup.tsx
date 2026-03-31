import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import type { WordGroup, StyleConfig } from "./types";

/**
 * Renders a single group of 2-4 words with full animation.
 * This is the heart of the caption system — each group gets:
 * - Per-word pop-in/spring/slide/typewriter/wave animation
 * - Active word highlighting (color + scale)
 * - Keyword emphasis (larger size + glow + vibrant color)
 * - Pill background with rounded corners
 * - Multi-layer text shadows for depth
 * - Fade in/out at group boundaries
 */
export const CaptionGroup: React.FC<{
  group: WordGroup;
  style: StyleConfig;
  keywordSet: Set<string>;
  kwColorIndex: number;
}> = ({ group, style, keywordSet, kwColorIndex }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const groupStart = group.start;
  const groupEnd = group.end;
  const groupDuration = groupEnd - groupStart;

  // Group-level fade envelope
  const fadeIn = interpolate(
    t,
    [groupStart, groupStart + style.fadeInMs / 1000],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const fadeOut = interpolate(
    t,
    [groupEnd - style.fadeOutMs / 1000, groupEnd],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const opacity = fadeIn * fadeOut;

  if (opacity <= 0) return null;

  // Group-level entrance animation (affects the whole pill)
  const groupAge = Math.max(0, t - groupStart);
  const entranceDur = style.animationDuration / 1000;

  let groupScale = 1;
  let groupTranslateY = 0;

  if (style.animation === "spring" || style.animation === "pop") {
    const springVal = spring({
      frame: Math.max(0, frame - Math.round(groupStart * fps)),
      fps,
      config: {
        damping: style.animation === "spring" ? 12 : 18,
        stiffness: style.animation === "spring" ? 180 : 260,
        mass: 0.8,
      },
    });
    groupScale = interpolate(springVal, [0, 1], [0.3, 1]);
  } else if (style.animation === "slide") {
    const slideProgress = interpolate(
      groupAge,
      [0, entranceDur],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
    );
    groupTranslateY = interpolate(slideProgress, [0, 1], [40, 0]);
    groupScale = interpolate(slideProgress, [0, 1], [0.8, 1]);
  } else if (style.animation === "typewriter") {
    // Typewriter: group appears instantly, words reveal one by one
    groupScale = 1;
  }

  // Build word elements
  let runningKwIdx = kwColorIndex;
  const wordElements = group.words.map((word, wi) => {
    const wordStart = word.start;
    const wordEnd = word.end;
    const isActive = t >= wordStart && t < wordEnd + 0.05;
    const isPast = t >= wordEnd + 0.05;
    const cleanWord = word.word.replace(/[.,!?;:'"\\]/g, "").toLowerCase();
    const isKeyword = keywordSet.has(cleanWord);

    // Per-word animation
    let wordScale = 1;
    let wordOpacity = 1;
    let wordTranslateY = 0;
    const wordAge = Math.max(0, t - wordStart);

    if (style.animation === "typewriter") {
      // Words appear one by one
      wordOpacity = t >= wordStart ? 1 : 0;
    } else if (style.animation === "wave") {
      // Each word has a cascading delay
      const waveDelay = wi * 0.05;
      const waveAge = Math.max(0, groupAge - waveDelay);
      const waveProgress = interpolate(
        waveAge,
        [0, entranceDur],
        [0, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.back(1.5)) }
      );
      wordScale = interpolate(waveProgress, [0, 1], [0.5, 1]);
      wordTranslateY = interpolate(waveProgress, [0, 1], [20, 0]);
      wordOpacity = waveProgress;
    } else if (style.animation === "spring" || style.animation === "pop") {
      // Per-word spring (slight stagger within group)
      const stagger = wi * 0.03;
      const wordSpring = spring({
        frame: Math.max(0, frame - Math.round((groupStart + stagger) * fps)),
        fps,
        config: {
          damping: 14,
          stiffness: 200,
          mass: 0.6,
        },
      });
      wordScale = interpolate(wordSpring, [0, 1], [0.4, 1]);
      wordOpacity = wordSpring;
    }

    // Active word emphasis
    if (isActive) {
      const activeSpring = spring({
        frame: Math.max(0, frame - Math.round(wordStart * fps)),
        fps,
        config: { damping: 15, stiffness: 300, mass: 0.5 },
      });
      wordScale *= interpolate(activeSpring, [0, 1], [1, style.activeWordScale]);
    }

    // Keyword scaling
    const fontSize = isKeyword ? style.keywordFontSize : style.baseFontSize;
    const fontWeight = isKeyword ? 900 : style.fontWeight;

    // Color logic
    let color = style.dimColor;
    if (isActive) {
      color = isKeyword
        ? style.keywordColors[runningKwIdx % style.keywordColors.length]
        : style.activeColor;
    } else if (isPast) {
      color = isKeyword
        ? style.keywordColors[runningKwIdx % style.keywordColors.length]
        : style.textColor;
    }

    if (isKeyword) runningKwIdx++;

    // Text shadow CSS
    const shadowCSS = style.shadowLayers
      .map((s) => `${s.x}px ${s.y}px ${s.blur}px ${s.color}`)
      .join(", ");

    // Keyword glow
    const glowCSS =
      isKeyword && style.glowEnabled && (isActive || isPast)
        ? `, 0 0 ${style.glowRadius}px ${style.glowColor}, 0 0 ${style.glowRadius * 2}px ${style.glowColor}40`
        : "";

    const display = word.punctuated_word || word.word;

    return (
      <span
        key={wi}
        style={{
          display: "inline-block",
          fontSize,
          fontWeight,
          fontFamily: style.fontFamily,
          color,
          textShadow: shadowCSS + glowCSS,
          transform: `scale(${wordScale}) translateY(${wordTranslateY}px)`,
          opacity: wordOpacity,
          marginRight: wi < group.words.length - 1 ? "0.25em" : 0,
          textTransform: style.textTransform,
          lineHeight: style.lineHeight,
          transition: "color 0.06s ease-out",
          willChange: "transform, opacity, color",
        }}
      >
        {display}
      </span>
    );
  });

  // Pill background dimensions
  const pillStyle: React.CSSProperties = style.pillEnabled
    ? {
        background: style.pillColor,
        borderRadius: style.pillRadius,
        padding: `${style.pillPadding[1]}px ${style.pillPadding[0]}px`,
      }
    : {
        padding: `${style.pillPadding[1]}px ${style.pillPadding[0]}px`,
      };

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: `${style.yPercent}%`,
        transform: `translateY(-50%) scale(${groupScale}) translateY(${groupTranslateY}px)`,
        opacity,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        willChange: "transform, opacity",
      }}
    >
      <div
        style={{
          ...pillStyle,
          display: "inline-flex",
          flexWrap: "wrap",
          justifyContent: "center",
          alignItems: "baseline",
          maxWidth: "85%",
          gap: "0",
        }}
      >
        {wordElements}
      </div>
    </div>
  );
};
