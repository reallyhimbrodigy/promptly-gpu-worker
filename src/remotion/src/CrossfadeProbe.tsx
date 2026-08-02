import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, staticFile } from "remotion";
import { CrossfadeZoom } from "./transitions/CrossfadeZoom/CrossfadeZoom";

/**
 * CrossfadeProbe — proves the SURVIVING-LAYER degrade paints real frames.
 * Not production. Drives the REAL CrossfadeZoom, ramping progress 0->1 across
 * the composition. clipA/clipB are distinct SOLID COLOURS so the measured mean
 * channel says WHICH layer is on screen, and a black frame is unmistakable.
 */
export const CrossfadeProbe: React.FC<{ clipA: string; clipB: string }> = ({
  clipA,
  clipB,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const progress = durationInFrames > 1 ? frame / (durationInFrames - 1) : 1;
  const resolve = (s: string) => (/^[a-z]+:/i.test(s) ? s : staticFile(s));
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <CrossfadeZoom
        clipA={resolve(clipA)}
        clipB={resolve(clipB)}
        progress={progress}
      />
    </AbsoluteFill>
  );
};
