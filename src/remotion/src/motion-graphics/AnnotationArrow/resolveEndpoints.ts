import { SAFE_RECT } from "../../shared/safeZone";

// ---------------------------------------------------------------------------
// Normalized 0-1 → canvas-pixel endpoint resolution for AnnotationArrow.
// ---------------------------------------------------------------------------
//
// Gemini emits `start`/`end` as NORMALIZED fractions of the frame (the
// handler.py prompt teaches {"x": 0.0-1.0, "y": 0.0-1.0}) and the props reach
// this component untouched — this is the single seam where fractions become
// pixels. Kept a pure function (no Remotion hooks) so the pre-deploy gate
// (validate_deploy.py "AnnotationArrow: normalized 0-1 endpoints…") can
// mirror the math offline and pin it.
//
// Two clamps, in order:
//   (1) defensive input clamp to [0, 1] — a model that regresses to pixel
//       coordinates (e.g. x: 540) lands on the frame edge instead of
//       resolving to 540 × canvas-width off-screen;
//   (2) safe-rect clamp — AnnotationArrow is the ONLY coordinate-positioned
//       MG (it never routes through resolveMGPosition; see
//       shared/positioning.ts), so the nearest equivalent of the resolver's
//       padding box is applied directly to each endpoint: both land inside
//       the same TikTok-safe rect every other MG is padded into
//       (x ∈ [80, 880], y ∈ [270, 1500] on the 1080×1920 canvas).

export interface ArrowPoint {
  x: number;
  y: number;
}

const clamp = (v: number, lo: number, hi: number): number =>
  Math.max(lo, Math.min(hi, v));

export function resolveArrowEndpoint(
  pt: ArrowPoint,
  width: number,
  height: number,
): ArrowPoint {
  const px = clamp(pt.x, 0, 1) * width;
  const py = clamp(pt.y, 0, 1) * height;
  return {
    x: clamp(px, SAFE_RECT.x, SAFE_RECT.x + SAFE_RECT.width),
    y: clamp(py, SAFE_RECT.y, SAFE_RECT.y + SAFE_RECT.height),
  };
}
