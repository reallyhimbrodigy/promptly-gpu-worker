import type { CaptionStyleProps } from "../shared/types";

export interface PulseProps extends CaptionStyleProps {
  /** Words that receive the accent (cyan) color. */
  keywords?: string[];
  /** Default text color. Default: "#FFFFFF" */
  textColor?: string;
  /** Keyword accent color. Default: "#00BFFF" */
  keywordColor?: string;
  /** Retained for prop-API back-compat; ignored. Page transitions are
   *  hard cuts now (snap on/off, no opacity interpolation). */
  fadeDurationFrames?: number;
}
