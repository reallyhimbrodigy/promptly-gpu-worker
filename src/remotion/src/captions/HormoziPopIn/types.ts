import type { SpringConfig } from "remotion";
import type { CaptionStyleProps } from "../shared/types";

export interface HormoziHighlightWord {
  /** Word text to match (case-insensitive, punctuation-stripped) */
  text: string;
  /** Color for this highlighted word */
  color: string;
}

export interface HormoziPopInProps extends CaptionStyleProps {
  /** Words to highlight with specific colors */
  highlightWords?: HormoziHighlightWord[];
  /** Scale multiplier for highlighted words at rest. Default: 1.45 */
  highlightScale?: number;
  /** Letter spacing in em units. Default: 0.05 */
  letterSpacing?: number;
  /** Spring config for pop-in. Default: Hormozi-tuned spring */
  springConfig?: SpringConfig;
  /** Stagger delay in frames between each word pop. Default: 1 */
  staggerDelayFrames?: number;
  /** Y translate distance in px for pop-in entry. Default: 8 */
  translateY?: number;
  /** Max words per line. Default: 4 */
  maxWordsPerLine?: number;
  /** Force uppercase. Default: true */
  allCaps?: boolean;
  /** Enable soft drop shadow behind stroke. Default: true */
  enableSoftShadow?: boolean;
}
