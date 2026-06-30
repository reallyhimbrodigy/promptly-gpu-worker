import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type StepDividerFontKey = "anton" | "oswald" | "inter";

export interface StepDividerProps extends MGTimingProps, MGPositionProps {
  title: string; // supports "\n" for multiple lines
  step?: number; // current step (1-based). Default 1.
  totalSteps?: number; // Default 5.
  kicker?: string; // word before the number, e.g. "STEP". Default "STEP".
  showProgress?: boolean; // segmented progress bar. Default true.
  showCount?: boolean; // "/ 05" total in the kicker. Default true.

  fontKey?: StepDividerFontKey; // title face. Default "anton".
  titleFontSize?: number; // Default 122.
  uppercase?: boolean; // title uppercase. Default true.
  titleColor?: string; // Default "#FFFFFF".
  kickerColor?: string; // Default "#FFFFFF".
  accentColor?: string; // progress + step number. Default "#4F9DF7".
}
