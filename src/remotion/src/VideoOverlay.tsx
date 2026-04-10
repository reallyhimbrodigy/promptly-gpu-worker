import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { CaptionOverlay } from "./CaptionOverlay";
import { EffectsLayer } from "./effects";
import { FontLoader } from "./FontLoader";
import { generateEffects } from "./effects/presets";
import type { OverlayInput, CaptionInput, VisualEffect, TextOverlay } from "./types";

/**
 * Renders a single text overlay (title/callout/CTA) with fade in/out.
 * Rendered as part of the Remotion PNG sequence so it's continuous across
 * segment boundaries — no flashing.
 */
const TextOverlayElement: React.FC<{
  overlay: TextOverlay;
  fps: number;
  width: number;
  height: number;
}> = ({ overlay, fps, width, height }) => {
  const frame = useCurrentFrame();
  const currentTime = frame / fps;

  if (currentTime < overlay.start || currentTime > overlay.end) return null;

  // No fade — text appears and disappears instantly. Fades on short
  // hook sub-clips caused visible flashing at segment boundaries.
  const opacity = 1;

  const isTitle = overlay.style === "title";
  const isCta = overlay.style === "cta";
  const textLen = overlay.text.length;
  const baseFontSize = isTitle ? 84 : isCta ? 72 : 60;
  const fontSize =
    textLen <= 18 ? baseFontSize :
    textLen <= 25 ? Math.round(baseFontSize * 0.85) :
    textLen <= 35 ? Math.round(baseFontSize * 0.70) :
    Math.round(baseFontSize * 0.60);

  const yPercent =
    overlay.position === "bottom" ? 75 :
    overlay.position === "center" ? 50 : 10;

  return (
    <div
      style={{
        position: "absolute",
        top: `${yPercent}%`,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity,
        pointerEvents: "none",
      }}
    >
      <span
        style={{
          fontFamily: "Montserrat, sans-serif",
          fontWeight: 900,
          fontSize,
          color: "white",
          textAlign: "center",
          textShadow: "2px 2px 6px rgba(0,0,0,0.6), -1px -1px 3px rgba(0,0,0,0.3)",
          WebkitTextStroke: "1px rgba(0,0,0,0.3)",
          maxWidth: "90%",
          lineHeight: 1.2,
        }}
      >
        {overlay.text}
      </span>
    </div>
  );
};

/**
 * Master overlay composition — renders ALL transparent overlays in one pass:
 * 1. Visual effects (light leaks, transitions, particles, glitch, etc.)
 * 2. Text overlays (title, callout, CTA — continuous across segments)
 * 3. Captions (animated word groups with keyword emphasis)
 *
 * Everything is rendered as a single transparent ProRes 4444 MOV.
 * FFmpeg composites this one file onto the edited video.
 */
export const VideoOverlay: React.FC<{
  input: OverlayInput;
}> = ({ input }) => {
  // Auto-generate effects from vibe + cuts + emphasis moments (memoized — static per video)
  const allEffects = useMemo<VisualEffect[]>(() => {
    const auto = generateEffects(input);
    return [...auto, ...(input.effects || [])];
  }, [input]);

  // Build caption input from overlay input
  const captionInput: CaptionInput = {
    words: input.words,
    style: input.captionStyle,
    width: input.width,
    height: input.height,
    fps: input.fps,
    durationInFrames: input.durationInFrames,
    keywords: input.keywords,
    fontDir: input.fontDir,
  };

  const hasCaptions = input.words.length > 0 && input.captionStyle !== "none";
  const textOverlays = input.textOverlays || [];

  return (
    <FontLoader>
      <AbsoluteFill style={{ backgroundColor: "transparent" }}>
        {/* Effects layer renders BELOW captions */}
        <EffectsLayer effects={allEffects} />
        {/* Text overlays render above effects, below captions */}
        {textOverlays.map((ov, i) => (
          <TextOverlayElement
            key={i}
            overlay={ov}
            fps={input.fps}
            width={input.width}
            height={input.height}
          />
        ))}
        {/* Captions render on top */}
        {hasCaptions && <CaptionOverlay input={captionInput} />}
      </AbsoluteFill>
    </FontLoader>
  );
};
