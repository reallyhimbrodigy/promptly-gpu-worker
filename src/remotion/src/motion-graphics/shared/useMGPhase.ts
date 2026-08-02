import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import { msToFrames } from "./timing";
import { useSmoothGraphics } from "./smooth-graphics-flag";
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
  const exitStartFrame = durationFrames - exitFrames;

  const visible = localFrame >= -2 && localFrame <= durationFrames + 2;

  const enterProgress = interpolate(
    localFrame,
    [0, enterFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // ease-OUT: decelerate INTO the settled position (the "arrival").
      // undefined = linear = today's exact behavior when smooth is OFF.
      easing: smooth ? Easing.out(Easing.cubic) : undefined,
    },
  );

  const exitProgress = interpolate(
    localFrame,
    [exitStartFrame, durationFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // ease-IN: accelerate AWAY on departure.
      easing: smooth ? Easing.in(Easing.cubic) : undefined,
    },
  );

  let phase: MGPhaseState["phase"];
  if (localFrame < 0) phase = "before";
  else if (localFrame < enterFrames) phase = "entering";
  else if (localFrame < exitStartFrame) phase = "holding";
  else if (localFrame < durationFrames) phase = "exiting";
  else phase = "after";

  return {
    visible,
    enterProgress,
    exitProgress,
    phase,
    localFrame,
    durationFrames,
  };
}
