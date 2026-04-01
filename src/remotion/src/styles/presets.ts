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

export const STYLE_PRESETS: Record<string, StyleConfig> = {
  /**
   * CAPTIONS DYNAMIC — The flagship style. Mixed-size words with keyword emphasis,
   * spring pop-in animation, dark pill background, vibrant keyword colors, glow halos.
   * This is what the Captions app does.
   */
  captions_dynamic: {
    ...BASE,
    baseFontSize: 160,
    keywordFontSize: 220,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(0, 0, 0, 0.55)",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 36,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * CAPTIONS CLEAN — Professional, minimal. No pill, no glow, subtle shadow.
   * Clean white text with gentle pop-in. Keywords highlighted by color only.
   */
  captions_clean: {
    ...BASE,
    baseFontSize: 150,
    keywordFontSize: 200,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    activeWordScale: 1.05,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * WORD POP — Word-by-word reveal with aggressive spring bounce.
   * Each word pops in individually with overshoot. Keywords get glow + scale.
   * Maximum energy — great for hype/motivation content.
   */
  word_pop: {
    ...BASE,
    baseFontSize: 170,
    keywordFontSize: 240,
    animation: "spring",
    animationDuration: 160,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.82)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 40,
    activeWordScale: 1.30,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * HORMOZI — Bold, high-impact style inspired by Alex Hormozi's content.
   * Large text, heavy shadows, yellow keyword emphasis, no pill.
   */
  hormozi: {
    ...BASE,
    baseFontSize: 180,
    keywordFontSize: 250,
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
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * IMPACT — Cinematic impact style. Dark background pill, white text,
   * typewriter reveal with subtle glow on keywords.
   */
  impact: {
    ...BASE,
    baseFontSize: 155,
    keywordFontSize: 210,
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
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * SLIDE — Words slide in from below with easing. Clean, modern look.
   */
  slide: {
    ...BASE,
    baseFontSize: 150,
    keywordFontSize: 200,
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
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * WAVE — Words animate in with a cascading wave effect.
   * Each character gets a slight delay, creating a ripple.
   */
  wave: {
    ...BASE,
    baseFontSize: 155,
    keywordFontSize: 210,
    animation: "wave",
    animationDuration: 300,
    pillEnabled: true,
    pillColor: "rgba(10, 10, 10, 0.80)",
    glowEnabled: true,
    glowColor: "#A855F7",
    glowRadius: 22,
    activeWordScale: 1.06,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * CAPCUT — CapCut-inspired style. Simple, bold, effective.
   * White text on semi-transparent pill, minimal animation.
   */
  capcut: {
    ...BASE,
    baseFontSize: 140,
    keywordFontSize: 190,
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
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * KEYWORD POP — Only keywords get animated. Regular words are static.
   * Keywords explode in with scale + glow + color.
   */
  keyword_pop: {
    ...BASE,
    baseFontSize: 155,
    keywordFontSize: 240,
    animation: "spring",
    animationDuration: 180,
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.75)",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 44,
    activeWordScale: 1.0, // only keywords scale
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * DYNAMIC — Alias for captions_dynamic (backwards compat)
   */
  dynamic: {
    ...BASE,
    baseFontSize: 160,
    keywordFontSize: 220,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.78)",
    glowEnabled: true,
    glowColor: "#FFE600",
    glowRadius: 36,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /**
   * CLEAN — Alias for captions_clean
   */
  clean: {
    ...BASE,
    baseFontSize: 150,
    keywordFontSize: 200,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SUBTLE,
    activeWordScale: 1.05,
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Gradient
  // ═══════════════════════════════════════════════════════════════════════════

  /** NEON GRADIENT — Poppins ExtraBold, pink→cyan gradient, dark pill, glow */
  neon_gradient: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    baseFontSize: 155,
    keywordFontSize: 215,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.80)",
    glowEnabled: true,
    glowColor: "#00D2FF",
    glowRadius: 24,
    gradientColors: ["#FF3CAC", "#00D2FF"],
    gradientDirection: "to right",
    speakerColors: ["#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF4400"],
  },

  /** SUNSET GRADIENT — Montserrat Black, orange→pink→purple, no pill */
  sunset_gradient: {
    ...BASE,
    fontWeight: 900,
    baseFontSize: 160,
    keywordFontSize: 220,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    gradientColors: ["#FF6B35", "#FF3C64", "#8B5CF6"],
    gradientDirection: "135deg",
    speakerColors: ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3", "#F38181"],
  },

  /** GOLD GRADIENT — Playfair Display Bold, gold→amber, gold underline */
  gold_gradient: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    baseFontSize: 145,
    keywordFontSize: 190,
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
    speakerColors: ["#FF6B6B", "#4ECDC4", "#FFE66D", "#95E1D3", "#F38181"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Outline
  // ═══════════════════════════════════════════════════════════════════════════

  /** OUTLINE BOLD — Montserrat Black, thick white outline only */
  outline_bold: {
    ...BASE,
    fontWeight: 900,
    baseFontSize: 190,
    keywordFontSize: 260,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 3, color: "#FFFFFF" },
    outlineOnly: true,
    backgroundShape: "none",
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  /** OUTLINE NEON — Poppins ExtraBold, cyan outline with glow, no fill */
  outline_neon: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    baseFontSize: 160,
    keywordFontSize: 215,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 28,
    textStroke: { width: 2, color: "#00DCC8" },
    outlineOnly: true,
    backgroundShape: "none",
    speakerColors: ["#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF4400"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Handwritten / Casual
  // ═══════════════════════════════════════════════════════════════════════════

  /** HANDWRITTEN — PermanentMarker, white text, deep shadow, no pill */
  handwritten: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    baseFontSize: 150,
    keywordFontSize: 200,
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

  /** MARKER HIGHLIGHT — PermanentMarker, yellow highlight background */
  marker_highlight: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    baseFontSize: 140,
    keywordFontSize: 190,
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
    speakerColors: ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Condensed / Cinema
  // ═══════════════════════════════════════════════════════════════════════════

  /** CINEMA — Bebas Neue, wide spacing, cool blue shadow, no pill */
  cinema: {
    ...BASE,
    fontFamily: "Bebas Neue",
    fontWeight: 400,
    baseFontSize: 175,
    keywordFontSize: 230,
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
    speakerColors: ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"],
  },

  /** NEWS TICKER — Oswald Bold, red pill, white text, typewriter */
  news_ticker: {
    ...BASE,
    fontFamily: "Oswald",
    fontWeight: 700,
    baseFontSize: 135,
    keywordFontSize: 170,
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
    speakerColors: ["#FFCC00", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Comic / Meme
  // ═══════════════════════════════════════════════════════════════════════════

  /** COMIC POP — Bangers, yellow text, thick black outline, spring bounce */
  comic_pop: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    baseFontSize: 165,
    keywordFontSize: 225,
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
    speakerColors: ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"],
  },

  /** MEME BOLD — Bangers, white text, heavy black outline, pop anim */
  meme_bold: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    baseFontSize: 160,
    keywordFontSize: 215,
    animation: "pop",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 4, color: "#000000" },
    backgroundShape: "none",
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Elegant / Luxury
  // ═══════════════════════════════════════════════════════════════════════════

  /** LUXURY — Playfair Display Bold, white text, subtle gold underline */
  luxury: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    baseFontSize: 145,
    keywordFontSize: 190,
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
    speakerColors: ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"],
  },

  /** EDITORIAL — Playfair Display, dark text on white pill (inverted) */
  editorial: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    baseFontSize: 135,
    keywordFontSize: 175,
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
    speakerColors: ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Stacked
  // ═══════════════════════════════════════════════════════════════════════════

  /** STACKED BOLD — Montserrat Black, stacked vertical, deep shadow */
  stacked_bold: {
    ...BASE,
    fontWeight: 900,
    baseFontSize: 195,
    keywordFontSize: 265,
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
    speakerColors: ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"],
  },

  /** STACKED COLOR — Poppins ExtraBold, stacked, cycling keyword colors, dark pill */
  stacked_color: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    baseFontSize: 180,
    keywordFontSize: 240,
    animation: "pop",
    pillEnabled: true,
    pillColor: "rgba(15, 15, 15, 0.80)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 22,
    stackedLayout: true,
    keywordColors: ["#FFE600", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: ["#FFD700", "#00FFFF", "#FF4444", "#44FF44", "#FF8C00"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — 3D / Extruded
  // ═══════════════════════════════════════════════════════════════════════════

  /** RETRO 3D — Bangers, yellow text, black 3D extrusion, no pill */
  retro_3d: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    baseFontSize: 160,
    keywordFontSize: 215,
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

  /** NEON 3D — Space Grotesk Bold, cyan text, glow + subtle extrusion */
  neon_3d: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    baseFontSize: 150,
    keywordFontSize: 200,
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
    speakerColors: ["#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF4400"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Tech / Modern
  // ═══════════════════════════════════════════════════════════════════════════

  /** TECH CLEAN — Space Grotesk, white text, thin cyan underline, minimal */
  tech_clean: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 500,
    baseFontSize: 140,
    keywordFontSize: 180,
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

  /** TECH GLOW — Space Grotesk Bold, cyan text, glow, no pill */
  tech_glow: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    baseFontSize: 145,
    keywordFontSize: 190,
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
    speakerColors: ["#FF00FF", "#00FFFF", "#FFFF00", "#00FF00", "#FF4400"],
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // NEW STYLES — Minimal / Clean
  // ═══════════════════════════════════════════════════════════════════════════

  /** MINIMAL SANS — Poppins SemiBold, white text, no pill, no glow, subtle shadow */
  minimal_sans: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    baseFontSize: 130,
    keywordFontSize: 170,
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
    speakerColors: ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"],
  },

  /** MINIMAL LOWER — Poppins, very small dark pill, extremely clean */
  minimal_lower: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    baseFontSize: 120,
    keywordFontSize: 155,
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
    speakerColors: ["#FFD700", "#87CEEB", "#98FB98", "#DDA0DD", "#F4A460"],
  },
};

export function getStyleConfig(styleName: string): StyleConfig {
  return STYLE_PRESETS[styleName] || STYLE_PRESETS["captions_dynamic"];
}
