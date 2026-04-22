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
import type { LetterboxPushProps } from "../types";

/**
 * Letterbox Push — background shows the video at normal scale,
 * a zoomed-in view pushes in from the center framed by the original
 * footage visible in the letterbox bars. Cinematic aspect ratio
 * narrows as the zoom deepens.
 */
export const LetterboxPush: React.FC<LetterboxPushProps> = ({
  src,
  events,
  style,
  maxBarHeight = 0.12,
  startFrom,
  playbackRate = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, height } = useVideoConfig();

  let scale = 1;
  let barProgress = 0;
  let originX = 0.5;
  let originY = 0.5;

  if (events.length === 0) {
    const rampIn = Math.round(durationInFrames * 0.35);
    const holdEnd = Math.round(durationInFrames * 0.6);

    if (frame < rampIn) {
      barProgress = interpolate(frame, [0, rampIn], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    } else if (frame < holdEnd) {
      barProgress = 1;
    } else {
      barProgress = interpolate(frame, [holdEnd, durationInFrames], [1, 0], {
        easing: Easing.in(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
    scale = 1 + 0.2 * barProgress;
  } else {
    for (const event of events) {
      const targetScale = event.scale ?? 1.2;
      const eventStart = msToFrames(event.startMs, fps);
      const eventEnd = msToFrames(event.startMs + event.durationMs, fps);

      if (frame < eventStart || frame > eventEnd) continue;

      const eventDuration = eventEnd - eventStart;
      const rampIn = eventStart + Math.round(eventDuration * 0.35);
      const holdEnd = eventStart + Math.round(eventDuration * 0.6);

      if (frame < rampIn) {
        barProgress = interpolate(frame, [eventStart, rampIn], [0, 1], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      } else if (frame < holdEnd) {
        barProgress = 1;
      } else {
        barProgress = interpolate(frame, [holdEnd, eventEnd], [1, 0], {
          easing: Easing.in(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      }

      scale = 1 + (targetScale - 1) * barProgress;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.5;
    }
  }

  const barHeight = maxBarHeight * height * barProgress;

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
        }}
      />

      <AbsoluteFill
        style={{
          backgroundColor: `rgba(0,0,0,${0.35 * barProgress})`,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: barHeight,
          left: 0,
          right: 0,
          bottom: barHeight,
          overflow: "hidden",
        }}
      >
        <OffthreadVideo
          src={src}
          startFrom={startFrom}
          playbackRate={playbackRate}
          style={{
            width: "100%",
            height: `${height}px`,
            objectFit: "cover",
            position: "absolute",
            top: -barHeight,
            left: 0,
            transform: `scale(${scale})`,
            transformOrigin: `${originX * 100}% ${originY * 100}%`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
