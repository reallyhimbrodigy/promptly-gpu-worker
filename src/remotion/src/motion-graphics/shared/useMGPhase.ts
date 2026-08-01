import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { msToFrames } from "./timing";
import type { MGPhaseState, MGTimingProps } from "./types";

interface Options {
  defaultEnterFrames: number;
  defaultExitFrames: number;
}

// Computes per-frame entrance/hold/exit progress for a motion graphic given
// its standardized timing props. Each component supplies its own sensible
// defaults for entrance/exit length.
export function useMGPhase(
  timing: MGTimingProps,
  { defaultEnterFrames, defaultExitFrames }: Options,
): MGPhaseState {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const startFrame = msToFrames(timing.startMs, fps);
  const durationFrames = msToFrames(timing.durationMs, fps);
  const enterFrames = timing.enterFrames ?? defaultEnterFrames;
  const exitFrames = timing.exitFrames ?? defaultExitFrames;

  const localFrame = frame - startFrame;
  const exitStartFrame = durationFrames - exitFrames;

  const visible = localFrame >= -2 && localFrame <= durationFrames + 2;

  const enterProgress = interpolate(
    localFrame,
    [0, enterFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const exitProgress = interpolate(
    localFrame,
    [exitStartFrame, durationFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
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
