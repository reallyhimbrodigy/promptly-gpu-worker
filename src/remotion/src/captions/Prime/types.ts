import type { CaptionStyleProps } from "../shared/types";

export interface PrimeProps extends CaptionStyleProps {
  /** Color of line 1 / top line (default: "#FFFFFF") */
  line1Color?: string;
  /** Color of line 2 / bottom line (default: "#3BA5FF") */
  line2Color?: string;
  /** Font size of line 1 in px (default: 52) */
  line1FontSize?: number;
  /** Font size of line 2 in px (default: 66) */
  line2FontSize?: number;
  /** Font weight of line 1 (default: 600) */
  line1FontWeight?: number | string;
  /** Font weight of line 2 (default: 800) */
  line2FontWeight?: number | string;
  /** Max words per line (default: 3) */
  maxWordsPerLine?: number;
  /** CSS letter-spacing (default: "0.01em") */
  letterSpacing?: string;
  /** Gap between lines in px (default: 12) */
  lineGap?: number;
  /** Text shadow for readability (default: "0 2px 8px rgba(0,0,0,0.7), 0 0 4px rgba(0,0,0,0.4)") */
  textShadow?: string;
  /** Words displayed in italic serif font (case-insensitive match) */
  specialWords?: string[];
  /** Font family for special words (default: playfairDisplay) */
  specialFontFamily?: string;
  /** Color for special words (default: "#5ED4E8") */
  specialColor?: string;
}
