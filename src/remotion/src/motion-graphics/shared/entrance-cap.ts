/**
 * MG ENTRANCE VELOCITY CAP (Zac 2026-08-01) — the same single quantity as the
 * zoom cap: PEAK PER-FRAME TRAVEL.
 *
 * WHY THIS, AND NOT A FRAME-COUNT FLOOR. Frame count does not predict stepping;
 * CONCENTRATION does. Measured on the battery, decimated to the 30fps delivery
 * grid (mg_entrance_step_audit.py):
 *     ChatThread     5-frame pop,  peak_step 0.20  -> ~5 positions, reads FINE
 *     SpeechBubbles 12-frame spring, peak_step 0.60 -> ~1.7 positions, STEPS
 * The twelve-frame animation is the one that steps, because SPRING_SNAPPY dumps
 * 60% of its travel into a single delivered frame. So a "≥N frames" floor would
 * have migrated the wrong components and left the real offenders alone.
 *
 * peak_step = the largest fraction of the entrance's total travel that lands in
 * ONE delivered frame. 1/peak_step = effective positions. The trapezoid profile
 * (shared with the zoom cap — one source of truth for the curve) has peak
 * velocity k = 1/(1-b/2) x the linear average, so over N frames
 *     peak_step = k / N
 * and the floor below is simply N >= k / MAX_STEP.
 *
 * Solved at 30fps ALWAYS (CAP_REFERENCE_FPS), so the entrance keeps its DURATION
 * at any render fps instead of doubling in speed at 60 — the same ms-base
 * decision the zoom cap and useMGPhase make, for the same reason.
 */
import {
  CAP_REFERENCE_FPS,
  MIN_BLEND_FRACTION,
  trapezoidEasing,
} from "../../zoom/shared/velocity-cap";

/**
 * Largest share of an entrance's travel allowed in one delivered frame.
 * 1/6 -> at least 6 effective positions. Calibrated against the components that
 * already read clean: PullQuote 0.16, StickyNotes 0.14, BarRace 0.13.
 */
export const MAX_ENTRANCE_STEP = 1 / 6;

/** Peak velocity of the shared trapezoid at the C1 floor: 1/(1-b/2). */
const PEAK_K = 1 / (1 - MIN_BLEND_FRACTION / 2);

/** Frames (at 30fps) an entrance needs so no single frame exceeds the cap. */
export const ENTRANCE_FLOOR_FRAMES_30 = Math.ceil(PEAK_K / MAX_ENTRANCE_STEP); // 8

/**
 * The eased, velocity-capped entrance progress 0->1.
 *
 * `authoredFrames` is the component's own entrance length at the RENDER fps; the
 * entrance is only ever LENGTHENED to meet the cap, never shortened, so a
 * component that already spreads its travel keeps its authored timing.
 *
 * Entrances GLIDE by default: an MG that pops in should decelerate into its
 * resting position (front-loaded), which is also what keeps the arrival reading
 * on the beat rather than drifting past it.
 */
export function cappedEntranceProgress(args: {
  localFrame: number;
  fps: number;
  authoredFrames: number;
  /** Override the shared cap for a component with unusually large travel. */
  maxStep?: number;
}): number {
  const floorAtFps = Math.ceil(
    (PEAK_K / (args.maxStep ?? MAX_ENTRANCE_STEP)) * (args.fps / CAP_REFERENCE_FPS),
  );
  const frames = Math.max(1, Math.max(args.authoredFrames, floorAtFps));
  const t = Math.min(Math.max(args.localFrame / frames, 0), 1);
  // GLIDE skew: energy early, decelerating into the resting position.
  return trapezoidEasing(MIN_BLEND_FRACTION, 0.25)(t);
}

/** The capped entrance length in frames, for components that need the span. */
export function cappedEntranceFrames(authoredFrames: number, fps: number, maxStep?: number): number {
  const floorAtFps = Math.ceil(
    (PEAK_K / (maxStep ?? MAX_ENTRANCE_STEP)) * (fps / CAP_REFERENCE_FPS),
  );
  return Math.max(1, Math.max(authoredFrames, floorAtFps));
}
