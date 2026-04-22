import type { CaptionStyleProps } from "../shared/types";

export interface PaperIIHighlightWord {
  text: string;
  color: string;
}

export interface PaperIIProps extends CaptionStyleProps {
  /** Background color of the strip (default: "transparent") */
  paperColor?: string;
  /** Color for words not yet spoken (default: "rgba(255,255,255,0.45)") */
  upcomingColor?: string;
  /** Color for the currently active and past words (default: "#FFFFFF") */
  activeColor?: string;
  /** Max words per strip line (default: 4) */
  maxWordsPerLine?: number;
  /** Display text in all caps (default: false) */
  allCaps?: boolean;
  /** CSS letter-spacing value (default: "-0.01em") */
  letterSpacing?: string;
  /** Horizontal padding inside each strip in px (default: 0) */
  stripPaddingX?: number;
  /** Vertical padding inside each strip in px (default: 0) */
  stripPaddingY?: number;
  /** Vertical gap between stacked strips in px (default: 10) */
  stripGap?: number;
  /** Border radius in px (default: 0) */
  borderRadius?: number;
  /** Duration of color transition per word in ms (default: 60) */
  colorTransitionMs?: number;
  /** Text shadow for readability (default: heavy shadow) */
  textShadow?: string;
}
