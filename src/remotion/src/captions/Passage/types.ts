import type { CaptionStyleProps } from "../shared/types";

export interface PassageProps extends CaptionStyleProps {
  /** Keywords — italicized, with tracking expansion on reveal. */
  keywords?: string[];
  /** Body text color. Default: "#F1EADB" (warm ivory) */
  textColor?: string;
  /** Keyword accent color. Default: "#D4A76A" (warm muted gold) */
  keywordColor?: string;
  /** Body font size in px. Default: 76 */
  fontSize?: number;
  /** Max words per line. Default: 5 */
  maxWordsPerLine?: number;
  /** Container max width as fraction of video width. Default: 0.78 */
  maxWidthPercent?: number;
  /** Gap between lines in px. Default: 16 */
  lineGap?: number;
  /** Gap between words in px. Default: 18 */
  wordGap?: number;
  /** Fade-in duration per word in ms. Default: 360 */
  fadeDurationMs?: number;
  /** Duration of the tracking expansion on keywords in ms. Default: 520 */
  trackingShiftDurationMs?: number;
  /** Starting letter-spacing for keywords (em). Default: -0.015 */
  keywordTrackingFrom?: number;
  /** Ending letter-spacing for keywords (em) — wider = louder. Default: 0.09 */
  keywordTrackingTo?: number;
  /** Letter-spacing for body text (em). Default: -0.005 */
  bodyTracking?: number;
  /** Line-height. Default: 1.12 */
  lineHeight?: number;
  /** Text shadow for readability over footage. Default: "0 2px 18px rgba(0,0,0,0.55)" */
  textShadow?: string;
}
