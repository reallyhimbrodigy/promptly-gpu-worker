import React, { useMemo } from "react";
import { AbsoluteFill } from "remotion";
import { CaptionOverlay } from "./CaptionOverlay";
import { EffectsLayer } from "./effects";
import { FontLoader } from "./FontLoader";
import { generateEffects } from "./effects/presets";
import type { OverlayInput, CaptionInput, VisualEffect } from "./types";

/**
 * Master overlay composition — renders ALL transparent overlays in one pass:
 * 1. Visual effects (light leaks, transitions, particles, glitch, etc.)
 * 2. Captions (animated word groups with keyword emphasis)
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

  return (
    <FontLoader>
      <AbsoluteFill style={{ backgroundColor: "transparent" }}>
        {/* Effects layer renders BELOW captions */}
        <EffectsLayer effects={allEffects} />
        {/* Captions render on top */}
        {hasCaptions && <CaptionOverlay input={captionInput} />}
      </AbsoluteFill>
    </FontLoader>
  );
};
