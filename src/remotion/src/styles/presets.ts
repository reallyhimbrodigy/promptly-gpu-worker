import type { StyleConfig } from "../types";

/**
 * Pre-built caption styles that match or exceed Captions app quality.
 * Each style is a complete visual configuration — fonts, colors, animations,
 * shadows, pills, glow effects.
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

const BASE: Omit<StyleConfig, "animation" | "pillEnabled" | "pillColor" | "glowEnabled" | "glowColor" | "glowRadius" | "keywordFontSize" | "baseFontSize"> = {
  fontFamily: "Montserrat",
  fontWeight: 800,
  lineHeight: 1.15,
  textTransform: "uppercase",
  maxWordsPerGroup: 4,
  position: "lower-third",
  yPercent: 72,
  pillRadius: 16,
  pillPadding: [28, 14],
  textColor: "#FFFFFF",
  activeColor: "#FFFFFF",
  dimColor: "#A0A0A0",
  keywordColors: KEYWORD_COLORS,
  shadowLayers: SHADOW_DEEP,
  animationDuration: 140,
  activeWordScale: 1.08,
  fadeInMs: 80,
  fadeOutMs: 100,
};

export const STYLE_PRESETS: Record<string, StyleConfig> = {
  /**
   * CAPTIONS DYNAMIC — The flagship style. Mixed-size words with keyword emphasis,
   * spring pop-in animation, dark pill background, vibrant keyword colors, glow halos.
   * This is what the Captions app does.
   */
  captions_dynamic: {
    ...BASE,
    baseFontSize: 96,
    keywordFontSize: 134,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.78)",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 24,
  },

  /**
   * CAPTIONS CLEAN — Professional, minimal. No pill, no glow, subtle shadow.
   * Clean white text with gentle pop-in. Keywords highlighted by color only.
   */
  captions_clean: {
    ...BASE,
    baseFontSize: 88,
    keywordFontSize: 110,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    activeWordScale: 1.05,
  },

  /**
   * WORD POP — Word-by-word reveal with aggressive spring bounce.
   * Each word pops in individually with overshoot. Keywords get glow + scale.
   * Maximum energy — great for hype/motivation content.
   */
  word_pop: {
    ...BASE,
    baseFontSize: 96,
    keywordFontSize: 140,
    animation: "spring",
    animationDuration: 160,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.82)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 28,
    activeWordScale: 1.12,
  },

  /**
   * HORMOZI — Bold, high-impact style inspired by Alex Hormozi's content.
   * Large text, heavy shadows, yellow keyword emphasis, no pill.
   */
  hormozi: {
    ...BASE,
    baseFontSize: 104,
    keywordFontSize: 146,
    fontWeight: 900,
    animation: "spring",
    animationDuration: 120,
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 32,
    shadowLayers: SHADOW_GLOW,
    keywordColors: ["#FFE600", "#FFE600", "#FFE600", "#FFE600"],
    activeWordScale: 1.15,
    textTransform: "uppercase",
  },

  /**
   * IMPACT — Cinematic impact style. Dark background pill, white text,
   * typewriter reveal with subtle glow on keywords.
   */
  impact: {
    ...BASE,
    baseFontSize: 92,
    keywordFontSize: 120,
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
  },

  /**
   * SLIDE — Words slide in from below with easing. Clean, modern look.
   */
  slide: {
    ...BASE,
    baseFontSize: 90,
    keywordFontSize: 118,
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
  },

  /**
   * WAVE — Words animate in with a cascading wave effect.
   * Each character gets a slight delay, creating a ripple.
   */
  wave: {
    ...BASE,
    baseFontSize: 92,
    keywordFontSize: 124,
    animation: "wave",
    animationDuration: 300,
    pillEnabled: true,
    pillColor: "rgba(10, 10, 10, 0.80)",
    glowEnabled: true,
    glowColor: "#A855F7",
    glowRadius: 22,
    activeWordScale: 1.06,
  },

  /**
   * CAPCUT — CapCut-inspired style. Simple, bold, effective.
   * White text on semi-transparent pill, minimal animation.
   */
  capcut: {
    ...BASE,
    baseFontSize: 84,
    keywordFontSize: 108,
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
  },

  /**
   * KEYWORD POP — Only keywords get animated. Regular words are static.
   * Keywords explode in with scale + glow + color.
   */
  keyword_pop: {
    ...BASE,
    baseFontSize: 90,
    keywordFontSize: 140,
    animation: "spring",
    animationDuration: 180,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.75)",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 30,
    activeWordScale: 1.0, // only keywords scale
  },

  /**
   * DYNAMIC — Alias for captions_dynamic (backwards compat)
   */
  dynamic: {
    ...BASE,
    baseFontSize: 96,
    keywordFontSize: 134,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.78)",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 24,
  },

  /**
   * CLEAN — Alias for captions_clean
   */
  clean: {
    ...BASE,
    baseFontSize: 88,
    keywordFontSize: 110,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    activeWordScale: 1.05,
  },
};

export function getStyleConfig(styleName: string): StyleConfig {
  return STYLE_PRESETS[styleName] || STYLE_PRESETS["captions_dynamic"];
}
