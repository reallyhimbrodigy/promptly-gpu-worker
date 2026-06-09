import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { Video } from "@remotion/media";
import { msToFrames } from "../shared/timing";
import type { StageZoomProps } from "../types";

/**
 * Stage Zoom — zooms in two stages with a pause between them.
 * First push settles, holds, then a second deeper push commits further.
 * Smooth out at the end. Like a camera operator finding focus
 * then pushing in for emphasis.
 *
 * Timeline: ramp1 → hold1 → ramp2 → hold2 → ramp out
 */
export const StageZoom: React.FC<StageZoomProps> = ({
  src,
  events,
  style,
  firstStage = 1.15,
  secondStage = 1.35,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  const computeStageProgress = (
    currentFrame: number,
    start: number,
    duration: number,
    s1: number,
    s2: number
  ): number => {
    // 0-20%: ramp to first stage
    // 20-40%: hold first stage
    // 40-65%: ramp to second stage
    // 65-80%: hold second stage
    // 80-100%: ramp out
    const p1End = start + Math.round(duration * 0.2);
    const h1End = start + Math.round(duration * 0.4);
    const p2End = start + Math.round(duration * 0.65);
    const h2End = start + Math.round(duration * 0.8);
    const end = start + duration;

    if (currentFrame < p1End) {
      // Ramp to first stage
      const t = interpolate(currentFrame, [start, p1End], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      return 1 + (s1 - 1) * t;
    }
    if (currentFrame < h1End) {
      // Hold first stage
      return s1;
    }
    if (currentFrame < p2End) {
      // Ramp to second stage
      const t = interpolate(currentFrame, [h1End, p2End], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      return s1 + (s2 - s1) * t;
    }
    if (currentFrame < h2End) {
      // Hold second stage
      return s2;
    }
    // Ramp out
    const t = interpolate(currentFrame, [h2End, end], [0, 1], {
      easing: Easing.in(Easing.cubic),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return s2 + (1 - s2) * t;
  };

  if (events.length === 0) {
    scale = computeStageProgress(frame, 0, durationInFrames, firstStage, secondStage);
  } else {
    for (const event of events) {
      const eventStart = msToFrames(event.startMs, fps);
      const eventEnd = msToFrames(event.startMs + event.durationMs, fps);
      if (frame < eventStart || frame > eventEnd) continue;

      const s1 = firstStage;
      const s2 = event.scale ?? secondStage;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.5;

      scale = computeStageProgress(frame, eventStart, eventEnd - eventStart, s1, s2);
    }
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      <Video
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />
    </AbsoluteFill>
  );
};
