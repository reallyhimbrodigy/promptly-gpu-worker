import type { CaptionStyleProps } from "../shared/types";

export interface GadzhiStyleProps extends CaptionStyleProps {
  /** Default text color. Default: "#FFFFFF" */
  textColor?: string;
  /** Keyword highlight color. Default: "#F5C518" */
  highlightColor?: string;
  /** Words that get the yellow highlight. Default: [] */
  keywords?: string[];
  /** Max words per line. Default: 2 */
  maxWordsPerLine?: number;
  /** Word gap in px. Default: 14 */
  wordGap?: number;
}
