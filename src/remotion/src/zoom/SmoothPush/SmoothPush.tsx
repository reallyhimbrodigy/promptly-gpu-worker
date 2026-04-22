import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  OffthreadVideo,
} from "remotion";
import { msToFrames } from "../shared/timing";
import type { SmoothPushProps } from "../types";

/**
 * Smooth Push — slow, deliberate forward zoom with refined easing.
 * Starts imperceptibly, accelerates slightly mid-move, decelerates to a stop.
 * The most essential zoom in professional editing.
 */
export const SmoothPush: React.FC<SmoothPushProps> = ({
  src,
  events,
  style,
  startFrom,
  playbackRate = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  if (events.length === 0) {
    const rampIn = Math.round(durationInFrames * 0.35);
    const holdEnd = Math.round(durationInFrames * 0.6);

    if (frame < rampIn) {
      scale = 1 + 0.18 * interpolate(frame, [0, rampIn], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    } else if (frame < holdEnd) {
      scale = 1.18;
    } else {
      scale = 1 + 0.18 * interpolate(frame, [holdEnd, durationInFrames], [1, 0], {
        easing: Easing.in(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
  } else {
    for (const event of events) {
      const targetScale = event.scale ?? 1.2;
      const eventStart = msToFrames(event.startMs, fps);
      const eventEnd = msToFrames(event.startMs + event.durationMs, fps);

      if (frame < eventStart || frame > eventEnd) continue;

      const eventDuration = eventEnd - eventStart;
      const rampIn = eventStart + Math.round(eventDuration * 0.35);
      const holdEnd = eventStart + Math.round(eventDuration * 0.6);

      let progress: number;
      if (frame < rampIn) {
        progress = interpolate(frame, [eventStart, rampIn], [0, 1], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      } else if (frame < holdEnd) {
        progress = 1;
      } else {
        progress = interpolate(frame, [holdEnd, eventEnd], [1, 0], {
          easing: Easing.in(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      }

      scale = 1 + (targetScale - 1) * progress;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.5;
    }
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      <OffthreadVideo
        src={src}
        startFrom={startFrom}
        playbackRate={playbackRate}
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
