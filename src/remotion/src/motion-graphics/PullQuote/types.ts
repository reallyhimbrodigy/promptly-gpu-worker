import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type PullQuoteHighlightStyle = "color" | "bar" | "scale";
export type PullQuoteAlign = "left" | "center" | "right";
export type PullQuoteFontKey =
  | "anton"
  | "oswald"
  | "inter"
  | "roboto"
  | "dmSerifDisplay"
  | "playfairDisplay";

export interface PullQuoteProps extends MGTimingProps, MGPositionProps {
  // The speaker's spoken line, rendered huge.
  text: string;
  // Words to emphasize (case- & punctuation-insensitive match).
  keywords?: string[];
  textColor?: string; // Default "#FFFFFF".
  keywordColor?: string; // Default "#FFD60A".
  accentColor?: string; // alias for keywordColor.
  fontKey?: PullQuoteFontKey; // Default "anton".
  fontSize?: number; // base px before auto-fit. Default 150.
  maxWordsPerLine?: number | null; // Default 3 (null → width-wrap).
  highlightStyle?: PullQuoteHighlightStyle; // Default "color".
  keywordScale?: number; // keyword size multiplier. Default 1.18.
  barColor?: string; // "bar" mode. Default = keywordColor.
  highlightTextColor?: string; // keyword ink on bar. Default "#0A0A0A".
  align?: PullQuoteAlign; // Default "center".
  uppercase?: boolean; // Default true.
  wordStagger?: number; // frames @60fps. Default 6.
  wordReveal?: number; // frames @60fps. Default 16.
  blurIn?: boolean; // Default true.
  showQuoteMark?: boolean; // big decorative opening quote. Default false (spec: pull-quote has no quote mark).
  quoteMarkColor?: string; // Default = keywordColor.
  textShadow?: string;
}
