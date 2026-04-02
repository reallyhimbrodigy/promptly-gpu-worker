import type { StyleConfig } from "../types";

/**
 * Caption style presets — tuned to match Captions AI quality.
 *
 * Design principles (from studying Captions AI output):
 * - Subtle scale pops (1.08-1.15) feel premium; large jumps (1.3+) look cheap
 * - One accent color per style, not rainbow
 * - Strong black outline (2-3px) is non-negotiable for readability
 * - Glow on active word, not just keywords
 * - Past words return to full white/bright (not dimmed gray)
 * - Spring damping ~10-12 with visible overshoot = organic, alive
 * - Font sizes auto-computed by CaptionPage based on word count
 */

const KEYWORD_COLORS = ["#FFD700", "#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"];

// Shadow presets — heavy enough for any background
const SHADOW_STRONG: StyleConfig["shadowLayers"] = [
  { x: 0, y: 2, blur: 8, color: "rgba(0,0,0,0.9)" },
  { x: 0, y: 4, blur: 16, color: "rgba(0,0,0,0.5)" },
];

const SHADOW_MEDIUM: StyleConfig["shadowLayers"] = [
  { x: 0, y: 2, blur: 6, color: "rgba(0,0,0,0.7)" },
  { x: 0, y: 1, blur: 3, color: "rgba(0,0,0,0.9)" },
];

const SHADOW_SOFT: StyleConfig["shadowLayers"] = [
  { x: 0, y: 1, blur: 4, color: "rgba(0,0,0,0.5)" },
];

const SPEAKER_COLORS = ["#FFD700", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"];

// ─── Base config ─────────────────────────────────────────────────────────────
const BASE: Omit<StyleConfig, "animation" | "pillEnabled" | "pillColor" | "glowEnabled" | "glowColor" | "glowRadius"> = {
  fontFamily: "Montserrat",
  fontWeight: 800,
  lineHeight: 1.1,
  textTransform: "uppercase",
  maxWordsPerGroup: 3,
  position: "lower-third",
  yPercent: 75,
  pillRadius: 14,
  pillPadding: [24, 12],
  textColor: "#FFFFFF",
  activeColor: "#FFD700",        // Yellow active = the Captions AI signature
  dimColor: "rgba(255,255,255,0.45)", // Future words: visible but clearly not active
  keywordColors: KEYWORD_COLORS,
  shadowLayers: SHADOW_STRONG,
  animationDuration: 140,
  activeWordScale: 1.12,         // Subtle pop = premium feel
  fadeInMs: 90,
  fadeOutMs: 110,
};

// ─── Presets ─────────────────────────────────────────────────────────────────

export const STYLE_PRESETS: Record<string, StyleConfig> = {

  // ═══════════════════════════════════════════════════════════════════════════
  // SIGNATURE STYLES (the ones that should look as good as Captions AI)
  // ═══════════════════════════════════════════════════════════════════════════

  /** BOLD — The flagship. White text, yellow active, black outline, spring pop, warm glow.
   *  This is the "Captions AI look" — the one that should be indistinguishable. */
  captions_dynamic: {
    ...BASE,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#FFD700",
    glowRadius: 20,
    activeWordScale: 1.12,
    speakerColors: SPEAKER_COLORS,
  },

  /** BOLD PILL — Same as bold but with dark pill behind text */
  captions_pill: {
    ...BASE,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(0,0,0,0.6)",
    glowEnabled: true,
    glowColor: "#FFD700",
    glowRadius: 18,
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  /** CLEAN — Minimal. White on white, no glow, barely any scale. Professional/corporate. */
  captions_clean: {
    ...BASE,
    animation: "spring",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.5)",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.06,
    shadowLayers: SHADOW_MEDIUM,
    speakerColors: SPEAKER_COLORS,
  },

  // Aliases
  dynamic: {
    ...BASE,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#FFD700",
    glowRadius: 20,
    activeWordScale: 1.12,
    speakerColors: SPEAKER_COLORS,
  },

  clean: {
    ...BASE,
    animation: "spring",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.5)",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.06,
    shadowLayers: SHADOW_MEDIUM,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // ENERGETIC
  // ═══════════════════════════════════════════════════════════════════════════

  /** HYPE — Slightly more aggressive pop, pink-red glow, for high-energy content */
  word_pop: {
    ...BASE,
    animation: "spring",
    activeColor: "#FF3C64",
    pillEnabled: true,
    pillColor: "rgba(10,10,10,0.7)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 22,
    activeWordScale: 1.15,
    speakerColors: SPEAKER_COLORS,
  },

  /** HORMOZI — Bold yellow emphasis, thick outlines, readable on any bg.
   *  Inspired by Alex Hormozi's video style: bold, high-contrast, impactful. */
  hormozi: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    activeColor: "#FFD700",
    textColor: "#FFFFFF",
    pillEnabled: true,
    pillColor: "rgba(0,0,0,0.65)",
    pillRadius: 16,
    glowEnabled: true,
    glowColor: "#FFD700",
    glowRadius: 14,               // Tighter glow — crisp, not blurry
    activeWordScale: 1.12,
    textStroke: { width: 3, color: "rgba(0,0,0,0.95)" },
    keywordColors: ["#FFD700", "#FF3C64", "#00DCC8", "#FF8C00"],
    shadowLayers: [
      { x: 0, y: 3, blur: 10, color: "rgba(0,0,0,0.95)" },
      { x: 0, y: 6, blur: 20, color: "rgba(0,0,0,0.5)" },
    ],
    speakerColors: SPEAKER_COLORS,
  },

  /** KEYWORD POP — Regular words stay still, only keywords animate */
  keyword_pop: {
    ...BASE,
    animation: "spring",
    activeColor: "#FFFFFF",
    pillEnabled: true,
    pillColor: "rgba(10,10,10,0.65)",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 20,
    activeWordScale: 1.0,  // No scale on regular words
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // CINEMATIC / BROADCAST
  // ═══════════════════════════════════════════════════════════════════════════

  /** IMPACT — Dark pill, typewriter reveal, blue keyword glow */
  impact: {
    ...BASE,
    animation: "typewriter",
    pillEnabled: true,
    pillColor: "rgba(0,0,0,0.8)",
    pillRadius: 10,
    glowEnabled: true,
    glowColor: "#3B82F6",
    glowRadius: 16,
    activeWordScale: 1.0,
    activeColor: "#FFFFFF",
    speakerColors: SPEAKER_COLORS,
  },

  /** SLIDE — Words slide up smoothly */
  slide: {
    ...BASE,
    animation: "slide",
    pillEnabled: true,
    pillColor: "rgba(15,15,15,0.65)",
    pillRadius: 16,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.05,
    shadowLayers: SHADOW_MEDIUM,
    speakerColors: SPEAKER_COLORS,
  },

  /** WAVE — Cascading entrance per word */
  wave: {
    ...BASE,
    animation: "wave",
    pillEnabled: true,
    pillColor: "rgba(8,8,8,0.7)",
    glowEnabled: true,
    glowColor: "#A855F7",
    glowRadius: 18,
    activeWordScale: 1.08,
    speakerColors: SPEAKER_COLORS,
  },

  /** CINEMA — Bebas Neue, cool blue shadow, cinematic feel */
  cinema: {
    ...BASE,
    fontFamily: "Bebas Neue",
    fontWeight: 400,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeColor: "#87CEEB",
    shadowLayers: [
      { x: 0, y: 3, blur: 12, color: "rgba(20,40,80,0.6)" },
      { x: 0, y: 1, blur: 4, color: "rgba(0,0,0,0.9)" },
    ],
    activeWordScale: 1.08,
    speakerColors: ["#87CEEB", "#FFD700", "#FF8C00", "#00FF88", "#FF44FF"],
  },

  /** CAPCUT — Simple, effective, lowercase-friendly */
  capcut: {
    ...BASE,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(0,0,0,0.6)",
    pillRadius: 10,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.06,
    shadowLayers: SHADOW_MEDIUM,
    textTransform: "none",
    speakerColors: SPEAKER_COLORS,
  },

  /** NEWS — Oswald, red pill, typewriter */
  news_ticker: {
    ...BASE,
    fontFamily: "Oswald",
    fontWeight: 700,
    animation: "typewriter",
    pillEnabled: true,
    pillColor: "#CC0000",
    pillRadius: 6,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    activeWordScale: 1.0,
    activeColor: "#FFFFFF",
    backgroundShape: "pill",
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // GRADIENT
  // ═══════════════════════════════════════════════════════════════════════════

  /** NEON GRADIENT — Pink-to-cyan gradient, dark pill, cyan glow */
  neon_gradient: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(10,10,10,0.75)",
    glowEnabled: true,
    glowColor: "#00D2FF",
    glowRadius: 20,
    gradientColors: ["#FF3CAC", "#00D2FF"],
    gradientDirection: "to right",
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  /** SUNSET — Warm orange-pink-purple gradient */
  sunset_gradient: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    gradientColors: ["#FF6B35", "#FF3C64", "#8B5CF6"],
    gradientDirection: "135deg",
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  /** GOLD — Playfair Display, gold gradient, gold underline */
  gold_gradient: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    animation: "spring",
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
    activeWordScale: 1.08,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // OUTLINE
  // ═══════════════════════════════════════════════════════════════════════════

  /** OUTLINE BOLD — Thick white outline, no fill */
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
    activeWordScale: 1.12,
    speakerColors: SPEAKER_COLORS,
  },

  /** OUTLINE NEON — Cyan outline with glow */
  outline_neon: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 22,
    textStroke: { width: 2, color: "#00DCC8" },
    outlineOnly: true,
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // HANDWRITTEN / CASUAL
  // ═══════════════════════════════════════════════════════════════════════════

  /** HANDWRITTEN — Permanent Marker, organic feel */
  handwritten: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textTransform: "none",
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  /** MARKER HIGHLIGHT — Dark text on yellow highlight */
  marker_highlight: {
    ...BASE,
    fontFamily: "Permanent Marker",
    fontWeight: 400,
    animation: "spring",
    textColor: "#1A1A1A",
    activeColor: "#1A1A1A",
    dimColor: "rgba(50,50,50,0.6)",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    backgroundShape: "highlight",
    highlightColor: "#FFD700",
    shadowLayers: SHADOW_SOFT,
    textTransform: "none",
    activeWordScale: 1.08,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // COMIC / MEME
  // ═══════════════════════════════════════════════════════════════════════════

  /** COMIC — Bangers font, yellow text, thick black outline */
  comic_pop: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    textColor: "#FFD700",
    activeColor: "#FFD700",
    dimColor: "rgba(200,180,0,0.5)",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 3, color: "#000000" },
    activeWordScale: 1.15,
    keywordColors: ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7", "#3B82F6"],
    speakerColors: SPEAKER_COLORS,
  },

  /** MEME — Heavy black outline, white fill */
  meme_bold: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    textStroke: { width: 4, color: "#000000" },
    activeWordScale: 1.10,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // ELEGANT
  // ═══════════════════════════════════════════════════════════════════════════

  /** LUXURY — Playfair Display, gold underline */
  luxury: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_MEDIUM,
    backgroundShape: "underline",
    underlineColor: "#D4AF37",
    underlineThickness: 3,
    textTransform: "none",
    activeColor: "#FFD700",
    activeWordScale: 1.08,
    keywordColors: ["#D4AF37", "#FFD700", "#D4AF37", "#FFA000"],
    speakerColors: SPEAKER_COLORS,
  },

  /** EDITORIAL — Dark text on white pill, refined */
  editorial: {
    ...BASE,
    fontFamily: "Playfair Display",
    fontWeight: 700,
    textColor: "#1A1A1A",
    activeColor: "#000000",
    dimColor: "rgba(80,80,80,0.5)",
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(255,255,255,0.9)",
    pillRadius: 10,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SOFT,
    textTransform: "none",
    activeWordScale: 1.06,
    keywordColors: ["#8B5CF6", "#3B82F6", "#059669", "#DC2626"],
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // STACKED
  // ═══════════════════════════════════════════════════════════════════════════

  /** STACKED BOLD — One word per line, bold impact */
  stacked_bold: {
    ...BASE,
    fontWeight: 900,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    stackedLayout: true,
    activeWordScale: 1.15,
    speakerColors: SPEAKER_COLORS,
  },

  /** STACKED COLOR — Stacked with color cycling and glow */
  stacked_color: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 800,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(10,10,10,0.7)",
    glowEnabled: true,
    glowColor: "#FF3C64",
    glowRadius: 18,
    stackedLayout: true,
    activeWordScale: 1.12,
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // 3D / EXTRUDED
  // ═══════════════════════════════════════════════════════════════════════════

  /** RETRO 3D — Yellow text, black 3D shadow */
  retro_3d: {
    ...BASE,
    fontFamily: "Bangers",
    fontWeight: 400,
    textColor: "#FFD700",
    activeColor: "#FFD700",
    dimColor: "rgba(200,180,0,0.5)",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowExtrude: { angle: 135, distance: 5, color: "#000000" },
    activeWordScale: 1.12,
    keywordColors: ["#FF3C64", "#00DCC8", "#FF8C00", "#A855F7"],
    speakerColors: SPEAKER_COLORS,
  },

  /** NEON 3D — Cyan text, glow + subtle extrusion */
  neon_3d: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    textColor: "#00DCC8",
    activeColor: "#00FFEE",
    dimColor: "rgba(0,140,128,0.5)",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 20,
    shadowExtrude: { angle: 135, distance: 2, color: "#005F54" },
    activeWordScale: 1.10,
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#FFD700"],
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // TECH / MODERN
  // ═══════════════════════════════════════════════════════════════════════════

  /** TECH CLEAN — Space Grotesk, cyan underline */
  tech_clean: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 500,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_MEDIUM,
    backgroundShape: "underline",
    underlineColor: "#00DCC8",
    underlineThickness: 3,
    activeWordScale: 1.06,
    textTransform: "none",
    activeColor: "#00DCC8",
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#FFD700"],
    speakerColors: SPEAKER_COLORS,
  },

  /** TECH GLOW — Cyan text with glow */
  tech_glow: {
    ...BASE,
    fontFamily: "Space Grotesk",
    fontWeight: 700,
    textColor: "#00DCC8",
    activeColor: "#00FFEE",
    dimColor: "rgba(0,140,128,0.5)",
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: true,
    glowColor: "#00DCC8",
    glowRadius: 20,
    activeWordScale: 1.08,
    keywordColors: ["#00DCC8", "#3B82F6", "#A855F7", "#FFD700"],
    speakerColors: SPEAKER_COLORS,
  },

  // ═══════════════════════════════════════════════════════════════════════════
  // MINIMAL
  // ═══════════════════════════════════════════════════════════════════════════

  /** MINIMAL SANS — Poppins, clean, barely there animation */
  minimal_sans: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    animation: "spring",
    pillEnabled: false,
    pillColor: "transparent",
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_MEDIUM,
    activeWordScale: 1.05,
    textTransform: "none",
    activeColor: "#FFFFFF",
    speakerColors: SPEAKER_COLORS,
  },

  /** MINIMAL LOWER — Small pill, extremely clean */
  minimal_lower: {
    ...BASE,
    fontFamily: "Poppins",
    fontWeight: 600,
    animation: "spring",
    pillEnabled: true,
    pillColor: "rgba(8,8,8,0.5)",
    pillRadius: 8,
    pillPadding: [16, 8],
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    shadowLayers: SHADOW_SOFT,
    activeWordScale: 1.04,
    textTransform: "none",
    activeColor: "#FFFFFF",
    speakerColors: SPEAKER_COLORS,
  },
};

export function getStyleConfig(styleName: string): StyleConfig {
  return STYLE_PRESETS[styleName] || STYLE_PRESETS["captions_dynamic"];
}
