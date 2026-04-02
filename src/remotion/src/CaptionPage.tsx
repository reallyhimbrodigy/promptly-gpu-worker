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
 * Compute base font size from token count.
 * Fewer words = bigger text. Sized for 1080px wide screen.
 */
/**
 * Compute base font size from token count.
 * Sized for 1080px wide screen. Reference: Captions AI uses ~60-80px
 * for regular text, never exceeding ~100px even for single words.
 */
function autoFontSize(tokenCount: number): number {
  const sizes: Record<number, number> = {
    1: 90,
    2: 78,
    3: 68,
    4: 62,
    5: 56,
  };
  return sizes[Math.min(tokenCount, 5)] || 56;
}

/**
 * Find the original ProjectedWord that matches a token's timing.
 */
function findOriginalWord(
  tokenStartMs: number,
  words: ProjectedWord[]
): ProjectedWord | undefined {
  const tokenStartS = tokenStartMs / 1000;
  return words.find((w) => Math.abs(w.start - tokenStartS) < 0.08);
}

/**
 * Renders a single page of captions with Captions AI-quality animation.
 *
 * KEY FEATURE: Mixed-size cascade layout (the Captions AI signature)
 * - Regular/context words are rendered at a smaller base size
 * - Keywords/emphasis words are rendered 1.6-2x larger
 * - When there are both regular and keyword tokens, they stack:
 *   Line 1 (top): smaller context words
 *   Line 2 (bottom): LARGE keyword/emphasis word
 * - This creates the distinctive two-tier visual hierarchy seen in every
 *   Captions AI video analyzed (V1-V4)
 *
 * Other principles:
 * - Subtle scale pops (1.08-1.15) feel premium; giant jumps look cheap
 * - Active word gets simultaneous scale + color + glow
 * - Strong black outline ensures readability on any background
 * - Past words return to full brightness (not dimmed)
 * - Spring physics with visible overshoot = organic, alive
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

  const pageStart = page.startMs / 1000;
  // Compute page end from last token's end time (TikTokPage has no durationMs)
  const lastToken = page.tokens[page.tokens.length - 1];
  const pageEnd = lastToken ? lastToken.toMs / 1000 : pageStart + 0.5;

  if (!isFinite(pageStart) || !isFinite(pageEnd) || pageEnd - pageStart < 0.01)
    return null;

  // ── Fade envelope ──────────────────────────────────────────────────────
  const maxFade = (pageEnd - pageStart) / 3;
  const fadeInDur = Math.min(0.1, maxFade);
  const fadeOutDur = Math.min(0.12, maxFade);
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

  // ── Page entrance ──────────────────────────────────────────────────────
  const pageAge = Math.max(0, frame - Math.round(pageStart * fps));
  const entranceSpring = spring({
    frame: pageAge,
    fps,
    config: { damping: 14, stiffness: 170, mass: 0.7 },
  });
  const pageScale = interpolate(entranceSpring, [0, 1], [0.88, 1]);
  const pageTranslateY = interpolate(entranceSpring, [0, 1], [12, 0]);

  // ── Organic sway ──────────────────────────────────────────────────────
  const swayX = noise2D("sx", frame * 0.006, 0) * 1.5;
  const swayY = noise2D("sy", 0, frame * 0.006) * 1.2;

  const tokens = page.tokens;
  const tokenCount = tokens.length;
  const baseFontSize = autoFontSize(tokenCount);

  // ── Classify tokens into context vs emphasis ──────────────────────────
  // This drives the mixed-size cascade layout
  const tokenMeta = tokens.map((token) => {
    const cleanWord = token.text
      .trim()
      .replace(/[.,!?;:'"\\]/g, "")
      .toLowerCase();
    const isKeyword = keywordSet.has(cleanWord);
    return { token, cleanWord, isKeyword };
  });

  const hasKeywords = tokenMeta.some((m) => m.isKeyword);
  const keywordCount = tokenMeta.filter((m) => m.isKeyword).length;
  const contextCount = tokenCount - keywordCount;

  // Mixed-size cascade: if we have both keywords AND context words,
  // use the two-tier layout (small context line + large keyword line)
  const useCascadeLayout = hasKeywords && contextCount > 0 && tokenCount >= 2;

  // Font sizes for the cascade layout
  // Context words: slightly smaller (the "regular" line)
  // Keywords: moderately larger (the "emphasis" line)
  // Tighter ratio (0.82/1.22) looks professional; extreme ratios look amateur
  const contextFontSize = useCascadeLayout
    ? Math.round(baseFontSize * 0.82)
    : baseFontSize;
  const keywordFontSize = useCascadeLayout
    ? Math.round(baseFontSize * 1.22)
    : Math.round(baseFontSize * 1.12);

  // Keyword color cycling
  let kwIdx = 0;

  // ── Build word elements ────────────────────────────────────────────────
  // In cascade mode, we split into two rows:
  //   Row 1: context words (smaller, lighter)
  //   Row 2: keyword words (larger, colored)
  // In non-cascade mode, all words render in a single column

  const contextElements: React.ReactNode[] = [];
  const keywordElements: React.ReactNode[] = [];
  const allElements: React.ReactNode[] = [];

  tokenMeta.forEach(({ token, cleanWord, isKeyword }, ti) => {
    const tokenStart = token.fromMs / 1000;
    const tokenEnd = token.toMs / 1000;
    const isActive = t >= tokenStart && t < tokenEnd + 0.04;
    const isPast = t >= tokenEnd + 0.04;

    const originalWord = findOriginalWord(token.fromMs, words);
    const speakerIdx = originalWord?.speaker ?? 0;

    // ── Per-word scale animation ───────────────────────────────────────
    const wordActiveScale = isKeyword
      ? Math.min(style.activeWordScale * 1.08, 1.22)
      : Math.min(style.activeWordScale, 1.15);

    let wordScale = 1;

    if (isActive) {
      const activeAge = Math.max(0, frame - Math.round(tokenStart * fps));
      const activeSpring = spring({
        frame: activeAge,
        fps,
        config: { damping: 10, stiffness: 200, mass: 0.5 },
      });
      wordScale = interpolate(activeSpring, [0, 1], [0.92, wordActiveScale]);
    } else if (isPast) {
      const pastAge = Math.max(0, frame - Math.round((tokenEnd + 0.04) * fps));
      const settleSpring = spring({
        frame: pastAge,
        fps,
        config: { damping: 18, stiffness: 200, mass: 0.6 },
      });
      wordScale = interpolate(settleSpring, [0, 1], [wordActiveScale, 1]);
    }

    // ── Typewriter / Wave special modes ────────────────────────────────
    let wordOpacity = 1;
    if (style.animation === "typewriter") {
      wordOpacity = t >= tokenStart ? 1 : 0;
    } else if (style.animation === "wave") {
      const waveDelay = ti * 0.05;
      const waveAge = Math.max(0, t - pageStart - waveDelay);
      const waveP = interpolate(waveAge, [0, 0.18], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.back(1.3)),
      });
      if (!isActive && !isPast) {
        wordScale *= interpolate(waveP, [0, 1], [0.6, 1]);
        wordOpacity = waveP;
      }
    }

    // ── Font size (cascade-aware) ────────────────────────────────────────
    const wordFontSize = isKeyword ? keywordFontSize : contextFontSize;

    // ── Color logic ──────────────────────────────────────────────────────
    const kColors = style.keywordColors;
    const speakerColor =
      style.speakerColors?.[speakerIdx % (style.speakerColors?.length || 1)];

    let color: string;
    if (isActive) {
      color = isKeyword
        ? kColors[kwIdx % kColors.length]
        : speakerColor || style.activeColor;
    } else if (isPast) {
      color = isKeyword
        ? kColors[kwIdx % kColors.length]
        : style.textColor;
    } else {
      // Future words: dim in cascade context row, bright dim in keyword row
      color = isKeyword ? `${kColors[kwIdx % kColors.length]}70` : style.dimColor;
    }
    if (isKeyword) kwIdx++;

    // ── Shadow layers ────────────────────────────────────────────────────
    const shadowParts: string[] = style.shadowLayers.map(
      (s) => `${s.x}px ${s.y}px ${s.blur}px ${s.color}`
    );

    // Active word glow
    if (isActive && style.glowEnabled && style.glowColor !== "transparent") {
      const glowSize1 = Math.round(wordFontSize * 0.12);
      const glowSize2 = Math.round(wordFontSize * 0.25);
      shadowParts.push(
        `0 0 ${glowSize1}px ${style.glowColor}`,
        `0 0 ${glowSize2}px ${style.glowColor}60`
      );
    }
    // Keyword glow persists after active (dimmer)
    if (isPast && isKeyword && style.glowEnabled && style.glowColor !== "transparent") {
      const glowSize = Math.round(wordFontSize * 0.15);
      shadowParts.push(`0 0 ${glowSize}px ${style.glowColor}40`);
    }

    const textShadow = shadowParts.join(", ");
    const display = token.text.trim();

    // ── Build word style ─────────────────────────────────────────────────
    const wordStyle: React.CSSProperties = {
      display: "inline-block",
      fontSize: wordFontSize,
      fontWeight: isKeyword ? 900 : style.fontWeight,
      fontFamily: style.fontFamily,
      color,
      textShadow,
      transform: `scale(${wordScale.toFixed(4)})`,
      opacity: wordOpacity,
      textTransform: style.textTransform,
      lineHeight: style.lineHeight,
      willChange: "transform, opacity, color",
      textAlign: "center",
      whiteSpace: "nowrap",
      WebkitTextStroke: "0px transparent",
      // In cascade mode, keywords get extra letter spacing for impact
      letterSpacing: useCascadeLayout && isKeyword ? "0.02em" : "normal",
    };

    // ── Text stroke / outline ────────────────────────────────────────────
    if (style.outlineOnly && style.textStroke) {
      wordStyle.WebkitTextStroke = `${style.textStroke.width}px ${style.textStroke.color}`;
      wordStyle.WebkitTextFillColor = "transparent";
      delete wordStyle.color;
    } else if (style.textStroke) {
      wordStyle.WebkitTextStroke = `${style.textStroke.width}px ${style.textStroke.color}`;
    } else {
      wordStyle.WebkitTextStroke = "2px rgba(0,0,0,0.8)";
    }

    // ── Gradient text ────────────────────────────────────────────────────
    if (
      style.gradientColors &&
      style.gradientColors.length >= 2 &&
      !style.outlineOnly
    ) {
      wordStyle.background = `linear-gradient(${style.gradientDirection || "to right"}, ${style.gradientColors.join(", ")})`;
      wordStyle.WebkitBackgroundClip = "text";
      wordStyle.WebkitTextFillColor = "transparent";
      delete wordStyle.color;
    }

    const element = (
      <span key={ti} style={wordStyle}>
        {display}
      </span>
    );

    if (useCascadeLayout) {
      if (isKeyword) {
        keywordElements.push(element);
      } else {
        contextElements.push(element);
      }
    }
    allElements.push(element);
  });

  // ── Container / pill background ──────────────────────────────────────────
  const bgShape =
    style.backgroundShape || (style.pillEnabled ? "pill" : "none");
  let containerBg: React.CSSProperties = {};
  if (bgShape === "pill" && style.pillEnabled) {
    containerBg = {
      background: style.pillColor,
      borderRadius: style.pillRadius,
      padding: `${Math.round(baseFontSize * 0.1)}px ${Math.round(baseFontSize * 0.2)}px`,
    };
  } else if (bgShape === "box") {
    containerBg = {
      background: style.pillColor,
      padding: `${Math.round(baseFontSize * 0.1)}px ${Math.round(baseFontSize * 0.2)}px`,
    };
  }

  // ── Cascade vs flat layout ───────────────────────────────────────────────
  // Cascade: two rows (context words on top, keywords on bottom)
  // Flat: all words stacked vertically (one word per line)
  const innerContent = useCascadeLayout ? (
    <>
      {/* Context line (smaller, top) */}
      {contextElements.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "baseline",
            gap: "8px",
          }}
        >
          {contextElements}
        </div>
      )}
      {/* Keyword line (larger, bottom) — the emphasis row */}
      {keywordElements.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "baseline",
            gap: "10px",
          }}
        >
          {keywordElements}
        </div>
      )}
    </>
  ) : (
    // Flat layout: words flow horizontally with wrapping
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "baseline",
        gap: "8px",
      }}
    >
      {allElements}
    </div>
  );

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: `${style.yPercent}%`,
        transform: `translateY(-50%) scale(${pageScale.toFixed(4)}) translate(${swayX.toFixed(2)}px, ${(pageTranslateY + swayY).toFixed(2)}px)`,
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
          gap: useCascadeLayout ? "6px" : "4px",
        }}
      >
        {innerContent}
      </div>
    </div>
  );
};
