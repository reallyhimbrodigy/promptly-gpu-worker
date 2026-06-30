import type { MGTimingProps } from "../shared/types";

export interface DropBannerPoint {
  // Orange point title, e.g. "1. The Missing Piece".
  title: string;
  // Caption sentence; highlights word-by-word (grey -> black) when active.
  caption: string;
}

// Fixed full-width banner pinned to the top of the frame — like StickyNotes it
// owns its placement (no anchor/offset/scale); tune footprint via cardHeightPct.
export interface DropBannerProps extends MGTimingProps {
  // --- Slide 1 (the numbered intro) ---
  title: string;
  subtitle?: string;
  count?: number; // amber number-circles (1..count). Default 3.

  // --- Caption slides, one per numbered point ---
  points?: DropBannerPoint[];

  cardColor?: string; // Default "#FFFFFF".
  titleColor?: string; // intro title. Default "#15151E".
  subtitleColor?: string; // Default "#5A5A5A".
  accentColor?: string; // rings + point titles. Default "#F5A11E".
  spokenColor?: string; // a word once "said". Default "#15151E" (black).
  mutedColor?: string; // a word not yet said. Default "#C2C2CA" (grey).
  // Banner height as a fraction of the frame (top-pinned). Default 0.47.
  cardHeightPct?: number;
}
