import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ZoomSource } from "../shared/ZoomSource";
import { msToFrames, msToFramesFloor } from "../shared/timing";
import type { StepZoomProps } from "../types";

/**
 * Step Zoom — instant jump cuts between zoom levels. No smooth animation,
 * no easing. Clean, precise editorial reframes that happen on the beat.
 * Like cutting between a wide and tight shot of the same camera.
 */
export const StepZoom: React.FC<StepZoomProps> = ({
  frames,
  src,
  events,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  for (const event of events) {
    const eventStart = msToFramesFloor(event.startMs, fps);
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
      <ZoomSource
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
       frames={frames}/>
    </AbsoluteFill>
  );
};
