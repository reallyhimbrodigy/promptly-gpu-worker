import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { StagedPush } from "./zoom/StagedPush/StagedPush";
import { SmoothGraphicsProvider } from "./motion-graphics/shared/smooth-graphics-flag";
import { MotionBlurProvider, MotionBlurWrap } from "./motion-graphics/shared/motion-blur";
import type { StagedPushEvent } from "./zoom/types";

/**
 * StagedPushProbe — isolated LOOK test for the multi-stage emphasis zoom (not
 * production). Renders StagedPush on the sample talking-head clip so the staged
 * push-in can be judged in isolation: smooth-fast equal steps, peak on each stage,
 * hold on the final, adaptive release. staged-push-battery.mjs drives the events.
 *
 * The velocity-cap A/B (velocity-cap-ab.mjs) drives the three flags below to
 * render OFF / CAP / CAP+BLUR off ONE composition, so the only thing that varies
 * between arms is the flag — never the scene.
 */
export interface StagedPushProbeProps {
  events: StagedPushEvent[];
  /** Drives the zoom VELOCITY CAP so an OFF/ON pair is renderable locally. */
  smoothGraphics?: boolean;
  /** Override the probe source (the A/B uses a PINNED real talking-head clip). */
  src?: string;
  /** Residual motion blur — the "then blur what remains" arm. */
  motionBlur?: boolean;
  motionBlurSamples?: number;
  motionBlurShutterAngle?: number;
}

const DEFAULT_EVENTS: StagedPushEvent[] = [
  {
    // a 3-part continuing example: peaks at 1.0s / 1.8s / 2.6s, equal +8% steps
    stages: [
      { atMs: 1000, scale: 1.08 },
      { atMs: 1800, scale: 1.16 },
      { atMs: 2600, scale: 1.24 },
    ],
    cutTerminated: false,
  },
];

export const StagedPushProbe: React.FC<StagedPushProbeProps> = ({
  events,
  smoothGraphics,
  src,
  motionBlur,
  motionBlurSamples,
  motionBlurShutterAngle,
}) => {
  return (
    <SmoothGraphicsProvider enabled={smoothGraphics ?? false}>
      <MotionBlurProvider
        enabled={motionBlur ?? false}
        samples={motionBlurSamples}
        shutterAngle={motionBlurShutterAngle}
      >
        <AbsoluteFill style={{ backgroundColor: "#000" }}>
          {/* StagedPush calls useCurrentFrame() itself and sits INSIDE the wrap,
              which is what makes CameraMotionBlur's time-shifted re-renders
              actually reach the zoom curve (Remotion's documented common
              mistake is reading the frame outside the blur context). */}
          <MotionBlurWrap>
            <StagedPush
              src={staticFile(src ?? "test_talking_head.mp4")}
              events={events ?? DEFAULT_EVENTS}
            />
          </MotionBlurWrap>
        </AbsoluteFill>
      </MotionBlurProvider>
    </SmoothGraphicsProvider>
  );
};
