import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface PillClusterProps extends MGTimingProps, MGPositionProps {
  // Keyword / hashtag labels. 4–10 read best.
  tags?: string[];
  // Single accent for the highlighted pills. Default "#4F9DF7".
  accentColor?: string;
  // Every Nth pill is accent-filled for rhythm (0 = none). Default 3.
  accentEvery?: number;
  // Frosted-glass pills vs flat dark pills. Default true.
  glass?: boolean;
  // Max cluster width before wrapping, in px. Default 900.
  width?: number;
  fontSize?: number; // Default 42.
  textColor?: string; // neutral pill text. Default "#FFFFFF".
  textShadow?: string;
}
