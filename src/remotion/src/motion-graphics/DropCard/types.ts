import type { MGTimingProps } from "../shared/types";

export interface DropCardStep {
  // Tiny label under the numbered circle (e.g. "Hook").
  label?: string;
}

export interface DropCardPoint {
  // Accent-colored point title, e.g. "1. The Missing Piece".
  title: string;
  // Caption sentence; highlights word-by-word (grey -> black) when active.
  caption: string;
}

// Fixed floating card pinned near the top of the frame — like StickyNotes it
// owns its placement (no anchor/offset/scale); tune footprint via cardHeightPct.
export interface DropCardProps extends MGTimingProps {
  // --- Slide 1 (the numbered intro) ---
  title: string;
  // Highlighted leading token shown in the accent color, e.g. "3".
  titleLead?: string;
  subtitle?: string;
  // Numbered circles with labels; the number is its 1-based index. Default 3.
  steps?: DropCardStep[];

  // --- Caption slides, one per numbered point ---
  points?: DropCardPoint[];

  cardColor?: string; // Default "#FFFFFF".
  titleColor?: string; // intro title. Default "#15151E".
  subtitleColor?: string; // Default "#5A5A5A".
  labelColor?: string; // under-circle labels. Default "#2A2A30".
  accentColor?: string; // ring + number + rail + point titles. Default "#F5A11E".
  railColor?: string; // dashed stepper rail. Defaults to accentColor.
  spokenColor?: string; // a word once "said". Default "#15151E" (black).
  mutedColor?: string; // a word not yet said. Default "#C2C2CA" (grey).
  // Card height as a fraction of the frame (fixed viewport). Default 0.5.
  cardHeightPct?: number;
}
