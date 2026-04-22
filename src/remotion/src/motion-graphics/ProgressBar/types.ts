import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export interface ProgressBarMilestone {
  // Position along the track, 0–1 (e.g. 0.5 = halfway).
  at: number;
  // Optional small label above the marker.
  label?: string;
}

interface ProgressBarBase extends MGTimingProps, MGPositionProps {
  label?: string;
  width?: number;
  trackHeight?: number;
  // Color of the progress fill itself. Default "#FFFFFF" — white reads on
  // any footage and stays out of the way of brand color elsewhere.
  fillColor?: string;
  // Accent for the eyebrow label + hairline rule. Default "#D4A12A"
  // (warm gold — reads as "money/wealth" on revenue-goal trackers).
  accentColor?: string;
  trackColor?: string;
  milestones?: ProgressBarMilestone[];
  // Override the right-side counter text (receives current numeric value during count-up).
  formatValue?: (current: number) => string;
  // Override the drop shadow used on the large hero value. Pass "" to
  // disable. Default is a two-stop shadow tuned for video backgrounds.
  textShadowLarge?: string;
  // Override the drop shadow used on small text (eyebrow, milestone labels).
  textShadowSmall?: string;
}

export interface ProgressBarValueProps extends ProgressBarBase {
  // Drive the bar from value/total. Right-side counter will display
  // `${formatValue(value)} / ${formatValue(total)}` by default.
  value: number;
  total: number;
  percentage?: never;
}

export interface ProgressBarPercentProps extends ProgressBarBase {
  // Drive the bar from a 0–100 percentage. Right-side counter will display
  // `${Math.round(current)}%` by default.
  percentage: number;
  value?: never;
  total?: never;
}

export type ProgressBarProps = ProgressBarValueProps | ProgressBarPercentProps;
