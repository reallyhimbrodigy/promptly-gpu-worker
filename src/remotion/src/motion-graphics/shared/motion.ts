import { spring, Easing } from "remotion";
import type { SpringConfig } from "remotion";

/**
 * SHARED MOTION TOKEN SYSTEM — Flare quality campaign (Workstream D).
 *
 * ONE vocabulary for every animated element outside the caption text layer.
 * No component may declare a spring config or an easing curve inline; it
 * references a token here. The build gate enforces this (see validate-motion).
 *
 * The whole system is behind ONE reversible flag (MOTION_TOKENS) so the
 * before/after is a true A/B and a bad verdict is one flip to undo. When the
 * flag is OFF every migrated component renders its preserved LEGACY_* config,
 * i.e. exactly today's pixels. When ON it renders the token below.
 *
 * CALIBRATION LAW: these are consolidated toward the BEST existing motion in
 * the codebase, not the mean of it. Provenance is noted per token. Where the
 * best value is genuinely unsettled (SNAP damping ratio), BOTH variants ship
 * in the A/B and Zac's eye decides — we do not pick here.
 *
 * NOTE — the caption text layer (src/captions/) is EXCLUDED. Caption entrances
 * are FRAME-1-IS-FINAL by standing law (zero entrance channels); these entrance
 * springs never touch a caption word.
 */

// ── SPRING PRESETS ────────────────────────────────────────────────────────

/**
 * SNAP — emphasis pops, stamps, banner arrivals. Punchy overshoot, fast settle.
 * Provenance: today's SPRING_SNAPPY, the most-used good spring (6 call sites:
 * the 4 SpeechBubbles, ProgressBar track, AnnotationArrow head). ACTUAL ζ≈0.50
 * (~16% overshoot) — its old comment miscalculated ζ as 0.71.
 * This is the punchy variant.
 */
export const SNAP: SpringConfig = {
  damping: 10,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false,
}; // ζ = 10/(2·√(200·0.5)) = 0.50 → ~16% overshoot

/**
 * SNAP_TIGHT — the subtle variant of SNAP. Same ωn, higher damping ratio, so a
 * small (~4%) overshoot that reads "crisp" rather than "bouncy". Shipped
 * ALONGSIDE SNAP in the A/B: which one reads premium is Zac's-eye, not ours.
 */
export const SNAP_TIGHT: SpringConfig = {
  damping: 14,
  mass: 0.5,
  stiffness: 200,
  overshootClamping: false,
}; // ζ = 14/20 = 0.70 → ~4% overshoot

/**
 * SETTLE — entrances that should arrive and rest (cards, drop banners, bubbles,
 * sticky notes). Gentle overshoot, clean land — no visible bounce, but alive.
 * Provenance: Notification {mass 0.6, damping 14, stiffness 220, ζ≈0.61}, the
 * best pure-entrance spring in motion-graphics, nudged to ζ≈0.67.
 */
export const SETTLE: SpringConfig = {
  damping: 14,
  mass: 0.6,
  stiffness: 180,
  overshootClamping: false,
}; // ζ = 14/(2·√(180·0.6)) ≈ 0.67 → ~6% overshoot

/**
 * GLIDE — slow moves and zoom reframes. Critically damped, NO bounce at all.
 * Provenance: the DropBanner/DropCard column-scroll {damping 19, stiffness 100,
 * ζ≈0.95}, whose own comment reads "clean settle, no bounce" — the proven-good
 * no-overshoot archetype. overshootClamping belt-and-suspenders.
 */
export const GLIDE: SpringConfig = {
  damping: 19,
  mass: 1,
  stiffness: 100,
  overshootClamping: true,
}; // ζ = 19/20 = 0.95, clamped → monotonic, eases flat to rest

// ── EASING TOKENS ─────────────────────────────────────────────────────────
// For channels that are curve-driven (transition crossfades, zoom pushes,
// fade-outs) rather than spring-driven. Consolidated from the existing curves
// that already read well; the amateur bare-linear channels migrate to these.

/** Decel to rest — the good "glide in" curve (zoom-in default, fade-in). */
export const EASE_GLIDE = Easing.out(Easing.cubic);
/** Accel — the "punch" flip: energy builds into the anchor frame. */
export const EASE_PUNCH = Easing.in(Easing.cubic);
/** Symmetric push — Keynote/Powerpoint grammar. Provenance: StepPush 0.65,0,0.35,1. */
export const EASE_PUSH = Easing.bezier(0.65, 0, 0.35, 1);
/** House snappy ease-out, already reused by ZoomThrough/CardSwipe/Stack. */
export const EASE_SNAP_OUT = Easing.bezier(0.32, 0.72, 0, 1);
/** House ease-out-quad, already reused by SlideOver/CrossfadeZoom/Stack. */
export const EASE_SOFT_OUT = Easing.bezier(0.25, 0.46, 0.45, 0.94);

// ── DURATION VOCABULARY ───────────────────────────────────────────────────
// Component ENTRANCE/EMPHASIS windows only. Expressed in ms and converted to
// frames at the comp's fps (30 canonical, 60 production, 30 micro) so timing is
// identical across renders — same discipline as the transition weight ladder.
// NOTE: transition SLOT durations (the 350→1200ms editorial weight ladder in
// handler.py) are a separate, already-coherent system and are NOT replaced here.

export const DUR_MS = {
  FAST: 130, // pops, accents
  BASE: 230, // standard entrance
  SLOW: 400, // heavy / deliberate arrivals
} as const;

export type DurName = keyof typeof DUR_MS;

/** ms → frames at a given fps, min 1 frame. */
export const durFrames = (ms: number, fps: number): number =>
  Math.max(1, Math.round((ms / 1000) * fps));

/** Convenience: a named duration in frames at a given fps. */
export const dur = (name: DurName, fps: number): number =>
  durFrames(DUR_MS[name], fps);

// ── PAYOFF COMPUTATION ────────────────────────────────────────────────────
// The payoff-frame law: an element's visual "landing" must sit ON the anchor
// frame, so it is scheduled at (anchor − timeToPayoff). timeToPayoff is NOT a
// guessed constant — it is COMPUTED from the actual spring, fps and
// durationInFrames by sampling Remotion's own spring() and locating the peak.
//
//   - underdamped (overshoots): payoff = frame of the FIRST overshoot peak.
//   - critically/over-damped or clamped (monotonic): payoff = first frame that
//     reaches 95% of the settle value.

const SETTLE_THRESHOLD = 0.95;

/**
 * Frame offset from a spring's start to its visual payoff, for the given fps
 * (and optional durationInFrames re-time). Sampled from Remotion's spring().
 */
export function payoffFrame(
  config: SpringConfig,
  fps: number,
  durationInFrames?: number,
): number {
  const maxF = durationInFrames ?? Math.max(1, Math.round(fps * 1.5));

  // Pass 1: first overshoot peak (first frame whose value exceeds the next).
  let prev = -Infinity;
  for (let f = 0; f <= maxF; f++) {
    const v = spring({ frame: f, fps, config, durationInFrames });
    if (f > 0 && prev > v && prev >= SETTLE_THRESHOLD) {
      return f - 1; // peak was the previous frame
    }
    prev = v;
  }

  // Pass 2: no overshoot (monotonic) → first frame at/above the settle bar.
  for (let f = 0; f <= maxF; f++) {
    if (spring({ frame: f, fps, config, durationInFrames }) >= SETTLE_THRESHOLD) {
      return f;
    }
  }
  return maxF;
}

/**
 * @deprecated Migration alias. Existing imports of SPRING_SNAPPY resolve to
 * SNAP so nothing breaks mid-migration; remove once all call sites reference
 * the token directly and the gate is green.
 */
export const SPRING_SNAPPY = SNAP;
