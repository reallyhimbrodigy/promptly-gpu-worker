// ITEM 3 — WS2 caption fade-bound (Zac 2026-07-12).
//
// The audit found the caption styles carry FIXED fade durations (CleanCut 80ms,
// TypewriterReveal 150ms, Pulse 5f, Quintessence 3f, Prime's 250ms word spring)
// that ignore how long the word is actually on screen. On fast speech a word can
// show for ~200ms; an 80ms fade is then 40% of its life — the word is still
// resolving when it is already spoken, so the caption reads as LAG, not as
// landing on the beat.
//
// boundedFade caps the fade at a quarter of the display window: the word is fully
// legible for at least three-quarters of the time it is up. Pure and unit-
// agnostic — the caller passes base and window in the SAME unit (frames or ms).
//
// UNIVERSAL FAST CAP (Zac 2026-07-12): the ≤25%-of-window bound is only RELATIVE —
// on a long word window (>4×base) it just returns the base, and the bases were
// still slow (Prime 160ms, Typewriter 90ms). Worse, the scale/slide/spring MOTION
// channels bypassed this helper entirely (Lumen ~1s, TwoTone ~330ms, Gadzhi 167ms,
// CleanCut 140ms). So EVERY caption still animated slowly on most styles. The fix
// is a single absolute ceiling — no style's entrance may exceed MAX_ENTRANCE_MS,
// applied to BOTH the fade and the motion channel. The unit self-resolves: the
// ms-based callers cap at 80ms; for the frame-based callers (Pulse/Quintessence)
// "80" reads as 80 FRAMES, which never binds (their base is 3-5f) — harmless.
export const FADE_WINDOW_FRACTION = 0.25;
export const MAX_ENTRANCE_MS = 80; // every caption entrance is quick-but-present

export function boundedFade(base: number, windowLen: number): number {
  if (!(windowLen > 0)) return 0; // no window (or NaN) → no fade
  return Math.min(base, windowLen * FADE_WINDOW_FRACTION, MAX_ENTRANCE_MS);
}
