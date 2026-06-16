import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";

/**
 * NewspaperWipeOverlay — DECORATION-ONLY variant of NewspaperWipe.
 *
 * Decoupled from clipA / clipB. Renders ONLY the torn-newspaper paper that
 * slams up from below, fully covers the canvas, holds briefly, and rushes
 * off the top — on a TRANSPARENT background. Whatever the underlying
 * composition shows during the overlay's frame range plays through
 * unaltered everywhere the paper isn't covering.
 *
 * Used by OverlayCutEffect to put the wipe ON TOP of a continuous hard cut
 * at a tight boundary, instead of inside a TransitionSeries slot that
 * consumes handle frames.
 *
 * The y-translate keyframes are LIFTED VERBATIM from
 * transitions/NewspaperWipe/NewspaperWipe.tsx — stepped values that
 * preserve the punchy, staccato feel. Linear interpolation would flatten
 * the rhythm into a soft slide.
 *
 * Peak coverage (y=0) is held across progress [5/13, 7/13] ≈ [0.385, 0.538]
 * — symmetric around the cut frame at progress 0.5. The cut is masked by
 * the paper for that ~2-frame hold window at the production 11-frame
 * duration (180ms).
 */
const PROGRESS_KEYFRAMES: [number, number][] = [
  [0.0, 1920], // off-screen below
  [2 / 13, 1000],
  [4 / 13, 300],
  [5 / 13, 0], // BAM — fully covers the frame
  [7 / 13, 0], // hold
  [9 / 13, -400],
  [11 / 13, -1100],
  [1.0, -1920], // gone off top
];

export interface NewspaperWipeOverlayProps {
  progress: number;
  /** Asset basename in src/remotion/public/. Defaults to the production
   *  asset used by the original handle-based NewspaperWipe. */
  assetPath?: string;
}

export const NewspaperWipeOverlay: React.FC<NewspaperWipeOverlayProps> = ({
  progress,
  assetPath = "torn-newspaper.png",
}) => {
  let y = 1920;
  for (let i = 0; i < PROGRESS_KEYFRAMES.length - 1; i++) {
    const [p1, y1] = PROGRESS_KEYFRAMES[i];
    const [p2] = PROGRESS_KEYFRAMES[i + 1];
    if (progress >= p1 && progress < p2) {
      y = y1;
      break;
    }
  }
  if (progress >= 1) {
    y = PROGRESS_KEYFRAMES[PROGRESS_KEYFRAMES.length - 1][1];
  }

  // Off-screen entirely → render nothing (zero DOM cost on the wipe-in /
  // wipe-out tails outside the visible part of the keyframe range).
  if (y >= 1920 || y <= -1920) {
    return null;
  }

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <Img
        src={staticFile(assetPath)}
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `translateY(${y}px)`,
          pointerEvents: "none",
        }}
      />
    </AbsoluteFill>
  );
};
