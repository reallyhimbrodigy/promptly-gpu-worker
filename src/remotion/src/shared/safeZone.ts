// ---------------------------------------------------------------------------
// TikTok UI safe-zone — SINGLE SOURCE OF TRUTH.
// ---------------------------------------------------------------------------
//
// When Promptly's output is posted to TikTok, the platform paints its own UI
// over the video and covers anything placed underneath it:
//   - top:    clock + header
//   - right:  like / comment / share / bookmark action rail
//   - bottom: caption text + progress bar + nav
//
// Both the motion-graphic resolver (motion-graphics/shared/positioning.ts)
// and the caption resolver (captions/shared/captionPosition.ts) import these
// constants and clamp every position into the safe rect — so Gemini can never
// emit coordinates that land under the platform chrome. Geometry has one
// correct answer; it belongs here in code, not in the prompt.
//
// The values are padded ~15-20% over the screenshot-measured TikTok UI on
// purpose: clipping is a VISIBLE failure, over-inset is INVISIBLE, so we pad
// toward the invisible one. Tightening the safe area later is a one-line edit
// in this file and nowhere else.

export const CANVAS_WIDTH = 1080;
export const CANVAS_HEIGHT = 1920;

export const TIKTOK_SAFE_TOP = 270; // clock + header
export const TIKTOK_SAFE_RIGHT = 200; // like/comment/share/bookmark action rail
export const TIKTOK_SAFE_BOTTOM = 420; // caption text + progress bar + nav
export const TIKTOK_SAFE_SIDE = 80; // left + general side inset

// Derived safe rectangle on the 1080×1920 canvas: x ∈ [80, 880], y ∈ [270, 1500].
export const SAFE_RECT = {
  x: TIKTOK_SAFE_SIDE, // 80
  y: TIKTOK_SAFE_TOP, // 270
  width: CANVAS_WIDTH - TIKTOK_SAFE_SIDE - TIKTOK_SAFE_RIGHT, // 800
  height: CANVAS_HEIGHT - TIKTOK_SAFE_TOP - TIKTOK_SAFE_BOTTOM, // 1230
} as const;
