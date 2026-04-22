import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
  spring,
} from "remotion";
import { OffthreadVideo } from "remotion";
import { msToFrames } from "../shared/timing";
import type { FocusWindowProps } from "../types";

/**
 * Focus Window — background shows the video zoomed in on a detail,
 * a smaller rectangle overlaid shows the video at normal framing.
 * Clean border on the window. Editorial, premium, broadcast feel.
 */
export const FocusWindow: React.FC<FocusWindowProps> = ({
  src,
  events,
  style,
  windowScale = 0.72,
  borderWidth = 0,
  borderColor = "transparent",
  bgScale = 1.8,
  startFrom,
  playbackRate = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  let active = false;
  let progress = 0;
  let originX = 0.5;
  let originY = 0.4;
  let eventBgScale = bgScale;

  for (const event of events) {
    const eventStart = msToFrames(event.startMs, fps);
    const eventEnd = msToFrames(event.startMs + event.durationMs, fps);

    if (frame < eventStart || frame > eventEnd) continue;
    active = true;

    eventBgScale = event.scale ?? bgScale;
    originX = event.originX ?? 0.5;
    originY = event.originY ?? 0.4;

    const enterDuration = Math.round(fps * 0.5);
    const enterProgress = spring({
      frame: frame - eventStart,
      fps,
      config: {
        damping: 24,
        mass: 0.7,
        stiffness: 180,
        overshootClamping: true,
      },
      durationInFrames: enterDuration,
    });

    const exitStart = eventEnd - Math.round(fps * 0.4);
    const exitProgress =
      frame >= exitStart
        ? interpolate(frame, [exitStart, eventEnd], [0, 1], {
            easing: Easing.in(Easing.cubic),
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : 0;

    progress = enterProgress * (1 - exitProgress);
  }

  if (!active) {
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
      </AbsoluteFill>
    );
  }

  const currentWindowScale = interpolate(progress, [0, 1], [1, windowScale]);
  const currentBgScale = interpolate(progress, [0, 1], [1, eventBgScale]);
  const currentBorder = borderWidth * progress;

  return (
    <AbsoluteFill style={{ overflow: "hidden", ...style }}>
      <OffthreadVideo
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${currentBgScale})`,
          transformOrigin: `${originX * 100}% ${originY * 100}%`,
        }}
      />

      <AbsoluteFill
        style={{
          backgroundColor: `rgba(0,0,0,${0.3 * progress})`,
          pointerEvents: "none",
        }}
      />

      <AbsoluteFill
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <div
          style={{
            width: `${currentWindowScale * 100}%`,
            height: `${currentWindowScale * 100}%`,
            overflow: "hidden",
            border: `${currentBorder}px solid ${borderColor}`,
            boxShadow:
              progress > 0.1
                ? `0 ${8 * progress}px ${30 * progress}px rgba(0,0,0,${0.5 * progress})`
                : "none",
            position: "relative",
          }}
        >
          <OffthreadVideo
            src={src}
            style={{
              width: `${(1 / currentWindowScale) * 100}%`,
              height: `${(1 / currentWindowScale) * 100}%`,
              objectFit: "cover",
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
            }}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
