import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { noise2D } from "@remotion/noise";
import type { TikTokPage } from "@remotion/captions";
import type { ProjectedWord, StyleConfig } from "./types";

/**
 * Compute font size from token count.
 * Fewer words = bigger text. This replaces all hardcoded font sizes.
 */
function autoFontSize(tokenCount: number, scale: number = 1.0): number {
  // Base: 200px for 1 word on 1080px wide screen
  const sizes: Record<number, number> = {
    1: 200,
    2: 155,
    3: 125,
    4: 105,
    5: 90,
  };
  const base = sizes[Math.min(tokenCount, 5)] || 90;
  return Math.round(base * scale);
}

/**
 * Build text shadow CSS from style config shadow layers.
 */
function buildShadowCSS(layers: StyleConfig["shadowLayers"]): string {
  return layers.map((s) => `${s.x}px ${s.y}px ${s.blur}px ${s.color}`).join(", ");
}

/**
 * Find the original ProjectedWord that matches a token's timing.
 */
function findOriginalWord(
  tokenStartMs: number,
  words: ProjectedWord[]
): ProjectedWord | undefined {
  const tokenStartS = tokenStartMs / 1000;
  return words.find(
    (w) => Math.abs(w.start - tokenStartS) < 0.08
  );
}

/**
 * Renders a single page of captions with auto-sizing and word-by-word highlighting.
 * This is the heart of the caption system.
 */
export const CaptionPage: React.FC<{
  page: TikTokPage;
  style: StyleConfig;
  keywordSet: Set<string>;
  words: ProjectedWord[];
}> = ({ page, style, keywordSet, words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const tMs = t * 1000;

  const pageStart = page.startMs / 1000;
  const pageEnd = (page.startMs + page.durationMs) / 1000;

  // Guard: skip pages with NaN, zero, or negligible duration
  // NaN comparisons always return false, so check isFinite explicitly
  if (!isFinite(pageStart) || !isFinite(pageEnd) || pageEnd - pageStart < 0.01) return null;

  // Fade envelope — clamp durations to fit within page
  const maxFade = (pageEnd - pageStart) / 3;
  const fadeInDur = Math.min(0.08, maxFade);
  const fadeOutDur = Math.min(0.10, maxFade);
  const fadeIn = interpolate(t, [pageStart, pageStart + fadeInDur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(t, [pageEnd - fadeOutDur, pageEnd], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = fadeIn * fadeOut;
  if (opacity <= 0) return null;

  // Page entrance animation
  const pageAge = Math.max(0, frame - Math.round(pageStart * fps));
  let pageScale = 1;
  let pageTranslateY = 0;

  if (style.animation === "spring" || style.animation === "pop") {
    const springVal = spring({
      frame: pageAge,
      fps,
      config: {
        damping: style.animation === "spring" ? 12 : 18,
        stiffness: style.animation === "spring" ? 180 : 260,
        mass: 0.8,
      },
    });
    pageScale = interpolate(springVal, [0, 1], [0.3, 1]);
  } else if (style.animation === "slide") {
    const slideP = interpolate(pageAge / fps, [0, 0.15], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });
    pageTranslateY = interpolate(slideP, [0, 1], [40, 0]);
    pageScale = interpolate(slideP, [0, 1], [0.8, 1]);
  }

  // Subtle organic sway using noise (replaces static positioning)
  const swayX = noise2D("sway-x", frame * 0.008, 0) * 2;
  const swayY = noise2D("sway-y", 0, frame * 0.008) * 1.5;

  const tokens = page.tokens;
  const tokenCount = tokens.length;
  const fontSize = autoFontSize(tokenCount);

  // Track keyword color index
  let kwIdx = 0;

  const wordElements = tokens.map((token, ti) => {
    const tokenStart = token.fromMs / 1000;
    const tokenEnd = token.toMs / 1000;
    const isActive = t >= tokenStart && t < tokenEnd + 0.05;
    const isPast = t >= tokenEnd + 0.05;
    const isFuture = t < tokenStart;

    const cleanWord = token.text.trim().replace(/[.,!?;:'"\\]/g, "").toLowerCase();
    const isKeyword = keywordSet.has(cleanWord);
    const originalWord = findOriginalWord(token.fromMs, words);
    const speakerIdx = originalWord?.speaker ?? 0;

    // Per-word animation
    let wordScale = 1;
    let wordOpacity = 1;

    if (style.animation === "typewriter") {
      wordOpacity = t >= tokenStart ? 1 : 0;
    } else if (style.animation === "wave") {
      const waveDelay = ti * 0.06;
      const waveAge = Math.max(0, (t - pageStart) - waveDelay);
      const waveP = interpolate(waveAge, [0, 0.2], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.back(1.5)),
      });
      wordScale = interpolate(waveP, [0, 1], [0.5, 1]);
      wordOpacity = waveP;
    }

    // Active word emphasis — the signature Captions AI effect
    const activeScale = 1.3;
    if (isActive) {
      const activeSpring = spring({
        frame: Math.max(0, frame - Math.round(tokenStart * fps)),
        fps,
        config: { damping: 14, stiffness: 300, mass: 0.5 },
      });
      wordScale *= interpolate(activeSpring, [0, 1], [0.88, activeScale]);
    }

    // Font size: keywords get 1.35x
    const wordFontSize = isKeyword ? Math.round(fontSize * 1.35) : fontSize;

    // Color logic
    const speakerActiveColor = style.speakerColors?.[speakerIdx % (style.speakerColors?.length || 1)];
    let color = style.dimColor;
    if (isActive) {
      color = isKeyword
        ? style.keywordColors[kwIdx % style.keywordColors.length]
        : (speakerActiveColor || style.activeColor);
    } else if (isPast) {
      color = isKeyword
        ? style.keywordColors[kwIdx % style.keywordColors.length]
        : style.textColor;
    }
    if (isKeyword) kwIdx++;

    // Shadow + glow
    const shadowCSS = buildShadowCSS(style.shadowLayers);
    const glowCSS =
      isKeyword && style.glowEnabled && (isActive || isPast)
        ? `, 0 0 ${Math.round(wordFontSize * 0.18)}px ${style.glowColor}, 0 0 ${Math.round(wordFontSize * 0.35)}px ${style.glowColor}40`
        : "";

    const display = token.text.trim();

    const wordStyle: React.CSSProperties = {
      display: "block",
      fontSize: wordFontSize,
      fontWeight: isKeyword ? 900 : style.fontWeight,
      fontFamily: style.fontFamily,
      color,
      textShadow: shadowCSS + glowCSS,
      transform: `scale(${wordScale})`,
      opacity: wordOpacity,
      textTransform: style.textTransform,
      lineHeight: style.lineHeight,
      transition: "color 0.06s ease-out",
      willChange: "transform, opacity, color",
      textAlign: "center",
      whiteSpace: "nowrap",
    };

    // Gradient text
    if (style.gradientColors && style.gradientColors.length >= 2 && !style.outlineOnly) {
      wordStyle.background = `linear-gradient(${style.gradientDirection || "to right"}, ${style.gradientColors.join(", ")})`;
      wordStyle.WebkitBackgroundClip = "text";
      wordStyle.WebkitTextFillColor = "transparent";
      delete wordStyle.color;
    }

    // Outline-only
    if (style.outlineOnly && style.textStroke) {
      wordStyle.WebkitTextStroke = `${style.textStroke.width}px ${style.textStroke.color}`;
      wordStyle.WebkitTextFillColor = "transparent";
      delete wordStyle.color;
    } else if (style.textStroke && !style.outlineOnly) {
      wordStyle.WebkitTextStroke = `${style.textStroke.width}px ${style.textStroke.color}`;
    }

    return (
      <span key={ti} style={wordStyle}>
        {display}
      </span>
    );
  });

  // Container background
  const bgShape = style.backgroundShape || (style.pillEnabled ? "pill" : "none");
  let containerBg: React.CSSProperties = {};
  if (bgShape === "pill" && style.pillEnabled) {
    containerBg = {
      background: style.pillColor,
      borderRadius: style.pillRadius,
      padding: `${Math.round(fontSize * 0.08)}px ${Math.round(fontSize * 0.16)}px`,
    };
  } else if (bgShape === "box") {
    containerBg = {
      background: style.pillColor,
      padding: `${Math.round(fontSize * 0.08)}px ${Math.round(fontSize * 0.16)}px`,
    };
  }

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: `${style.yPercent}%`,
        transform: `translateY(-50%) scale(${pageScale}) translate(${swayX}px, ${pageTranslateY + swayY}px)`,
        opacity,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        willChange: "transform, opacity",
      }}
    >
      <div
        style={{
          ...containerBg,
          display: "inline-flex",
          flexDirection: "column",
          alignItems: "center",
          maxWidth: "92%",
          gap: "2px",
        }}
      >
        {wordElements}
      </div>
    </div>
  );
};
