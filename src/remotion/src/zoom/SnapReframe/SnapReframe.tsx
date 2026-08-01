import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  spring,
} from "remotion";
import { Video } from "@remotion/media";
import { msToFrames, msToFramesFloor } from "../shared/timing";
import { useResprungZooms } from "../shared/resprung-flag";
import type { SnapReframeProps } from "../types";

/**
 * Snap Reframe — fast, precise zoom to a tighter composition.
 * Critically-damped spring: no bounce, no overshoot. Just a quick,
 * clean reframe like a professional camera operator pulling focus.
 */
export const SnapReframe: React.FC<SnapReframeProps> = ({
  src,
  events,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const resprung = useResprungZooms();
  // Re-sprung (Zac 2026-07-31): damping 28→22 (ζ 1.12→0.881), clamp OFF, mass
  // untouched. time-to-peak ≈ 9.6 frames @30fps (above the 8-frame floor).
  const springConfig = resprung
    ? { damping: 22, mass: 0.6, stiffness: 260 }
    : { damping: 28, mass: 0.6, stiffness: 260, overshootClamping: true };

  let scale = 1;
  let originX = 0.5;
  let originY = 0.5;

  for (const event of events) {
    const targetScale = event.scale ?? 1.3;
    const eventStart = msToFramesFloor(event.startMs, fps);
    const eventEnd = msToFrames(event.startMs + event.durationMs, fps);

    if (frame < eventStart) continue;

    const zoomIn = spring({
      frame: frame - eventStart,
      fps,
      config: springConfig,
    });

    const zoomOut =
      frame >= eventEnd
        ? spring({
            frame: frame - eventEnd,
            fps,
            config: springConfig,
          })
        : 0;

    const eventScale = 1 + (targetScale - 1) * zoomIn * (1 - zoomOut);

    if (eventScale > scale) {
      scale = eventScale;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.5;
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
