import type { MGTimingProps } from "../shared/types";
import type { MGPositionProps } from "../shared/positioning";

export type EditorialQuoteFontKey =
  | "playfairDisplay"
  | "dmSerifDisplay"
  | "inter"
  | "oswald";

export interface EditorialQuoteProps extends MGTimingProps, MGPositionProps {
  // The quote sentence.
  text: string;
  author?: string; // attribution name.
  role?: string; // attribution sub-line (title / source).

  accentColor?: string; // left bar. Default "#FFD60A".
  textColor?: string; // Default "#FFFFFF".
  authorColor?: string; // role line. Default "rgba(255,255,255,0.7)".
  fontKey?: EditorialQuoteFontKey; // Default "playfairDisplay".
  fontSize?: number; // base px before auto-fit. Default 92.
  maxWordsPerLine?: number; // Default 3.
  italic?: boolean; // Default true.
  lineStagger?: number; // frames between line reveals. Default 8.
  showQuoteMark?: boolean; // big opening quote mark above the text. Default true.
}
