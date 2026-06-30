import type { CaptionStyleProps } from "../shared/types";

export interface TwoToneProps extends CaptionStyleProps {
  // Top line color. Default "#FFFFFF".
  topColor?: string;
  // Bottom line color (the accent). Default "#FFD23F".
  accentColor?: string;
  // Heavy display font. Default Montserrat.
  fontFamily?: string;
  fontSize?: number; // Default 132.
  position?: "top" | "center" | "bottom";
  // Outline width / color for legibility over footage.
  strokeWidth?: number; // Default 7.
  strokeColor?: string; // Default "#000000".
  // Uppercase the words. Default true.
  allCaps?: boolean;
}
