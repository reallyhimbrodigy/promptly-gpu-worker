import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface MouseDragProps extends MGTimingProps, MGPositionProps {
  label: string; // the dragged card text, e.g. "Lace Quick Fix"

  cardColor?: string; // card fill. Default "#F2C211".
  cardTextColor?: string; // Default "#1C1C1C".

  regionWidth?: number; // Default 720.
  regionHeight?: number; // Default 360.
  showCursor?: boolean; // Default true.
}
