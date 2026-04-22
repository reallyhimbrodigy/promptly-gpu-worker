import type { CaptionStyleProps } from "../shared/types";

export interface CoveProps extends CaptionStyleProps {
  /** Words that get the black box treatment (matched case-insensitive). */
  boxedWords?: string[];
  /** Horizontal padding inside black box (px). Default: 14 */
  boxPaddingX?: number;
  /** Vertical padding inside black box (px). Default: 8 */
  boxPaddingY?: number;
  /** Max words per line. Default: 4 */
  maxWordsPerLine?: number;
  /** Gap between lines (px). Default: 14 */
  lineGap?: number;
  /** Gap between words in a line (px). Default: 14 */
  wordGap?: number;
}
