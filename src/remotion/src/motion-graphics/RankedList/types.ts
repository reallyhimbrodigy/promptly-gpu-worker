import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface RankedListItem {
  // Optional rank text (e.g. "1" or "01"). Falls back to the 1-based position.
  rank?: string;
  label: string;
  // Optional right-aligned value (e.g. "98%", "12.4K").
  value?: string;
}

export interface RankedListProps extends MGTimingProps, MGPositionProps {
  // Ordered rows, displayed top → bottom. 3–5 read best.
  items?: RankedListItem[];
  // Reveal order. "topDown" reveals #1 first; "bottomUp" saves #1 for last.
  order?: "topDown" | "bottomUp";
  // Emphasize the #1 row (accent numeral + glow bloom). Default true.
  highlightTop?: boolean;
  // Single accent. Default "#FFC53D".
  accentColor?: string;
  // Overall block width in px. Default 880.
  width?: number;
  rankFontSize?: number; // Default 116.
  labelColor?: string;
  valueColor?: string;
  textShadow?: string;
}
