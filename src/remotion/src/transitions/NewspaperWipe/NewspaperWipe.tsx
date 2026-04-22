import React from "react";
import { AbsoluteFill, Img, OffthreadVideo, staticFile } from "remotion";
import type { NewspaperWipeProps } from "../types";

export const NEWSPAPER_WIPE_PEAK_PROGRESS = 0.5;

// Stepped keyframes mapped to normalized progress 0→1. Values match the
// original PaperII newspaper-transition timing (13-frame punch, 2-frame
// hold at peak, 13-frame exit) scaled to progress units. Using stepped
// snapping preserves the characteristic punchy, staccato feel — smooth
// interpolation would flatten it into "soft slide."
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

/**
 * NewspaperWipe — transition where a torn newspaper slams up from below,
 * fully covers the frame, holds briefly, then rushes off the top. The cut
 * from clipA to clipB happens at peak coverage (progress 0.5). Stepped
 * keyframes preserve the punchy PaperII rhythm — no smooth easing.
 */
export const NewspaperWipe: React.FC<NewspaperWipeProps> = ({
  clipA,
  clipB,
  progress,
  style,
  assetPath = "torn-newspaper.png",
  startFromA,
  startFromB,
  playbackRateA = 1,
  playbackRateB = 1,
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

  const showB = progress >= NEWSPAPER_WIPE_PEAK_PROGRESS;
  const activeClip = showB ? clipB : clipA;

  return (
    <AbsoluteFill style={{ overflow: "hidden", background: "#000", ...style }}>
      <AbsoluteFill>
        <OffthreadVideo
          src={activeClip}
          startFrom={showB ? startFromB : startFromA}
          playbackRate={showB ? playbackRateB : playbackRateA}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </AbsoluteFill>
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
        }}
      />
    </AbsoluteFill>
  );
};
