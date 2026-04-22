import type { CaptionStyleProps } from "../shared/types";

export interface PrismProps extends CaptionStyleProps {
  maxWidthPercent?: number;
  maxWordsPerLine?: number;
  keywordScale?: number;
  /** Scale for keywords when alone on a line. Default: 2.2 */
  soloKeywordScale?: number;
}
