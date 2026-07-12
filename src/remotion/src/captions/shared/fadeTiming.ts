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
export const FADE_WINDOW_FRACTION = 0.25;

export function boundedFade(base: number, windowLen: number): number {
  if (!(windowLen > 0)) return 0; // no window (or NaN) → no fade, never divide into nothing
  const ceiling = windowLen * FADE_WINDOW_FRACTION;
  return base < ceiling ? base : ceiling;
}
