import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type NumberTickerIcon = "none" | "coin";

export interface NumberTickerProps extends MGTimingProps, MGPositionProps {
  // Target value the digits roll up to.
  value: number;
  // Start value for the roll. Default 0.
  fromValue?: number;
  // Small prefix before the number (e.g. "$"). Optional.
  prefix?: string;
  // Small suffix after the number (e.g. "+", "%", "K", "M"). Optional.
  suffix?: string;
  // Built-in premium icon to the left of the number inside the pill. Default "none".
  icon?: NumberTickerIcon;
  // Decimal places. Default 0.
  decimals?: number;
  // Thousands separators (12,000). Default true.
  grouping?: boolean;
  // Subtle breathing "live" glow on the pill. Default true.
  live?: boolean;
  // Live-glow tint on the pill. Default "#FFFFFF".
  accentColor?: string;
  // Digit + separator + affix color. Default "#FFFFFF".
  digitColor?: string;
  // Frosted glass pill container behind the number. Default true.
  chip?: boolean;
  // Glass pill fill (translucent; only used when chip=true). Default "rgba(17,19,25,0.30)".
  chipColor?: string;
  // Override roll length in frames @60fps. Default 42.
  rollFrames?: number;
  // Override digit/affix drop shadow. Pass "" to disable.
  textShadow?: string;
}
