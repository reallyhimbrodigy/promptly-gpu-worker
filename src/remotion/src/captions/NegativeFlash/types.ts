import type { CaptionStyleProps } from "../shared/types";

export interface NegativeFlashColorPreset {
  tintColor: string;
  burnColor: string;
  glowColor: string;
}

export const NEGATIVE_FLASH_PRESETS: Record<string, NegativeFlashColorPreset> = {
  red: { tintColor: "#FF8C5A", burnColor: "#F0A070", glowColor: "#FF8C5A" },
  blue: { tintColor: "#4DD9E8", burnColor: "#38C4D4", glowColor: "#4DD9E8" },
  green: { tintColor: "#00FF44", burnColor: "#00CC33", glowColor: "#00FF44" },
  purple: { tintColor: "#8800FF", burnColor: "#6600CC", glowColor: "#8800FF" },
  gold: { tintColor: "#FFD700", burnColor: "#CC9900", glowColor: "#FFD700" },
  cyan: { tintColor: "#00E5FF", burnColor: "#00B8CC", glowColor: "#00E5FF" },
};

export type NegativeFlashPresetName = keyof typeof NEGATIVE_FLASH_PRESETS;

export interface NegativeFlashProps extends CaptionStyleProps {
  maxWidthPercent?: number;
  maxWordsPerLine?: number;
  keywordScale?: number;
  /** Color preset for the negative flash effect. Default: "red" */
  colorPreset?: NegativeFlashPresetName;
}
