import type { CaptionStyleProps } from "../shared/types";

export interface MagazineCutoutProps extends CaptionStyleProps {
  /** Base background color for each cutout piece — default "#FDF8F0" */
  cutoutBg?: string;
  /** Text ink color — default "#0D0D0D" */
  inkColor?: string;
  /** Max random rotation in degrees (±) per word — default 6 */
  maxRotation?: number;
  /** Max font size variation in px (±) — default 10 */
  sizeVariation?: number;
  /** Horizontal padding inside each cutout — default 14 */
  cutoutPaddingX?: number;
  /** Vertical padding inside each cutout — default 8 */
  cutoutPaddingY?: number;
  /** All caps — default true */
  allCaps?: boolean;
  /** Max words per line — default 3 */
  maxWordsPerLine?: number;
  /** Gap between lines — default 18 */
  lineGap?: number;
  /** Gap between word cutouts — default 12 */
  wordGap?: number;
}
