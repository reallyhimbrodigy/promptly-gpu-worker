import type { CaptionStyleProps } from "../shared/types";

export interface EditorialPopProps extends CaptionStyleProps {
  /** Words that get the bold-italic pop treatment. */
  keywords?: string[];
  /** Base font size for filler words. Default: 62 */
  fontSize?: number;
  /** Scale multiplier for keyword text. Default: 1.35 */
  keywordScale?: number;
  /** Text color (all white by default). Default: "#FFFFFF" */
  textColor?: string;
  /** Max words per line before splitting. Default: 3 */
  maxWordsPerLine?: number;
}
