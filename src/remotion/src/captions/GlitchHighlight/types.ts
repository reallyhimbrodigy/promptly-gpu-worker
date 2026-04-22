import type { CaptionStyleProps } from "../shared/types";

export interface GlitchColorPreset {
  /** Main color of the special word after glitch settles */
  color: string;
}

export const GLITCH_PRESETS: Record<string, GlitchColorPreset> = {
  cyan: { color: "#38BDF8" },
  blue: { color: "#3B82F6" },
  red: { color: "#FF4060" },
  green: { color: "#34D399" },
  yellow: { color: "#FBBF24" },
  pink: { color: "#F472B6" },
};

export interface GlitchHighlightWord {
  text: string;
  preset?: string;
}

export interface GlitchHighlightProps extends CaptionStyleProps {
  /** Words that get the glitch effect */
  highlightWords?: GlitchHighlightWord[];
  /** Default color preset. Default: "blue" */
  colorPreset?: string;
  /** Stagger delay in frames. Default: 1 */
  staggerDelayFrames?: number;
  /** Duration of glitch effect in frames. Default: 14 */
  glitchDurationFrames?: number;
}
