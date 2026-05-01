import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Sequence,
  spring,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import type { TikTokToken, TikTokPage } from "../shared/types";
import type { GlitchHighlightProps, GlitchColorPreset } from "./types";
import { GLITCH_PRESETS } from "./types";
import { CAPTION_FONTS } from "../shared/fonts";
import { msToFrames } from "../shared/timing";
import { getCaptionPositionStyle } from "../shared/captionPosition";

function normalizeWord(text: string): string {
  return text.replace(/[^a-zA-Z0-9]/g, "").toLowerCase();
}

function hash(frame: number, seed: number): number {
  const x = Math.sin(frame * 127.1 + seed * 311.7) * 43758.5453;
  return x - Math.floor(x);
}

const FONT = CAPTION_FONTS.montserrat;
const FONT_SIZE = 80;
const FONT_WEIGHT = 900;

const GLITCH_FONT = CAPTION_FONTS.teko;
const GLITCH_FONT_SIZE = Math.round(FONT_SIZE * 1.6);
const GLITCH_FONT_WEIGHT = 700;
const GLITCH_LETTER_SPACING = "0.05em";

/* ─── Normal Word ─── */

const NormalWord: React.FC<{
  text: string;
  entryProgress: number;
  isActive: boolean;
  isPast: boolean;
}> = ({ text, entryProgress, isActive, isPast }) => {
  const opacity = interpolate(entryProgress, [0, 0.3], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(entryProgress, [0, 1], [18, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = isActive ? 1.08 : 1;
  const activeGlow = isActive
    ? "0 0 12px rgba(56,189,248,0.35), 0 0 30px rgba(56,189,248,0.15)"
    : "";

  return (
    <span
      style={{
        display: "inline-block",
        fontFamily: FONT,
        fontSize: FONT_SIZE,
        fontWeight: FONT_WEIGHT,
        color: "#FFFFFF",
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        textShadow: `0 2px 12px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.5)${activeGlow ? `, ${activeGlow}` : ""}`,
        transform: `translateY(${y}px) scale(${scale})`,
        transformOrigin: "center bottom",
        opacity,
        whiteSpace: "nowrap",
        lineHeight: 1.2,
      }}
    >
      {text}
    </span>
  );
};

/* ─── Glitch Word ─── */

const GlitchWord: React.FC<{
  text: string;
  color: string;
  glitchProgress: number;
  localFrame: number;
  entryProgress: number;
}> = ({ text, color, glitchProgress, localFrame, entryProgress }) => {
  const opacity = interpolate(entryProgress, [0, 0.15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Two-phase: hard glitch burst (0→0.4), then fast settle (0.4→1)
  const intensity = (() => {
    if (glitchProgress < 0.08) return interpolate(glitchProgress, [0, 0.08], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    if (glitchProgress < 0.35) {
      const burst = hash(localFrame, 99) > 0.3 ? 1 : 0.2;
      return burst * interpolate(glitchProgress, [0.08, 0.35], [1, 0.6], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    }
    if (glitchProgress < 0.55) return interpolate(glitchProgress, [0.35, 0.55], [0.6, 0.15], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return interpolate(glitchProgress, [0.55, 0.8], [0.15, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  })();

  const r1 = hash(localFrame, 1);
  const r2 = hash(localFrame, 2);
  const r3 = hash(localFrame, 3);
  const r4 = hash(localFrame, 4);

  // RGB chromatic aberration — full red/green/blue split
  const splitX = intensity * (r1 - 0.5) * 32;
  const splitY = intensity * (r2 - 0.5) * 8;

  // Horizontal slice displacement (3 slices)
  const slices = [0, 1, 2].map((i) => {
    const sliceH = 100 / 3;
    const top = i * sliceH;
    const bottom = 100 - (i + 1) * sliceH;
    const shift = intensity * (hash(localFrame, 10 + i) - 0.5) * 40;
    return { top, bottom: Math.max(bottom, 0), shift };
  });

  // Flicker
  const flickerVal = hash(localFrame, 7);
  const flicker = intensity > 0.1 ? (flickerVal > 0.75 ? 0.4 : flickerVal > 0.25 ? 1 : 0.7) : 1;

  // Skew
  const skew = intensity * (r3 - 0.5) * 16;
  const scaleX = 1 + intensity * (r4 - 0.5) * 0.12;

  // White flash on entry
  const isFlash = localFrame >= 0 && localFrame <= 1;
  const mainColor = isFlash ? "#FFFFFF" : color;

  // Settled glow — persistent after glitch ends
  const glowPulse = 1 + Math.sin(localFrame * 0.15) * 0.15;
  const settledGlow = `0 0 ${12 * glowPulse}px ${color}, 0 0 ${28 * glowPulse}px ${color}80, 0 0 ${50 * glowPulse}px ${color}30`;
  const activeGlow = `0 0 ${interpolate(intensity, [0, 1], [8, 35], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px ${color}90, 0 0 ${interpolate(intensity, [0, 1], [16, 60], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px ${color}40`;
  const glowShadow = intensity > 0.05 ? activeGlow : settledGlow;

  const baseFont: React.CSSProperties = {
    fontFamily: GLITCH_FONT,
    fontSize: GLITCH_FONT_SIZE,
    fontWeight: GLITCH_FONT_WEIGHT,
    textTransform: "uppercase",
    letterSpacing: GLITCH_LETTER_SPACING,
    whiteSpace: "nowrap",
    lineHeight: 1.1,
    position: "absolute",
    top: 0,
    left: 0,
    width: "100%",
  };

  return (
    <span
      style={{
        display: "inline-block",
        position: "relative",
        opacity: opacity * flicker,
        transform: `scaleX(${scaleX}) skewX(${skew}deg)`,
        transformOrigin: "center center",
      }}
    >
      {/* Invisible sizer */}
      <span
        style={{
          fontFamily: GLITCH_FONT,
          fontSize: GLITCH_FONT_SIZE,
          fontWeight: GLITCH_FONT_WEIGHT,
          textTransform: "uppercase",
          letterSpacing: GLITCH_LETTER_SPACING,
          visibility: "hidden",
          whiteSpace: "nowrap",
          lineHeight: 1.1,
        }}
      >
        {text}
      </span>

      {/* RGB chromatic aberration */}
      {intensity > 0.08 && (
        <>
          <span
            style={{
              ...baseFont,
              color: "#FF0040",
              opacity: intensity * 0.65,
              transform: `translate(${-splitX}px, ${-splitY * 0.5}px)`,
              clipPath: `inset(0% -200px ${40 + hash(localFrame, 5) * 20}% -200px)`,
              mixBlendMode: "screen",
            }}
          >
            {text}
          </span>
          <span
            style={{
              ...baseFont,
              color: "#00FF66",
              opacity: intensity * 0.5,
              transform: `translate(${splitX * 0.7}px, ${splitY}px)`,
              clipPath: `inset(${30 - hash(localFrame, 6) * 15}% -200px ${30 - hash(localFrame, 8) * 15}% -200px)`,
              mixBlendMode: "screen",
            }}
          >
            {text}
          </span>
          <span
            style={{
              ...baseFont,
              color: "#0066FF",
              opacity: intensity * 0.6,
              transform: `translate(${splitX * 0.4}px, ${-splitY * 0.8}px)`,
              clipPath: `inset(${50 - hash(localFrame, 9) * 20}% -200px 0% -200px)`,
              mixBlendMode: "screen",
            }}
          >
            {text}
          </span>
        </>
      )}

      {/* Main text — sliced during glitch */}
      {intensity > 0.05 ? (
        slices.map((slice, i) => (
          <span
            key={i}
            style={{
              ...baseFont,
              color: mainColor,
              textShadow: `0 2px 8px rgba(0,0,0,0.6), ${glowShadow}`,
              transform: `translateX(${slice.shift}px)`,
              clipPath: `inset(${slice.top}% -200px ${slice.bottom}% -200px)`,
            }}
          >
            {text}
          </span>
        ))
      ) : (
        <span
          style={{
            ...baseFont,
            color,
            textShadow: `0 2px 8px rgba(0,0,0,0.6), ${glowShadow}`,
          }}
        >
          {text}
        </span>
      )}

      {/* Scanlines during glitch */}
      {intensity > 0.08 && (
        <span
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            background: `repeating-linear-gradient(0deg, transparent 0px, transparent 3px, rgba(0,0,0,${intensity * 0.3}) 3px, rgba(0,0,0,${intensity * 0.3}) 5px)`,
            pointerEvents: "none",
          }}
        />
      )}
    </span>
  );
};

/* ─── Word Wrapper ─── */

const AnimatedWord: React.FC<{
  token: TikTokToken;
  globalIndex: number;
  pageStartMs: number;
  currentTimeMs: number;
  isGlitch: boolean;
  color: string;
  staggerDelayFrames: number;
  glitchDurationFrames: number;
}> = ({
  token,
  globalIndex,
  pageStartMs,
  currentTimeMs,
  isGlitch,
  color,
  staggerDelayFrames,
  glitchDurationFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const tokenEntryFrame = msToFrames(token.fromMs - pageStartMs, fps);
  const delayedEntry = tokenEntryFrame + globalIndex * staggerDelayFrames;
  const localFrame = frame - delayedEntry;

  const entryProgress = spring({
    fps,
    frame: localFrame,
    config: { mass: 0.35, damping: 14, stiffness: 200 },
  });

  if (isGlitch) {
    const glitchProgress = interpolate(
      localFrame,
      [0, glitchDurationFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );

    return (
      <GlitchWord
        text={token.text}
        color={color}
        glitchProgress={glitchProgress}
        localFrame={localFrame}
        entryProgress={entryProgress}
      />
    );
  }

  const isActive = currentTimeMs >= token.fromMs && currentTimeMs < token.toMs;
  const isPast = currentTimeMs >= token.toMs;

  return (
    <NormalWord
      text={token.text}
      entryProgress={entryProgress}
      isActive={isActive}
      isPast={isPast}
    />
  );
};

/* ─── Page ─── */

const GlitchPage: React.FC<{
  page: TikTokPage;
  highlightMap: Map<string, GlitchColorPreset>;
  staggerDelayFrames: number;
  glitchDurationFrames: number;
}> = ({ page, highlightMap, staggerDelayFrames, glitchDurationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTimeMs = page.startMs + (frame / fps) * 1000;

  // Subtle screen shake when a glitch word is active
  const activeGlitch = page.tokens.find((t) => {
    if (!highlightMap.has(normalizeWord(t.text))) return false;
    return currentTimeMs >= t.fromMs && currentTimeMs < t.fromMs + (glitchDurationFrames / fps) * 1000 * 0.4;
  });

  let shakeX = 0;
  let shakeY = 0;
  if (activeGlitch) {
    const elapsed = currentTimeMs - activeGlitch.fromMs;
    const fade = interpolate(elapsed, [0, 250], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    shakeX = (hash(frame, 20) - 0.5) * 10 * fade;
    shakeY = (hash(frame, 21) - 0.5) * 6 * fade;
  }

  let globalIndex = 0;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "baseline",
        gap: "0 14px",
        transform: `translate(${shakeX}px, ${shakeY}px)`,
      }}
    >
      {page.tokens.map((token) => {
        const norm = normalizeWord(token.text);
        const match = highlightMap.get(norm);
        const idx = globalIndex;
        globalIndex++;

        return (
          <AnimatedWord
            key={`w-${idx}`}
            token={token}
            globalIndex={idx}
            pageStartMs={page.startMs}
            currentTimeMs={currentTimeMs}
            isGlitch={!!match}
            color={match?.color ?? "#FFFFFF"}
            staggerDelayFrames={staggerDelayFrames}
            glitchDurationFrames={glitchDurationFrames}
          />
        );
      })}
    </div>
  );
};

/* ─── Main ─── */

export const GlitchHighlight: React.FC<GlitchHighlightProps> = ({
  pages,
  highlightWords = [],
  colorPreset = "blue",
  position = "center",
  staggerDelayFrames = 1,
  glitchDurationFrames = 14,
}) => {
  const frame = useCurrentFrame();
  const { fps, width } = useVideoConfig();
  const maxWidth = width * 0.85;

  const defaultPreset = GLITCH_PRESETS[colorPreset] ?? GLITCH_PRESETS.blue;

  const highlightMap = useMemo(() => {
    const map = new Map<string, GlitchColorPreset>();
    for (const hw of highlightWords) {
      const preset = GLITCH_PRESETS[hw.preset ?? colorPreset] ?? defaultPreset;
      map.set(normalizeWord(hw.text), preset);
    }
    return map;
  }, [highlightWords, colorPreset, defaultPreset]);

  const positionStyle = getCaptionPositionStyle(position as "top" | "center" | "bottom");

  return (
    <AbsoluteFill>
      {pages.map((page, pageIndex) => {
        const startFrame = msToFrames(page.startMs, fps);
        const durationFrames = msToFrames(page.durationMs, fps);
        if (durationFrames <= 0) return null;

        const endFrame = startFrame + durationFrames;
        // 3 frames (~50ms at 60fps) — tight page-boundary fade so captions
        // land ON the spoken word rather than trailing it.
        const fadeFrames = 3;
        const fadeIn = interpolate(
          frame,
          [startFrame, startFrame + fadeFrames],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        const fadeOut = interpolate(
          frame,
          [endFrame - fadeFrames, endFrame],
          [1, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
        const pageOpacity = fadeIn * fadeOut;

        return (
          <Sequence
            key={pageIndex}
            from={startFrame}
            durationInFrames={durationFrames}
            premountFor={10}
            name={page.tokens.map((t) => t.text).join(" ")}
          >
            <AbsoluteFill
              style={{ display: "flex", alignItems: "center", opacity: pageOpacity, ...positionStyle }}
            >
              <div style={{ maxWidth, width: "100%" }}>
                <GlitchPage
                  page={page}
                  highlightMap={highlightMap}
                  staggerDelayFrames={staggerDelayFrames}
                  glitchDurationFrames={glitchDurationFrames}
                />
              </div>
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
