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
import type { DepthPullProps } from "../types";

const BOKEH_ORBS = [
  { x: 15, y: 22, size: 110, delay: 0, driftX: 25, driftY: -12 },
  { x: 72, y: 58, size: 80, delay: 4, driftX: -18, driftY: 8 },
  { x: 42, y: 78, size: 95, delay: 7, driftX: 12, driftY: -20 },
  { x: 82, y: 18, size: 65, delay: 2, driftX: -8, driftY: 15 },
  { x: 28, y: 50, size: 70, delay: 10, driftX: 20, driftY: 5 },
];

/**
 * Depth Pull — multi-layer cinematic depth zoom. Background video zooms
 * slowly while floating bokeh orbs, edge blur, atmospheric haze, and
 * decorative frame lines create genuine perceived 3D depth.
 * The look of an HBO title sequence.
 */
export const DepthPull: React.FC<DepthPullProps> = ({
  src,
  events,
  style,
  edgeBlur = 4,
  frameLines = true,
  startFrom,
  playbackRate = 1,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  let zoomProgress = 0;
  let originX = 0.5;
  let originY = 0.45;
  let targetScale = 1.15;

  if (events.length === 0) {
    // Full-duration: ramp in first 40%, hold 20%, ramp out last 40%
    const rampIn = Math.round(durationInFrames * 0.4);
    const holdEnd = Math.round(durationInFrames * 0.6);

    if (frame < rampIn) {
      zoomProgress = interpolate(frame, [0, rampIn], [0, 1], {
        easing: Easing.out(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    } else if (frame < holdEnd) {
      zoomProgress = 1;
    } else {
      zoomProgress = interpolate(frame, [holdEnd, durationInFrames], [1, 0], {
        easing: Easing.in(Easing.cubic),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
    }
  } else {
    for (const event of events) {
      const eventStart = msToFrames(event.startMs, fps);
      const eventEnd = msToFrames(event.startMs + event.durationMs, fps);
      if (frame < eventStart || frame > eventEnd) continue;

      targetScale = event.scale ?? 1.15;
      originX = event.originX ?? 0.5;
      originY = event.originY ?? 0.45;

      const eventDuration = eventEnd - eventStart;
      const rampIn = eventStart + Math.round(eventDuration * 0.35);
      const holdEnd = eventStart + Math.round(eventDuration * 0.6);

      if (frame < rampIn) {
        zoomProgress = interpolate(frame, [eventStart, rampIn], [0, 1], {
          easing: Easing.out(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      } else if (frame < holdEnd) {
        zoomProgress = 1;
      } else {
        zoomProgress = interpolate(frame, [holdEnd, eventEnd], [1, 0], {
          easing: Easing.in(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      }
    }
  }

  const bgScale = 1 + (targetScale - 1) * 0.6 * zoomProgress;
  const midScale = 1 + (targetScale - 1) * 1.0 * zoomProgress;
  const currentEdgeBlur = edgeBlur * zoomProgress;

  const frameOpacity = interpolate(
    zoomProgress,
    [0, 0.25, 0.75, 1],
    [0, 0.15, 0.15, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const frameScale = 1 - 0.04 * zoomProgress;

  return (
    <AbsoluteFill
      style={{
        overflow: "hidden",
        ...style,
      }}
    >
      <AbsoluteFill>
        <OffthreadVideo
          src={src}
          startFrom={startFrom}
          playbackRate={playbackRate}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(${bgScale})`,
            transformOrigin: `${originX * 100}% ${originY * 100}%`,
          }}
        />
      </AbsoluteFill>

      {/* Removed: contrast/brightness boost, background saturate/darken,
          and blue mixBlendMode-multiply tint. Those were a global cinematic
          color grade that read as "subtle color effects on emphasis
          moments" — unwanted. The geometric zoom + bokeh + edge blur
          remain as the depth/atmosphere identity. */}

      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(180deg,
            rgba(180, 160, 130, ${0.025 * zoomProgress}) 0%,
            rgba(160, 140, 110, ${0.04 * zoomProgress}) 50%,
            rgba(140, 120, 100, ${0.025 * zoomProgress}) 100%)`,
          mixBlendMode: "screen",
          filter: "blur(20px)",
          transform: `scale(${midScale})`,
          pointerEvents: "none",
        }}
      />

      {BOKEH_ORBS.map((orb, i) => {
        const orbStart = events.length > 0
          ? msToFrames(events[0].startMs, fps) + orb.delay
          : orb.delay;
        const orbDuration = events.length > 0
          ? msToFrames(events[0].durationMs, fps)
          : durationInFrames;

        const orbProgress = interpolate(
          frame,
          [orbStart, orbStart + orbDuration],
          [0, 1],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );
        const orbOpacity = interpolate(
          orbProgress,
          [0, 0.12, 0.85, 1],
          [0, 0.12, 0.12, 0],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
        );

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${orb.x + orb.driftX * orbProgress}%`,
              top: `${orb.y + orb.driftY * orbProgress}%`,
              width: orb.size,
              height: orb.size,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(255,220,160,0.35) 0%, rgba(255,200,120,0.08) 40%, transparent 70%)",
              filter: "blur(15px)",
              mixBlendMode: "screen",
              opacity: orbOpacity,
              transform: `scale(${midScale})`,
              pointerEvents: "none",
            }}
          />
        );
      })}

      {currentEdgeBlur > 0.2 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitBackdropFilter: `blur(${currentEdgeBlur}px)`,
            WebkitMaskImage:
              "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            maskImage:
              "radial-gradient(ellipse 50% 50% at center, transparent 25%, black 80%)",
            pointerEvents: "none",
          }}
        />
      )}

      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center,
            transparent 35%,
            rgba(15, 8, 3, ${0.2 * zoomProgress}) 70%,
            rgba(8, 4, 2, ${0.45 * zoomProgress}) 100%)`,
          pointerEvents: "none",
        }}
      />

      {frameLines && frameOpacity > 0.01 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              width: "84%",
              height: "84%",
              border: `1px solid rgba(255, 255, 255, ${frameOpacity})`,
              transform: `scale(${frameScale})`,
            }}
          />
        </div>
      )}
    </AbsoluteFill>
  );
};
