import type { CaptionStyleProps } from "../shared/types";

export interface NeonStripeProps extends CaptionStyleProps {
  // Bright neon used for the stripe band, edge and glow. Default "#39FF14".
  neonColor?: string;
  // Dark texture line over the neon fill. Default "#04210A".
  stripeColor?: string;
  // Line spacing as a fraction of font size. Default 0.05 (fine, ~5px at 104pt).
  stripeWidth?: number;
  // Vertical drift of the stripes, px/frame at 30fps (fps-normalized). 0 = static. Default 0.25.
  stripeScrollSpeed?: number;
  fontFamily?: string; // Default Montserrat.
  fontSize?: number; // Default 104.
  position?: "top" | "center" | "bottom";
  maxWordsPerLine?: number; // Default 3.
  // Keywords get a size bump + a hotter glow.
  keywords?: string[];
  allCaps?: boolean; // Default true.
}
