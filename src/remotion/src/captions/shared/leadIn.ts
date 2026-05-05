// Lead-in animation timing.
//
// Per-word reveal animations should peak AT the moment a word is spoken,
// not start from it. Without lead-in, a 360 ms fade starts when the audio
// hits the word and reaches full visibility 360 ms later — by which point
// the speaker has moved on, producing the "delayed caption" feel.
//
// With lead-in, the animation builds up TO the spoken moment so the word
// is fully readable the instant it's audibly delivered. Same animation,
// same duration, same visual character — just anchored to END at the
// spoken time instead of START there.

// Default spring lead-in: covers most of our caption springs' settle
// windows (~7-14 frames depending on damping/stiffness). Springs that
// settle slower can pass a larger value; springs that settle faster
// can clamp earlier without visual cost.
export const SPRING_LEAD_IN_FRAMES = 8;

/**
 * Spring/elapsed-frame style.
 *
 * Returns the elapsed-frames value to feed into `spring({ frame })` such
 * that the spring is at its settle point when `currentFrame` reaches
 * `anchorFrame`. The spring effectively starts at
 * `anchorFrame - leadInFrames`.
 *
 *   const elapsed = leadInElapsed(frame, activateFrame);
 *   const value = spring({ fps, frame: elapsed, config: ... });
 */
export function leadInElapsed(
  currentFrame: number,
  anchorFrame: number,
  leadInFrames: number = SPRING_LEAD_IN_FRAMES,
): number {
  return currentFrame - (anchorFrame - leadInFrames);
}

/**
 * Interpolation-domain style.
 *
 * Returns the [start, end] domain to feed into `interpolate(t, ...)` so
 * the animation reaches its end value at `anchorMs` (or `anchorFrame`).
 *
 *   const range = leadInRange(tokenLocalMs, fadeDurationMs);
 *   const opacity = interpolate(pageLocalMs, range, [0, 1], { ... });
 */
export function leadInRange(
  anchor: number,
  duration: number,
): [number, number] {
  return [anchor - duration, anchor];
}
