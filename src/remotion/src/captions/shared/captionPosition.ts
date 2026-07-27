import {
  TIKTOK_SAFE_TOP,
  TIKTOK_SAFE_RIGHT,
  TIKTOK_SAFE_BOTTOM,
  TIKTOK_SAFE_SIDE,
} from "../../shared/safeZone";

// Caption padding box = the TikTok-safe rect (single source of truth in
// src/shared/safeZone.ts). The padding fully bounds the wrapped text, so
// captions can never render under the platform header, the right action
// rail, or the bottom caption/progress/nav drawer.
//
// Key names are kept for the other caption styles that consume them
// (Cove / CinematicLetterpress / Prime) as absolute top/left/right/bottom
// offsets — only the VALUES are raised to the safe rect. `sidesSafe` (200)
// is used on BOTH sides so caption text stays horizontally centered
// (center x = 540) while clearing the right rail; 200 left is more inset
// than the rect's 80 minimum, but over-inset is invisible and keeps
// captions centered rather than shifted left.
export const CAPTION_PADDING = {
  top: TIKTOK_SAFE_TOP, // 270 — clears the top header
  sides: TIKTOK_SAFE_SIDE, // 80  — general/left inset
  bottomSafe: TIKTOK_SAFE_BOTTOM, // 420 — clears the caption/progress/nav drawer
  sidesSafe: TIKTOK_SAFE_RIGHT, // 200 — clears the right action rail
} as const;

export function getCaptionPositionStyle(
  position: "top" | "center" | "bottom",
  anchor?: { topPx: number },
): React.CSSProperties {
  // SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): when a per-page anchor is
  // present it OVERRIDES the fixed vertical slot — the block is flex-start-pinned
  // at `topPx` (constant per page → the render snaps between pages, never slides,
  // so FRAME-1-IS-FINAL holds). Horizontal padding is unchanged (captions stay
  // centred, clear of the right action rail). Undefined anchor → the switch below
  // runs exactly as before (byte-identical fixed-slot behavior).
  if (anchor) {
    return {
      justifyContent: "flex-start",
      paddingTop: anchor.topPx,
      paddingLeft: CAPTION_PADDING.sidesSafe,
      paddingRight: CAPTION_PADDING.sidesSafe,
    };
  }
  switch (position) {
    case "top":
      return {
        justifyContent: "flex-start",
        paddingTop: CAPTION_PADDING.top,
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe,
      };
    case "bottom":
      return {
        justifyContent: "flex-end",
        paddingBottom: CAPTION_PADDING.bottomSafe,
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe,
      };
    case "center":
    default:
      return {
        justifyContent: "center",
        paddingLeft: CAPTION_PADDING.sidesSafe,
        paddingRight: CAPTION_PADDING.sidesSafe,
      };
  }
}
