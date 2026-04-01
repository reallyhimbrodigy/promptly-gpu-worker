import type { StyleConfig } from "../types";

/**
 * Pre-built caption styles that match or exceed Captions app quality.
 * Each style is a complete visual configuration -- fonts, colors, animations,
 * shadows, pills, glow effects.
 *
 * Font sizes (baseFontSize / keywordFontSize) are intentionally omitted.
 * CaptionPage auto-computes them at render time based on word count and
 * video dimensions.
 */

const KEYWORD_COLORS = ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"];

const SHADOW_DEEP: StyleConfig["shadowLayers"] = [
  { x: 0, y: 4, blur: 12, color: "rgba(0,0,0,0.7)" },
  { x: 0, y: 2, blur: 6, color: "rgba(0,0,0,0.5)" },
  { x: 0, y: 1, blur: 2, color: "rgba(0,0,0,0.9)" },
];

const SHADOW_SUBTLE: StyleConfig["shadowLayers"] = [
  { x: 0, y: 2, blur: 8, color: "rgba(0,0,0,0.5)" },
  { x: 0, y: 1, blur: 3, color: "rgba(0,0,0,0.7)" },
];

const SHADOW_GLOW: StyleConfig["shadowLayers"] = [
  { x: 0, y: 0, blur: 20, color: "rgba(255,255,255,0.3)" },
  { x: 0, y: 3, blur: 8, color: "rgba(0,0,0,0.8)" },
  { x: 0, y: 1, blur: 2, color: "rgba(0,0,0,0.9)" },
];

const SPEAKER_DEFAULT = ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"];
const SPEAKER_NEON = ["#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF4400"];
const SPEAKER_WARM = ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3", "#F38181"];
const SPEAKER_PASTEL = ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"];
const SPEAKER_COMIC = ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"];

const BASE: Omit<StyleConfig, "animation" | "pillEnabled" | "pillColor" | "glowEnabled" | "glowColor" | "glowRadius"> = {
  fontFamily: "Montserrat",
  fontWeight: 800,
  lineHeight: 1.05,
  textTransform: "uppercase",
  maxWordsPerGroup: 3,
  position: "lower-third",
  yPercent: 68,
  pillRadius: 16,
  pillPadding: [28, 14],
  textColor: "#FFFFFF",
  activeColor: "#FFFFFF",
  dimColor: "#A0A0A0",
  keywordColors: KEYWORD_COLORS,
  shadowLayers: SHADOW_DEEP,
  animationDuration: 140,
  activeWordScale: 1.25,
  fadeInMs: 80,
  fadeOutMs: 100,
};

// ─── Presets ─────────────────────────────────────────────────────────────────

const captions_dynamic: StyleConfig = {
  ...BASE,
  animation: "spring",
  pillEnabled: true,
  pillColor: "rgba(0, 0, 0, 0.55)",
  glowEnabled: true,
  glowColor: "#FFE600",
  glowRadius: 36,
  speakerColors: SPEAKER_DEFAULT,
};

const captions_clean: StyleConfig = {
  ...BASE,
  animation: "pop",
  pillEnabled: false,
  pillColor: "transparent",
  glowEnabled: false,
  glowColor: "transparent",
  glowRadius: 0,
  shadowLayers: SHADOW_SUBTLE,
  activeWordScale: 1.05,
  speakerColors: SPEAKER_DEFAULT,
};

export const STYLE_PRESETS: Record<string, StyleConfig> = {
  // ═══════════════════════════════════════════════════════════════════════════
  // Flagship
  // ═══════════════════════════════════════════════════════════════════════════

  /** CAPTIONS DYNAMIC -- Mixed-size words, spring pop-in, dark pill, glow halos */
  captions_dynamic,

  /** CAPTIONS CLEAN -- Professional, minimal. No pill, no glow, subtle shadow */
  captions_clean,

  /** DYNAMIC -- Alias for captions_dynamic (backward compat) */
  dynamic: captions_dynamic,

  /** CLEAN -- Alias for captions_clean (backward compat) */
  clean: captions_clean,

  // ═══════════════════════════════════════════════════════════════════════════
  // High-energy
  // ═══════════════════════════════════════════════════════════════════════════

  /** WORD POP -- Aggressive spring bounce, keyword glow + scale */
  word_pop: {
    ...BASE,
    animation: "spring",
    animationDuration: 160,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.82)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 40,
    activeWordScale: 1.30,
    speakerColors: SPEAKER_DEFAULT,
  },

  /** HORMOZI -- Bold, high-impact, yellow keyword emphasis, no pill */
  hormozi: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    animationDuration: 120,
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 48,
    shadowLayers: SHADOW_GLOW,
    keywordColors: ["#FFE600", "#FFE600", "#FFE600", "#FFE600"],
    activeWordScale: 1.35,
    textTransform: "uppercase",
    speakerColors: SPEAKER_DEFAULT,
  },

  /** KEYWORD POP -- Only keywords animate; regular words static */
  keyword_pop: {
    ...BASE,
    animation: "spring",
    animationDuration: 180,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.75)",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 44,
    activeWordScale: 1.0,
    speakerColors: SPEAKER_DEFAULT,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Cinematic / Broadcast
  // ═══════════════════════════════════════════════════════════════════════════

  /** IMPACT -- Dark pill, typewriter reveal, subtle keyword glow */
  impact: {
    ...BASE,
    animation: "typewriter",
    animationDuration: 60,
    pillEnabled: true,
    pillColor: "rgba(0, 0, 0, 0.85)",
    pillRadius: 12,
    glowEnabled: true,
    glowColor: "#3B82F6",
    glowRadius: 20,
    activeWordScale: 1.0,
    shadowLayers: SHADOW_DEEP,
    speakerColors: SPEAKER_DEFAULT,
  },

  /** SLIDE -- Words slide in from below, clean modern look */
  slide: {
    ...BASE,
    animation: "slide",
    animationDuration: 200,
    pillEnabled: true,
    pillColor: "rgba(20, 20, 20, 0.75)",
    pillRadius: 20,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.04,
    shadowLayers: SHADOW_SUBTLE,
    speakerColors: SPEAKER_DEFAULT,
  },

  /** WAVE -- Cascading wave animation per character */
  wave: {
    ...BASE,
    animation: "wave",
    animationDuration: 300,
    pillEnabled: true,
    pillColor: "rgba(10, 10, 10, 0.80)",
    glowEnabled: true,
    glowColor: "#A855F7",
    glowRadius: 22,
    activeWordScale: 1.06,
    speakerColors: SPEAKER_DEFAULT,
  },

  /** CAPCUT -- CapCut-inspired, simple bold effective */
  capcut: {
    ...BASE,
    animation: "pop",
    animationDuration: 100,
    pillEnabled: true,
    pillColor: "rgba(0, 0, 0, 0.70)",
    pillRadius: 10,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.03,
    shadowLayers: SHADOW_SUBTLE,
    textTransform: "none",
    speakerColors: SPEAKER_DEFAULT,
  },

  /** CINEMA -- Bebas Neue, wide spacing, cool blue shadow */
  cinema: {
    ...BASE,
    fontFamily: "Bebas Neue",
    fontWeight: 400,
    animation: "slide",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: [
      { x: 0, y: 4, blur: 14, color: "rgba(30, 60, 120, 0.6)" },
      { x: 0, y: 2, blur: 6, color: "rgba(0, 0, 0, 0.7)" },
      { x: 0, y: 1, blur: 2, color: "rgba(0, 0, 0, 0.9)" },
    ],
    backgroundShape: "none",
    speakerColors: SPEAKER_PASTEL,
  },

  /** NEWS TICKER -- Oswald Bold, red pill, typewriter */
  news_ticker: {
    ...BASE,
    fontFamily: "Oswald",
    fontWeight: 700,
    animation: "typewriter",
    animationDuration: 60,
    pillEnabled: true,
    pillColor: "#CC0000",
    pillRadius: 6,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.0,
    backgroundShape: "pill",
    speakerColors: SPEAKER_DEFAULT,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Gradient
  // ═══════════════════════════════════════════════════════════════════════════

  /** NEON GRADIENT -- Poppins ExtraBold, pink-cyan gradient, dark pill, glow */
  neon_gradient: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.80)",
    glowEnabled: true,
    glowColor: "#00D2FF",
    glowRadius: 24,
    gradientColors: ["#FF3CAC", "#00D2FF"],
    gradientDirection: "to right",
    speakerColors: SPEAKER_NEON,
  },

  /** SUNSET GRADIENT -- Montserrat Black, orange-pink-purple, no pill */
  sunset_gradient: {
    ...BASE,
    fontWeight: 900,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    gradientColors: ["#FF6B35", "#FF3C64", "#8B5CF6"],
    gradientDirection: "135deg",
    speakerColors: SPEAKER_WARM,
  },

  /** GOLD GRADIENT -- Playfair Display Bold, gold-amber, gold underline */
  gold_gradient: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    animation: "slide",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    gradientColors: ["#FFD700", "#FFA000"],
    gradientDirection: "to right",
    backgroundShape: "underline",
    underlineColor: "#FFD700",
    underlineThickness: 4,
    textTransform: "none",
    speakerColors: SPEAKER_WARM,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Outline
  // ═══════════════════════════════════════════════════════════════════════════

  /** OUTLINE BOLD -- Montserrat Black, thick white outline only */
  outline_bold: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 3, color: "#FFFFFF" },
    outlineOnly: true,
    backgroundShape: "none",
    speakerColors: SPEAKER_DEFAULT,
  },

  /** OUTLINE NEON -- Poppins ExtraBold, cyan outline with glow, no fill */
  outline_neon: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 28,
    textStroke: { width: 2, color: "#00DCC8" },
    outlineOnly: true,
    backgroundShape: "none",
    speakerColors: SPEAKER_NEON,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Handwritten / Casual
  // ═══════════════════════════════════════════════════════════════════════════

  /** HANDWRITTEN -- PermanentMarker, white text, deep shadow */
  handwritten: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_DEEP,
    textTransform: "none",
    backgroundShape: "none",
    speakerColors: ["#2C3E50", "#E74C3C", "#3498DB", "#27AE60", "#F39C12"],
  },

  /** MARKER HIGHLIGHT -- PermanentMarker, yellow highlight background */
  marker_highlight: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textColor: "#1A1A1A",
    activeColor: "#1A1A1A",
    dimColor: "#333333",
    backgroundShape: "highlight",
    highlightColor: "#FFE600",
    shadowLayers: SHADOW_SUBTLE,
    textTransform: "none",
    speakerColors: SPEAKER_COMIC,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Comic / Meme
  // ═══════════════════════════════════════════════════════════════════════════

  /** COMIC POP -- Bangers, yellow text, thick black outline, spring bounce */
  comic_pop: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    textColor: "#FFE600",
    activeColor: "#FFE600",
    dimColor: "#CCBB00",
    animation: "spring",
    animationDuration: 180,
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 3, color: "#000000" },
    activeWordScale: 1.30,
    backgroundShape: "none",
    keywordColors: ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6", "#FFE600"],
    speakerColors: SPEAKER_COMIC,
  },

  /** MEME BOLD -- Bangers, white text, heavy black outline */
  meme_bold: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 4, color: "#000000" },
    backgroundShape: "none",
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: SPEAKER_COMIC,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Elegant / Luxury
  // ═══════════════════════════════════════════════════════════════════════════

  /** LUXURY -- Playfair Display Bold, white text, subtle gold underline */
  luxury: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    animation: "slide",
    animationDuration: 240,
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    backgroundShape: "underline",
    underlineColor: "#D4AF37",
    underlineThickness: 3,
    textTransform: "none",
    keywordColors: ["#D4AF37", "#FFD700", "#D4AF37", "#FFA000", "#D4AF37", "#FFD700"],
    speakerColors: SPEAKER_PASTEL,
  },

  /** EDITORIAL -- Playfair Display, dark text on white pill (inverted) */
  editorial: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    textColor: "#1A1A1A",
    activeColor: "#000000",
    dimColor: "#444444",
    animation: "slide",
    animationDuration: 220,
    pillEnabled: true,
    pillColor: "rgba(255, 255, 255, 0.92)",
    pillRadius: 12,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: [
      { x: 0, y: 1, blur: 3, color: "rgba(0, 0, 0, 0.1)" },
    ],
    textTransform: "none",
    keywordColors: ["#8B5CF6", "#3B82F6", "#059669", "#DC2626", "#D97706", "#7C3AED"],
    speakerColors: SPEAKER_PASTEL,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Stacked
  // ═══════════════════════════════════════════════════════════════════════════

  /** STACKED BOLD -- Montserrat Black, stacked vertical, deep shadow */
  stacked_bold: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_DEEP,
    stackedLayout: true,
    backgroundShape: "none",
    activeWordScale: 1.30,
    speakerColors: SPEAKER_COMIC,
  },

  /** STACKED COLOR -- Poppins ExtraBold, stacked, cycling keyword colors, dark pill */
  stacked_color: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "pop",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.80)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 22,
    stackedLayout: true,
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: SPEAKER_COMIC,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // 3D / Extruded
  // ═══════════════════════════════════════════════════════════════════════════

  /** RETRO 3D -- Bangers, yellow text, black 3D extrusion */
  retro_3d: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    textColor: "#FFE600",
    activeColor: "#FFE600",
    dimColor: "#CCBB00",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowExtrude: { angle: 135, distance: 6, color: "#000000" },
    backgroundShape: "none",
    keywordColors: ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#FFE600", "#3B82F6"],
    speakerColors: ["#FF6B35", "#00D4FF", "#FFDD00", "#FF3366", "#00FF88"],
  },

  /** NEON 3D -- Space Grotesk Bold, cyan text, glow + subtle extrusion */
  neon_3d: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    textColor: "#00DCC8",
    activeColor: "#00DCC8",
    dimColor: "#008F80",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 24,
    shadowExtrude: { angle: 135, distance: 2, color: "#005F54" },
    backgroundShape: "none",
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#FF3C64"],
    speakerColors: SPEAKER_NEON,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Tech / Modern
  // ═══════════════════════════════════════════════════════════════════════════

  /** TECH CLEAN -- Space Grotesk, white text, thin cyan underline, minimal */
  tech_clean: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 500,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    backgroundShape: "underline",
    underlineColor: "#00DCC8",
    underlineThickness: 3,
    activeWordScale: 1.04,
    textTransform: "none",
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#00DCC8", "#FFE600", "#3B82F6"],
    speakerColors: ["#00D4FF", "#00FF88", "#FFD700", "#FF44FF", "#FF6B35"],
  },

  /** TECH GLOW -- Space Grotesk Bold, cyan text, glow */
  tech_glow: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    textColor: "#00DCC8",
    activeColor: "#00FFEE",
    dimColor: "#008F80",
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 22,
    shadowLayers: SHADOW_GLOW,
    backgroundShape: "none",
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#FFE600", "#00DCC8", "#FF3C64"],
    speakerColors: SPEAKER_NEON,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // Minimal / Clean
  // ═══════════════════════════════════════════════════════════════════════════

  /** MINIMAL SANS -- Poppins SemiBold, white text, no pill, no glow */
  minimal_sans: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    animation: "pop",
    animationDuration: 100,
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: [
      { x: 0, y: 2, blur: 6, color: "rgba(0, 0, 0, 0.5)" },
    ],
    activeWordScale: 1.04,
    textTransform: "none",
    backgroundShape: "none",
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: SPEAKER_PASTEL,
  },

  /** MINIMAL LOWER -- Poppins, very small dark pill, extremely clean */
  minimal_lower: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    animation: "slide",
    animationDuration: 180,
    pillEnabled: true,
    pillColor: "rgba(10, 10, 10, 0.55)",
    pillRadius: 10,
    pillPadding: [18, 8],
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: [
      { x: 0, y: 1, blur: 3, color: "rgba(0, 0, 0, 0.4)" },
    ],
    activeWordScale: 1.02,
    textTransform: "none",
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: SPEAKER_PASTEL,
  },
};

export function getStyleConfig(styleName: string): StyleConfig {
  return STYLE_PRESETS[styleName] || STYLE_PRESETS["captions_dynamic"];
}
