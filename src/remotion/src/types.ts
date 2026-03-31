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

// ─── Visual Effects Types ────────────────────────────────────────────────────

/** A cut/transition point in the output timeline */
export interface CutPoint {
  time: number; // seconds in output timeline where this cut happens
  transition: string; // transition type from edit plan
  duration: number; // clip duration after this cut
}

/** An emphasis moment from Gemini's edit plan */
export interface EmphasisMoment {
  t: number; // seconds in output timeline
  type: string; // punchline, revelation, statement, reaction, question, transition
  intensity: string; // high, medium
}

/** A single visual effect instance */
export interface VisualEffect {
  type: EffectType;
  start: number; // seconds
  end: number; // seconds
  params?: Record<string, unknown>;
}

export type EffectType =
  | "light_leak"
  | "glitch"
  | "impact_flash"
  | "particle_burst"
  | "particle_ambient"
  | "emoji_pop"
  | "vhs_grain"
  | "zoom_blur_transition"
  | "whip_pan"
  | "vignette_pulse"
  | "color_flash"
  | "letterbox_cinematic"
  | "edge_glow";

/** Full input for the combined overlay renderer */
export interface OverlayInput {
  // Captions
  words: ProjectedWord[];
  captionStyle: string;
  keywords: string[];
  // Visual effects
  effects: VisualEffect[];
  // Cuts/transitions timeline
  cuts: CutPoint[];
  // Emphasis moments
  emphasisMoments: EmphasisMoment[];
  // Video metadata
  width: number;
  height: number;
  fps: number;
  duration: number;
  durationInFrames: number;
  fontDir: string;
  // Vibe for effect selection
  vibe: string;
}
