import type { CaptionStyleProps } from "../shared/types";

export interface CleanCutProps extends CaptionStyleProps {
  textColor?: string; // Default "#FFFFFF".
  fontFamily?: string; // Default Inter.
  fontSize?: number; // Default 100.
  fontWeight?: number | string; // Default 800.
  position?: "top" | "center" | "bottom";
  allCaps?: boolean; // Default false (deliberately plain).
  // Legibility shadow.
  textShadow?: string;
}
