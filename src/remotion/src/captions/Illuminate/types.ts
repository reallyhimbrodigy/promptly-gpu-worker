import type { CaptionStyleProps } from "../shared/types";

export interface IlluminateProps extends CaptionStyleProps {
  /** Words that get the golden glow treatment. Default: [] */
  keywords?: string[];
  /** Font size in px. Default: 58 */
  fontSize?: number;
  /** Text color. Default: "#FFFFFF" */
  textColor?: string;
  /** Glow color for keywords. Default: "#D4A853" */
  glowColor?: string;
  /** Max words per line. Default: 3 */
  maxWordsPerLine?: number;
}
