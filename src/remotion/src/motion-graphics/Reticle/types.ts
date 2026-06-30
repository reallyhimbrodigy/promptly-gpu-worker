import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface ReticleProps extends MGTimingProps, MGPositionProps {
  // Tag text shown at the top-left corner. Omit to hide the tag.
  label?: string;
  // Region marked by the corner brackets, in px.
  regionWidth?: number; // Default 620.
  regionHeight?: number; // Default 720.
  // Bracket color before lock. Default "#FFFFFF".
  bracketColor?: string;
  // Accent shown on lock (brackets + tag). Default "#36E27A".
  accentColor?: string;
  // Sweep a thin scanline down the region once. Default true.
  showScanline?: boolean;
  // Show a small center crosshair tick. Default false.
  showCrosshair?: boolean;
  // Corner bracket arm length / thickness in px.
  armLength?: number; // Default 64.
  thickness?: number; // Default 5.
  textShadow?: string;
}
