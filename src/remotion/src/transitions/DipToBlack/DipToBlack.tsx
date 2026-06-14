import React from "react";
import { AbsoluteFill, interpolate, Easing, OffthreadVideo } from "remotion";
import type { DipToBlackProps } from "../types";

export const DIP_TO_BLACK_PEAK_PROGRESS = 0.5;

/**
 * DipToBlack — clean, fast dip-through-black between two clips.
 *
 * The transition reads as ONE thing: a quick blink of black between
 * two cuts. No leak, no swirl, no theme. The dip is what hides the
 * cut; everything else is invisible.
 *
 *   0   → 0.5  clip A fades to black (cosine-out: most of the fade
 *              happens in the last third — the screen LOOKS like A
 *              right up until the last beat, then snaps dark)
 *   0.5        full black (one frame at peak)
 *   0.5 → 1    clip B fades in from black (cosine-in mirror — opens
 *              quickly off black, settles into B's full content)
 *
 * Designed for ~350ms slot duration. Faster than that reads as a
 * hard flicker; slower than ~500ms starts to "eat a beat" between
 * the surrounding speech.
 */
export const DipToBlack: React.FC<DipToBlackProps> = ({
  clipA,
  clipB,
  progress,
  style,
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
}) => {
  const aOpacity = interpolate(
    progress,
    [0, DIP_TO_BLACK_PEAK_PROGRESS],
    [1, 0],
    {
      easing: Easing.bezier(0.55, 0, 0.85, 0.2),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  const bOpacity = interpolate(
    progress,
    [DIP_TO_BLACK_PEAK_PROGRESS, 1],
    [0, 1],
    {
      easing: Easing.bezier(0.15, 0.8, 0.45, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      {aOpacity > 0.01 && (
        <AbsoluteFill style={{ opacity: aOpacity, willChange: "opacity" }}>
          <OffthreadVideo
            src={clipA}
            startFrom={startFromA}
            playbackRate={playbackRateA}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}
      {bOpacity > 0.01 && (
        <AbsoluteFill style={{ opacity: bOpacity, willChange: "opacity" }}>
          <OffthreadVideo
            src={clipB}
            startFrom={startFromB}
            playbackRate={playbackRateB}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
