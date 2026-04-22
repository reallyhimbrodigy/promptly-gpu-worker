import type { MGTimingProps } from "../shared/types";

export interface TornPaperProps extends MGTimingProps {
  // Top slammed strip text.
  topText: string;
  // Bottom slammed strip text.
  bottomText: string;
  // Rotation in degrees applied to each strip at rest. Defaults -10 / +7.
  topStripRotation?: number;
  bottomStripRotation?: number;
  // Strip block color + text color.
  stripColor?: string;
  stripTextColor?: string;
  // Hard offset shadow color (the colored block behind each strip).
  shadowColor?: string;
  shadowOffsetX?: number;
  shadowOffsetY?: number;
  // Strip font.
  stripFontFamily?: string;
  stripFontSize?: number;
  stripFontWeight?: number | string;
  stripLetterSpacing?: string;
  // Strip padding [vertical, horizontal].
  stripPadding?: [number, number];
  // Gap between the two strips.
  stripGap?: number;
  // Vertical area height the strips live inside (top of frame). Default "25%".
  stripsPositionTop?: string;
}
