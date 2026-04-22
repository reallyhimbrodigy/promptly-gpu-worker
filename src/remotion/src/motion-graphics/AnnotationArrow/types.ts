import type { MGTimingProps } from "../shared/types";

export interface AnnotationArrowProps extends MGTimingProps {
  // Start point of the arrow in pixel coordinates relative to the 1080x1920 frame.
  start: { x: number; y: number };
  // End point (the arrow tip) in pixel coordinates.
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
