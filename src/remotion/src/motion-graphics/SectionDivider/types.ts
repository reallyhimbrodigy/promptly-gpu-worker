import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type SectionDividerFontKey =
  | "anton"
  | "dmSerifDisplay"
  | "playfairDisplay"
  | "oswald";

export interface SectionDividerProps extends MGTimingProps, MGPositionProps {
  // Title text. "\n" splits into separately-revealed lines (1–2 recommended).
  title: string;
  // Eyebrow kicker above the title, e.g. "PART ONE". Omit to hide.
  label?: string;
  // Optional giant index, e.g. "01" (string preserves the leading zero).
  number?: string;
  fontKey?: SectionDividerFontKey; // Default "anton".
  align?: "center" | "left"; // Default "center".
  variant?: "full" | "band"; // Default "full".
  titleColor?: string; // Default "#FFFFFF".
  accentColor?: string; // rule color. Default "#C8551F".
  eyebrowColor?: string; // Default = accentColor.
  numberColor?: string; // Default = accentColor.
  titleFontSize?: number; // Default 150.
  showRule?: boolean; // Default true.
  showScrim?: boolean; // Default true.
  scrimColor?: string; // Default "rgba(0,0,0,0.55)".
  showVignette?: boolean; // darken all 4 corners. Default true.
  vignetteStrength?: number; // 0–1 corner darkness. Default 0.6.
  textShadow?: string;
}
