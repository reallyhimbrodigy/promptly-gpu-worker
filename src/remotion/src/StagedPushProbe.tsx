import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { StagedPush } from "./zoom/StagedPush/StagedPush";
import type { StagedPushEvent } from "./zoom/types";

/**
 * StagedPushProbe — isolated LOOK test for the multi-stage emphasis zoom (not
 * production). Renders StagedPush on the sample talking-head clip so the staged
 * push-in can be judged in isolation: smooth-fast equal steps, peak on each stage,
 * hold on the final, adaptive release. staged-push-battery.mjs drives the events.
 */
export interface StagedPushProbeProps {
  events: StagedPushEvent[];
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

export const StagedPushProbe: React.FC<StagedPushProbeProps> = ({ events }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <StagedPush src={staticFile("test_talking_head.mp4")} events={events ?? DEFAULT_EVENTS} />
    </AbsoluteFill>
  );
};
