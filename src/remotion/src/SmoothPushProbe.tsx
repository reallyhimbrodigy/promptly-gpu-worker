import React from "react";
import { AbsoluteFill, staticFile } from "remotion";
import { SmoothPush } from "./zoom";
import { SmoothGraphicsProvider } from "./motion-graphics/shared/smooth-graphics-flag";
import type { ZoomEvent } from "./zoom/types";

/**
 * SmoothPushProbe — the velocity-cap pair on the zoom that ACTUALLY SHIPS.
 *
 * SmoothPush is 48.6% of all zooms in production; StagedPush (which the first
 * pair used) fires 3 times in 1,542. So this is the arm that decides whether the
 * cap is worth flipping, and it drives the REAL SmoothPush component — not a
 * copy — so what is judged is the shipped behaviour.
 *
 * Deliberately BARE: no label, no onset flash, no border. ZoomEaseProbe has
 * those for the glide/punch read, but any overlay is itself a visual event and
 * would pollute a taste call about smoothness.
 */
export interface SmoothPushProbeProps {
  events: ZoomEvent[];
  /** Drives the zoom VELOCITY CAP so an OFF/CAP pair is renderable locally. */
  smoothGraphics?: boolean;
  /** PUNCH (ease-in) vs GLIDE (ease-out) — the vibe register. */
  punch?: boolean;
  /** Override the probe source (the A/B uses a PINNED real talking-head clip). */
  src?: string;
}

// Production defaults: ZOOM_NATURAL_DURATION_FRAMES / ZOOM_NATURAL_SCALE.
// 1200ms / 1.22, placed 1.6s in so the capped ramp has real lead-in headroom to
// grow backwards into — which is exactly how it preserves the zoom amplitude.
const DEFAULT_EVENTS: ZoomEvent[] = [
  { startMs: 1600, durationMs: 1200, scale: 1.22, originX: 0.5, originY: 0.42 },
];

export const SmoothPushProbe: React.FC<SmoothPushProbeProps> = ({
  events,
  smoothGraphics,
  punch,
  src,
}) => {
  return (
    <SmoothGraphicsProvider enabled={smoothGraphics ?? false}>
      <AbsoluteFill style={{ backgroundColor: "#000" }}>
        <SmoothPush
          src={staticFile(src ?? "test_talking_head.mp4")}
          punch={punch ?? false}
          events={events ?? DEFAULT_EVENTS}
        />
      </AbsoluteFill>
    </SmoothGraphicsProvider>
  );
};
