import type { MGPhase } from "./types";

// THE ENTER-WINDOW CLAMP (2026-08-26, its own gated change — mg-phase.test.mjs
// imports THIS file directly, so it must stay free of React/Remotion imports).
//
// A computed enter window can outlive a short placement's pre-exit window
// (SectionDivider live: enter 50f vs a 46f life with exit from f22). Unclamped,
// that meant: phase read "entering" on frames where exitProgress was already
// rising (contradictory), enterProgress never reached 1 (consumers render
// mid-entrance for the component's whole life), and "holding" was unreachable
// (phase-keyed masks never lifted). The effective enter window is clamped to
// end at least 1 frame before exit onset, so the entrance always COMPLETES and
// holding is always reachable whenever the window allows any hold at all.
// Identity for every healthy window (enter <= exitStart − 1): render-proven
// zero-pixel-diff across families at standard windows.
export interface MGPhaseFrameInputs {
  localFrame: number;
  durationFrames: number;
  // Smooth-resolved (post ms-floor) enter/exit frame counts.
  enterFrames: number;
  exitFrames: number;
}
export interface MGPhaseFrames {
  visible: boolean;
  phase: MGPhase;
  exitStartFrame: number;
  effectiveEnterFrames: number;
}
export function resolveMGPhaseFrames({
  localFrame,
  durationFrames,
  enterFrames,
  exitFrames,
}: MGPhaseFrameInputs): MGPhaseFrames {
  const exitStartFrame = durationFrames - exitFrames;
  const effectiveEnterFrames = Math.min(
    enterFrames,
    Math.max(1, exitStartFrame - 1),
  );
  const visible = localFrame >= -2 && localFrame <= durationFrames + 2;
  let phase: MGPhase;
  if (localFrame < 0) phase = "before";
  else if (localFrame < effectiveEnterFrames) phase = "entering";
  else if (localFrame < exitStartFrame) phase = "holding";
  else if (localFrame < durationFrames) phase = "exiting";
  else phase = "after";
  return { visible, phase, exitStartFrame, effectiveEnterFrames };
}
