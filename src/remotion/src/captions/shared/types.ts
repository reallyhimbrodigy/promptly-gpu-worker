import type { TikTokToken, TikTokPage } from "@remotion/captions";

export type { TikTokToken, TikTokPage };

/**
 * SPEAKER-FOLLOWING CAPTIONS (Zac 2026-07-26, DARK): per-page vertical anchor.
 * `topPx` is the caption block's top in canonical 1080x1920 canvas px. When
 * present, a style pins its block there (via getCaptionPositionStyle or its own
 * anchor branch) instead of using the fixed `position` slot. Absent → today's
 * fixed-slot behavior, byte-identical.
 */
export interface CaptionAnchor {
  topPx: number;
}

export interface CaptionStyleProps {
  pages: TikTokPage[];
  fontFamily?: string;
  fontSize?: number;
  fontWeight?: number | string;
  primaryColor?: string;
  secondaryColor?: string;
  position?: "top" | "center" | "bottom";
  /** Speaker-follow per-page anchor (DARK unless PROMPTLY_SPEAKER_CAPTIONS). */
  anchor?: CaptionAnchor;
  strokeColor?: string;
  strokeWidth?: number;
}
