import type { CaptionStyleProps } from "../shared/types";

export interface StaggerWaveProps extends CaptionStyleProps {
  /** Color of the active (currently spoken) word — default "#FFED00" */
  accentColor?: string;
  /** Opacity for upcoming (unspoken) words — default 0.38 */
  upcomingOpacity?: number;
  /** Frames between each word's entry spring start — default 3 */
  staggerFrames?: number;
  /** Amplitude of the idle floating wave in px — default 3 */
  waveAmplitude?: number;
  /** Floating wave frequency in Hz — default 0.7 */
  waveHz?: number;
  /** Letter spacing in em — default 0.02 */
  letterSpacing?: number;
  /** All caps — default true */
  allCaps?: boolean;
  /** Max words per line — default 3 */
  maxWordsPerLine?: number;
  /** Gap between lines — default 14 */
  lineGap?: number;
  /** Gap between words — default 20 */
  wordGap?: number;
}
