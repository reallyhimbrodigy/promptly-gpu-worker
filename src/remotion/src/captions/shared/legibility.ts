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
