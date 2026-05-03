import type { CaptionStyleProps } from "../shared/types";

export interface PulseProps extends CaptionStyleProps {
  /** Words that receive the accent (cyan) color. */
  keywords?: string[];
  /** Default text color. Default: "#FFFFFF" */
  textColor?: string;
  /** Keyword accent color. Default: "#00BFFF" */
  keywordColor?: string;
  /** Fade duration in frames (opacity transition). Default: 1 (~17ms at 60fps) — captions snap to spoken-word timing. */
  fadeDurationFrames?: number;
}
