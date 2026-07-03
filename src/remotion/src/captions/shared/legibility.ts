// Caption legibility floor — single source of truth for the minimum contrast
// treatment caption body text must carry over arbitrary footage (white
// shirts, sky, blown-out windows). A style meets the floor with any ONE of:
//   • a solid box / word-shaped scrim behind the text
//     (PaperII strip; Cove / Quintessence blurred word-copies)
//   • a dark contour ≥ 2px — WebkitTextStroke or 0-blur offset shadows
//     (NeonStripe 4.2px, TwoTone 3px)
//   • a tight anchor shadow: blur ≤ 8px, offset ≤ 4px, dark alpha ≥ 0.55
//     (Prime, Spectrum, CleanCut, TypewriterReveal)
// Styles that only had wide diffusion (blur ≥ 10px) PREPEND the anchor
// layers below to their own diffusion. Never add the anchor to a stack that
// already meets the floor — that double-darkens.
//
//   "0 0 2px rgba(0,0,0,0.75)" — 0-offset 2px blur hugs the glyph on all
//     sides: the shadow equivalent of a ~1px soft outline, without the hard
//     vector edge of WebkitTextStroke (Lumen's design is outline-free).
//   "0 2px 6px rgba(0,0,0,0.85)" — tight directional drop, calibrated
//     between TypewriterReveal's 0 2px 4px @0.9 (strongest tight layer in
//     the pack) and CleanCut's 0 2px 6px @0.55.
// validate_deploy.py pins these numbers and requires every style directory
// to be classified as importer or exempt.
export const LEGIBILITY_ANCHOR_LAYERS = [
  "0 0 2px rgba(0,0,0,0.75)",
  "0 2px 6px rgba(0,0,0,0.85)",
] as const;

export const LEGIBILITY_ANCHOR = LEGIBILITY_ANCHOR_LAYERS.join(", ");

/** Prepend the floor anchor to a style's own diffusion stack. */
export const withLegibilityAnchor = (diffusion: string): string =>
  diffusion ? `${LEGIBILITY_ANCHOR}, ${diffusion}` : LEGIBILITY_ANCHOR;

// ── Emphasis-keyword contrast floor (B3 · directive #11) ────────────────────
// D3 numbers (render C, Lumen amber #D4A24C over warm granite): keyword-vs-
// band contrast measured 1.22–1.32:1 — Δluma only +15..+20 of 255. Warm
// keyword fills over warm surfaces read as texture. The step-up triggers when
// the keyword color's luma sits within KEYWORD_CONTRAST_TRIGGER of the
// measured caption-band luma (delivered per-video as extraProps.bandLuma).
export const KEYWORD_CONTRAST_TRIGGER = 40; // 0-255 luma units
export const KEYWORD_CONTRAST_LAYERS = [
  "0 0 1px rgba(20,12,4,0.95)",
  "0 0 3px rgba(20,12,4,0.9)",
  "0 2px 5px rgba(0,0,0,0.9)",
] as const;
// Stronger second step for a triggered convergence (auto step-up).
export const KEYWORD_CONTRAST_STEPUP_LAYERS = [
  "0 0 2px rgba(10,6,2,0.95)",
  "0 0 5px rgba(10,6,2,0.9)",
  "0 3px 7px rgba(0,0,0,0.95)",
] as const;

export const lumaOf = (hex: string): number => {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return 128;
  const v = parseInt(m[1], 16);
  const r = (v >> 16) & 255, g = (v >> 8) & 255, b = v & 255;
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

/** Auto step-up: extra dark layers when keyword color converges with the
 * measured band luma. Empty when band luma is unknown (fail-open). */
export const keywordContrastShadow = (
  keywordColor: string,
  bandLuma?: number,
): string[] =>
  bandLuma !== undefined &&
  Math.abs(lumaOf(keywordColor) - bandLuma) < KEYWORD_CONTRAST_TRIGGER
    ? [...KEYWORD_CONTRAST_STEPUP_LAYERS]
    : [];
