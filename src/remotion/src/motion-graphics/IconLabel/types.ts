import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type IconName =
  | "check"
  | "bolt"
  | "star"
  | "dollar"
  | "arrow-up"
  | "fire"
  | "heart"
  | "clock"
  | "lock"
  | "trophy"
  | "target"
  | "chart-up"
  | "sparkle"
  | "x";

export type IconLabelLayout = "row" | "stack";
export type IconLabelFontKey = "inter" | "anton" | "oswald";

export interface IconLabelProps extends MGTimingProps, MGPositionProps {
  icon: IconName; // required
  label?: string; // optional → icon-only mode
  layout?: IconLabelLayout; // Default "row".
  iconColor?: string; // Default "#FFFFFF".
  labelColor?: string; // Default "#FFFFFF".
  fontKey?: IconLabelFontKey; // Default "inter".
  fontSize?: number; // Default 56.
  iconSize?: number; // rendered px. Default 96.
  strokeWidth?: number; // 24-grid units. Default 2.
  showPill?: boolean; // soft chip behind icon+label. Default false.
  pillColor?: string; // Default "rgba(18,18,22,0.5)".
  showRing?: boolean; // radiating ping ring on entrance. Default true.
  ringColor?: string; // Default = iconColor.
  textShadow?: string;
  idle?: boolean; // subtle icon breath during hold. Default false.
}
