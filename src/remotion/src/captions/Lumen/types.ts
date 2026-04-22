import type { CaptionStyleProps } from "../shared/types";

export interface LumenProps extends CaptionStyleProps {
  /** Keywords that get the amber glow + serif switch. */
  keywords?: string[];
  /** Words that get the shine sweep + gold underline (subset of keywords). */
  shineWords?: string[];
  /** Max words per line. Default: 4 */
  maxWordsPerLine?: number;
  /** Line gap. Default: 0 */
  lineGap?: number;
  /** Word gap. Default: 14 */
  wordGap?: number;
  /** Normal text color. Default: "#FFFFFF" */
  textColor?: string;
  /** Keyword amber/gold color. Default: "#D4A24C" */
  keywordColor?: string;
  /** Duration of brightness flash on keywords in frames. Default: 15 */
  sweepDuration?: number;
}
