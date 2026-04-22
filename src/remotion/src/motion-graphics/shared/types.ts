// Shared types for motion graphics components.
//
// Convention: every motion graphic accepts standardized timing props so it can
// be slotted into any timeline without bespoke math at the call site.

export interface MGTimingProps {
  // When the entrance begins, in milliseconds from composition start.
  startMs: number;
  // Total on-screen lifespan in milliseconds, including entrance and exit.
  durationMs: number;
  // Optional override for entrance length (frames). Component-defined default if omitted.
  enterFrames?: number;
  // Optional override for exit length (frames). Component-defined default if omitted.
  exitFrames?: number;
}

export type MGPhase = "before" | "entering" | "holding" | "exiting" | "after";

export interface MGPhaseState {
  // True when the component should be rendered at all.
  visible: boolean;
  // 0 → 1 across the entrance window (clamped).
  enterProgress: number;
  // 0 → 1 across the exit window (clamped). 0 while holding.
  exitProgress: number;
  // Current phase label.
  phase: MGPhase;
  // Frames elapsed since `startMs` (negative before, can exceed duration after).
  localFrame: number;
  // Convenience: durationMs converted to frames.
  durationFrames: number;
}
