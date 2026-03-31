/** Word-level timing data from Deepgram (post-projection) */
export interface ProjectedWord {
  start: number;
  end: number;
  word: string;
  punctuated_word: string;
  speaker?: number;
  _kw?: boolean;
  _kw_color?: [number, number, number];
}

/** A group of 2-4 words displayed together */
export interface WordGroup {
  words: ProjectedWord[];
  start: number;
  end: number;
}

/** Input data for the caption renderer */
export interface CaptionInput {
  words: ProjectedWord[];
  style: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  keywords: string[];
  fontDir: string;
}

/** Style configuration for a caption style */
export interface StyleConfig {
  fontFamily: string;
  fontWeight: number;
  baseFontSize: number;
  keywordFontSize: number;
  lineHeight: number;
  textTransform: "uppercase" | "none" | "capitalize";
  maxWordsPerGroup: number;
  position: "lower-third" | "center" | "bottom";
  yPercent: number;
  pillEnabled: boolean;
  pillColor: string;
  pillRadius: number;
  pillPadding: [number, number]; // [horizontal, vertical]
  textColor: string;
  activeColor: string;
  dimColor: string;
  keywordColors: string[];
  shadowLayers: { x: number; y: number; blur: number; color: string }[];
  glowEnabled: boolean;
  glowColor: string;
  glowRadius: number;
  animation: "pop" | "spring" | "typewriter" | "slide" | "wave" | "none";
  animationDuration: number; // ms
  activeWordScale: number;
  fadeInMs: number;
  fadeOutMs: number;
}
