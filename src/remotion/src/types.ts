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
  baseFontSize?: number;
  keywordFontSize?: number;
  lineHeight: number;
  textTransform: "uppercase" | "lowercase" | "none" | "capitalize";
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

  // ─── Extended style properties (optional) ───────────────────────────────
  // Text fill
  textStroke?: { width: number; color: string };  // outline stroke
  gradientColors?: string[];  // gradient text fill (2-3 colors)
  gradientDirection?: string; // CSS gradient direction (e.g. "to right", "135deg")
  outlineOnly?: boolean; // stroke only, transparent fill

  // Background variations
  backgroundShape?: "pill" | "underline" | "highlight" | "box" | "none";
  highlightColor?: string; // for highlight background shape
  underlineColor?: string; // for underline background shape
  underlineThickness?: number;

  // Layout
  stackedLayout?: boolean; // one word per line, stacked vertically

  // 3D/Depth
  shadowExtrude?: { angle: number; distance: number; color: string }; // 3D extruded shadow

  // Typography (override default fontFamily at word level is already fontFamily above)

  // Multi-speaker
  speakerColors?: string[];  // per-speaker active highlight colors
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
  word?: string; // the key word/phrase to display (for cascade echo / impact text)
  duration?: number; // how long the emphasis lasts (seconds)
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
  | "whip_pan_blur"
  | "vignette_pulse"
  | "color_flash"
  | "warm_flash"
  | "letterbox_cinematic"
  | "edge_glow"
  | "cascade_echo"
  | "impact_text"
  | "blur_card";

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
