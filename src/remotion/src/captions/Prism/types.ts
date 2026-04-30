import type { CaptionStyleProps } from "../shared/types";

export interface PrismProps extends CaptionStyleProps {
  maxWidthPercent?: number;
  maxWordsPerLine?: number;
  keywordScale?: number;
  /** Scale for keywords when alone on a line. Default: 2.2 */
  soloKeywordScale?: number;
  /** Words that get the prism highlight. When provided (non-empty),
   *  drives the per-word highlight check instead of the bundled static
   *  dictionary. Empty / undefined falls back to the static dictionary. */
  keywords?: string[];
}
