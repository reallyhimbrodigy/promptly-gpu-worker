import type { MGTimingProps } from "../shared/types";

export type PillMarqueeFontKey = "inter" | "oswald";

// Full-width marquee band centered on the frame — it owns its horizontal layout
// (no anchor/offsetX/scale); nudge it vertically with offsetY.
export interface PillMarqueeProps extends MGTimingProps {
  // Tags streamed across the rows (distributed + looped).
  pills: string[];
  rows?: number; // number of marquee rows. Default 3.
  hashtag?: boolean; // prefix each with "#". Default true.
  speed?: number; // scroll px per frame @60fps. Default 2.2.
  firstDirection?: 1 | -1; // top row direction; alternates down. Default 1 (L→R).

  fontKey?: PillMarqueeFontKey; // Default "inter".
  fontSize?: number; // Default 46.
  uppercase?: boolean;
  textColor?: string; // Default "#FFFFFF".
  colorMode?: "single" | "varied"; // Default "single".
  accentColor?: string; // "single" mode border / "#". Default "#FF6A3D".
  palette?: string[]; // "varied" mode colors.
  pillColor?: string; // "single" mode fill. Default neutral dark.
  glass?: boolean; // light backdrop blur. Default true.

  gap?: number; // gap between pills in a row. Default 18.
  rowGap?: number; // gap between rows. Default 24.
  paddingX?: number; // Default 34.
  paddingY?: number; // Default 20.
  edgeFade?: number; // edge fade width in px. Default 200.
  offsetY?: number; // vertical nudge of the whole band, px. Default 0.
}
