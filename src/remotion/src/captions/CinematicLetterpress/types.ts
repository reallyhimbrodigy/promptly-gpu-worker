import type { CaptionStyleProps } from "../shared/types";

export interface CinematicLetterpressProps extends CaptionStyleProps {
  /** Text color. Default: "#F5F0EB" (warm ivory) */
  textColor?: string;
  /** Letter spacing CSS value. Default: "0.12em" */
  letterSpacing?: string;
  /** Max gaussian blur in px at word start. Default: 8 */
  blurAmount?: number;
  /** Duration of blur-to-sharp transition per word in ms. Default: 200 */
  blurDurationMs?: number;
  /** Subtle scale animation on word entry. Default: true */
  enableScale?: boolean;
  /** Starting scale for word entry. Default: 0.95 */
  scaleFrom?: number;
  /** Text shadow for ambient readability. Default: wide diffuse */
  textShadow?: string;
  /** Max words per line before wrapping. Default: 3 */
  maxWordsPerLine?: number;
  /** Gap between lines in px. Default: 12 */
  lineGap?: number;
  /** Page exit blur duration in ms. Default: 250 */
  exitDurationMs?: number;
  /** Force lowercase text. Default: false (preserves original case) */
  lowercase?: boolean;
  /** Line height multiplier. Default: 1.2 */
  lineHeight?: number;
}
