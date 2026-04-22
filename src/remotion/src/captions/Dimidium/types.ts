import type { CaptionStyleProps } from "../shared/types";

export interface DimidiumProps extends CaptionStyleProps {
  /** Color for normal words. Default: "#FFFFFF" */
  color?: string;
  /** Color for highlighted keywords. Default: "#E8D44D" */
  highlightColor?: string;
  /** Words to highlight in yellow. */
  highlightWords?: string[];
  /** Max words per line. Default: 3 */
  maxWordsPerLine?: number;
  /** Line gap in px. Default: 8 */
  lineGap?: number;
}
