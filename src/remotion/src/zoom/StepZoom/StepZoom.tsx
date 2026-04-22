import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  OffthreadVideo,
} from "remotion";
import { msToFrames } from "../shared/timing";
import type { StepZoomProps } from "../types";

export const StepZoom: React.FC<StepZoomProps> = ({
  src,
  events,
  style,
  startFrom,
  playbackRate = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  for (const event of events) {
    const eventStart = msToFrames(event.startMs, fps);
    const eventEnd = msToFrames(event.startMs + event.durationMs, fps);

    if (frame >= eventStart && frame < eventEnd) {
      scale = event.scale ?? 1.3;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.5;
      break;
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
