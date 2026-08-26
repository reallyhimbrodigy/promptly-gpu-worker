import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { msToFrames } from "./timing";
import { useSmoothGraphics } from "./smooth-graphics-flag";
import { trapezoidEasing, MIN_BLEND_FRACTION } from "../../zoom/shared/velocity-cap";
import { resolveMGPhaseFrames } from "./mg-phase-frames";
import type { MGPhaseState, MGTimingProps } from "./types";

interface Options {
  defaultEnterFrames: number;
  defaultExitFrames: number;
}

// SMOOTH-GRAPHICS (Zac 2026-08-01). ms-BASE DECISION (LOCKED, do NOT restore):
// authored enter/exit frame counts are interpreted at 30fps -> ms (8f = 267ms,
// NOT the pre-flip 133ms@60), then floored to a perceptual constant so an
// entrance always carries enough SAMPLES, and the linear ramp is replaced by an
// eased curve so the samples distribute by acceleration, not equal jumps (8
// equal jumps = the "low frame rate" read). Fixed frames were fps-DEPENDENT --
// the root of the class -- so ms makes it fps-independent.
const _REF_FPS = 30;
const _ENTER_FLOOR_MS = 400; // >=12 samples @30fps
const _EXIT_FLOOR_MS = 350; // >=10 samples @30fps
const _framesToFlooredMs = (f: number, floorMs: number) =>
  Math.max(floorMs, (f / _REF_FPS) * 1000);

// Computes per-frame entrance/hold/exit progress for a motion graphic given
// its standardized timing props. Each component supplies its own sensible
// defaults for entrance/exit length.
export function useMGPhase(
  timing: MGTimingProps,
  { defaultEnterFrames, defaultExitFrames }: Options,
): MGPhaseState {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const smooth = useSmoothGraphics();

  const startFrame = msToFrames(timing.startMs, fps);
  const durationFrames = msToFrames(timing.durationMs, fps);

  const rawEnterFrames = timing.enterFrames ?? defaultEnterFrames;
  const rawExitFrames = timing.exitFrames ?? defaultExitFrames;
  // smooth ON: convert the authored frame count to a FLOORED ms duration, then
  // back to frames at the render fps (fps-independent + enough samples).
  const enterFrames = smooth
    ? msToFrames(_framesToFlooredMs(rawEnterFrames, _ENTER_FLOOR_MS), fps)
    : rawEnterFrames;
  const exitFrames = smooth
    ? msToFrames(_framesToFlooredMs(rawExitFrames, _EXIT_FLOOR_MS), fps)
    : rawExitFrames;

  const localFrame = frame - startFrame;
  const { visible, phase, exitStartFrame, effectiveEnterFrames } =
    resolveMGPhaseFrames({ localFrame, durationFrames, enterFrames, exitFrames });

  const enterProgress = interpolate(
    localFrame,
    [0, effectiveEnterFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // TRAPEZOID, not ease-out cubic. Measured: ease-out cubic peaks at 3x the
      // linear average ON THE FIRST FRAME, so it made its one consumer
      // (PillMarquee) step WORSE, 0.30 -> 0.41 peak_step. Same finding as the
      // zoom cap, same fix — one profile for all motion in this codebase.
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.25) : undefined,
    },
  );

  const exitProgress = interpolate(
    localFrame,
    [exitStartFrame, durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // Departure: the same bounded-velocity profile, skewed late so the exit
      // accelerates away rather than crawling off.
      easing: smooth ? trapezoidEasing(MIN_BLEND_FRACTION, 0.75) : undefined,
    },
  );

  return {
    visible,
    enterProgress,
    exitProgress,
    phase,
    localFrame,
    durationFrames,
    exitStartFrame,
  };
}
