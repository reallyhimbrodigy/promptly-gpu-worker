import type { MGTimingProps } from "../shared/types";

export interface AnnotationArrowProps extends MGTimingProps {
  // Start point of the arrow as NORMALIZED fractions of the frame:
  // x, y ∈ [0, 1] with (0,0) = top-left, (1,1) = bottom-right. The component
  // converts to canvas pixels and clamps each endpoint into the TikTok-safe
  // rect (see resolveEndpoints.ts) — the same rect other MGs are padded into.
  start: { x: number; y: number };
  // End point (the arrow tip), normalized 0-1 like `start`.
  end: { x: number; y: number };
  // Preset shape. "custom" requires `customPath`.
  pathType?: "straight" | "curved-arc" | "j-shape" | "custom";
  // Caller-provided SVG `d` attribute. Required when `pathType === "custom"`.
  customPath?: string;
  // Stroke color. Default "#C8551F" (rust — matches the kit accent).
  color?: string;
  // Stroke width in pixels. Default 8.
  strokeWidth?: number;
  // Deterministic seed for the hand-drawn jitter. Same seed → same arrow.
  seed?: number;
  // Arrowhead chevron length in pixels. Default 32.
  arrowheadSize?: number;
}
