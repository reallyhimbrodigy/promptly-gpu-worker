import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { Video } from "@remotion/media";
import { msToFrames, msToFramesFloor } from "../shared/timing";
import { useSmoothGraphics } from "../../motion-graphics/shared/smooth-graphics-flag";
import {
  cornerPx, planCappedRampIn, planCappedRelease, SKEW_GLIDE, SKEW_PUNCH,
} from "../shared/velocity-cap";
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
  punch,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();
  // VELOCITY CAP (Zac 2026-08-01). OFF → today's exact cubic pixels.
  const smooth = useSmoothGraphics();
  // PUNCH (ease-in) accelerates the push INTO the word so the impact lands ON the
  // onset frame (viral/punchy); the default GLIDE (ease-out) front-loads the motion
  // and settles gently on the word (calm/corporate). Only the ramp-IN ease changes;
  // the scale still completes on the word either way. (Zac 2026-07-15)
  const rampInEase = punch ? Easing.in(Easing.cubic) : Easing.out(Easing.cubic);

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
    // Tracks the previous event's finished frame so a capped ramp can only grow
    // backwards into GENUINELY free time, never over its predecessor.
    let prevEventEnd = 0;
    for (const event of events) {
      const targetScale = event.scale ?? 1.2;
      const eventStart = msToFramesFloor(event.startMs, fps);
      const eventEnd = msToFrames(event.startMs + event.durationMs, fps);
      const eventDuration = eventEnd - eventStart;
      const rampIn = eventStart + Math.round(eventDuration * 0.35);
      const holdEnd = eventStart + Math.round(eventDuration * 0.6);

      // VELOCITY CAP. The ramp LANDS on rampIn — peak-on-word is a product law
      // (ZOOM_PEAK_REACH_MS back-times startMs for exactly this) — so it may
      // only grow BACKWARDS into the gap after the previous event. The release
      // is anchored at holdEnd and grows FORWARDS to the clip end; nothing is
      // waiting on it, so that is the cheap direction.
      const corner = cornerPx(width, height, event.originX ?? 0.5, event.originY ?? 0.5);
      const capIn = smooth
        ? planCappedRampIn({
            fromScale: 1,
            toScale: targetScale,
            landFrame: rampIn,
            earliestFrame: Math.min(prevEventEnd, eventStart),
            authoredFrames: Math.max(1, rampIn - eventStart),
            fps,
            corner,
            // the vibe register, preserved under the cap (see velocity-cap.ts):
            // PUNCH accelerates INTO the word, GLIDE decelerates into it.
            skew: punch ? SKEW_PUNCH : SKEW_GLIDE,
          })
        : null;
      const capOut = smooth
        ? planCappedRelease({
            fromScale: capIn ? capIn.toScale : targetScale,
            toScale: 1,
            startFrame: holdEnd,
            latestFrame: durationInFrames,
            authoredFrames: Math.max(1, eventEnd - holdEnd),
            fps,
            corner,
            skew: SKEW_GLIDE,   // a release lands on nothing — it always glides

          })
        : null;

      const spanStart = capIn ? capIn.startFrame : eventStart;
      const spanEnd = capOut ? capOut.endFrame : eventEnd;
      prevEventEnd = spanEnd;
      if (frame < spanStart || frame > spanEnd) continue;

      const peakScale = capIn ? capIn.toScale : targetScale;
      let progress: number;
      if (frame < rampIn) {
        progress = interpolate(frame, [spanStart, rampIn], [0, 1], {
          easing: capIn ? capIn.easing : rampInEase,
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      } else if (frame < holdEnd) {
        progress = 1;
      } else {
        progress = interpolate(frame, [holdEnd, spanEnd], [1, 0], {
          easing: capOut ? capOut.easing : Easing.in(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
      }

      scale = 1 + (peakScale - 1) * progress;
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
