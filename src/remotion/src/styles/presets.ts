import type { StyleConfig } from "../types";

/**
 * Caption style presets — each one is a faithful recreation of a
 * specific Captions AI style, built from actual reference videos.
 *
 * Reference videos analyzed:
 *   V1: snaptik_7610116468012780813 — Volt style (confirmed via app UI)
 *   V2: snaptik_7610117567755111700 — Volt style (confirmed via "Edit style: Volt")
 *   V3: snaptik_7621679615941053726 — Clarity-like minimal style
 *   V4: snaptik_7621683684067904799 — Impact style (red keywords)
 *   Style picker thumbnails visible across V1, V2, V4
 */

// ─── Shadow presets ──────────────────────────────────────────────────────────

const SHADOW_STRONG: StyleConfig["shadowLayers"] = [
  { x: 0, y: 2, blur: 8, color: "rgba(0,0,0,0.9)" },
  { x: 0, y: 4, blur: 16, color: "rgba(0,0,0,0.5)" },
];

const SHADOW_MEDIUM: StyleConfig["shadowLayers"] = [
  { x: 0, y: 1, blur: 3, color: "rgba(0,0,0,0.9)" },
  { x: 0, y: 2, blur: 6, color: "rgba(0,0,0,0.7)" },
];

const SHADOW_SOFT: StyleConfig["shadowLayers"] = [
  { x: 0, y: 1, blur: 4, color: "rgba(0,0,0,0.5)" },
];

const SHADOW_HEAVY: StyleConfig["shadowLayers"] = [
  { x: 0, y: 2, blur: 4, color: "rgba(0,0,0,1)" },
  { x: 0, y: 4, blur: 12, color: "rgba(0,0,0,0.7)" },
  { x: 0, y: 6, blur: 24, color: "rgba(0,0,0,0.3)" },
];

const SPEAKER_COLORS = ["#FFD700", "#00E5FF", "#00FF88", "#FF44FF", "#FF8800"];

// ─── Presets ─────────────────────────────────────────────────────────────────

export const STYLE_PRESETS: Record<string, StyleConfig> = {
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // VOLT — Reference: V1 (confirmed), V2 (confirmed via app UI)
  //
  // White bold Montserrat, lowercase. Keywords pop in bright cyan/teal.
  // Strong black shadow ensures readability on any background.
  // Cascade layout: context words smaller on top line, keywords larger below.
  // Active word gets a subtle spring scale-up.
  // This is the most popular/default Captions AI style.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  volt: {
    fontFamily: "Montserrat",
    fontWeight: 800,
    lineHeight: 1.1,
    textTransform: "lowercase",
    maxWordsPerGroup: 4,
    position: "lower-third",
    yPercent: 72,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.50)",
    keywordColors: ["#00D4FF", "#00E5FF", "#00BCD4"],
    shadowLayers: SHADOW_STRONG,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "spring",
    animationDuration: 200,
    activeWordScale: 1.1,
    fadeInMs: 80,
    fadeOutMs: 100,
    textStroke: { width: 2, color: "rgba(0,0,0,0.8)" },
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // CLARITY — Reference: V3 (clean minimal single-word style)
  //
  // Ultra-clean, minimal. White Poppins SemiBold, lowercase, centered.
  // Shows 1-2 words at a time for maximum readability.
  // Keywords get a soft teal color. Very subtle shadow, no stroke.
  // No pill, no glow — pure text on video. Premium, understated feel.
  // Position is center-screen (~55%) rather than lower-third.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  clarity: {
    fontFamily: "Poppins",
    fontWeight: 600,
    lineHeight: 1.15,
    textTransform: "lowercase",
    maxWordsPerGroup: 2,
    position: "center",
    yPercent: 55,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.40)",
    keywordColors: ["#5DADE2", "#48C9B0", "#45B7D1"],
    shadowLayers: SHADOW_SOFT,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "spring",
    animationDuration: 180,
    activeWordScale: 1.08,
    fadeInMs: 60,
    fadeOutMs: 80,
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // IMPACT — Reference: V4 (white bold + red keywords)
  //
  // Bold Montserrat Black, lowercase. Keywords are vivid RED.
  // Heavy shadow for outdoor/bright backgrounds. Cascade layout.
  // "content in a click" → "content" red + large, "in a click" white + smaller.
  // Punchy, attention-grabbing. No glow, just raw bold text + red pop.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  impact: {
    fontFamily: "Montserrat",
    fontWeight: 900,
    lineHeight: 1.05,
    textTransform: "lowercase",
    maxWordsPerGroup: 3,
    position: "lower-third",
    yPercent: 78,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.45)",
    keywordColors: ["#E53935", "#FF1744", "#D50000"],
    shadowLayers: SHADOW_HEAVY,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "pop",
    animationDuration: 150,
    activeWordScale: 1.12,
    fadeInMs: 60,
    fadeOutMs: 80,
    textStroke: { width: 2.5, color: "rgba(0,0,0,0.85)" },
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // EMBER — Reference: V2 bottom captions (serif italic style)
  //
  // Elegant Playfair Display, lowercase italic feel. White text.
  // Keywords in warm gold. Positioned lower. Subtle shadow.
  // Smaller, refined text — premium/editorial vibe.
  // Used in V2 for the in-video captions (serif italic visible).
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ember: {
    fontFamily: "Playfair Display",
    fontWeight: 700,
    lineHeight: 1.15,
    textTransform: "lowercase",
    maxWordsPerGroup: 3,
    position: "lower-third",
    yPercent: 78,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.45)",
    keywordColors: ["#FFD700", "#FFA726", "#FFAB40"],
    shadowLayers: SHADOW_MEDIUM,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "spring",
    animationDuration: 200,
    activeWordScale: 1.08,
    fadeInMs: 80,
    fadeOutMs: 100,
    textStroke: { width: 1.5, color: "rgba(0,0,0,0.7)" },
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // VELOCITY — Reference: V4 style picker thumbnail
  //   "GROWTH GROWTH / BOOST YOUR BUSINESS" — bold uppercase, yellow + cyan
  //
  // High-energy Montserrat Black, UPPERCASE. Yellow keyword highlights.
  // Strong shadow + subtle glow on active words. Maximum impact.
  // Cascade layout with tight line height for stacked text blocks.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  velocity: {
    fontFamily: "Montserrat",
    fontWeight: 900,
    lineHeight: 1.0,
    textTransform: "uppercase",
    maxWordsPerGroup: 3,
    position: "lower-third",
    yPercent: 70,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#FFD700",
    dimColor: "rgba(255,255,255,0.50)",
    keywordColors: ["#FFD700", "#00E5FF", "#FFC107"],
    shadowLayers: SHADOW_HEAVY,
    glowEnabled: true,
    glowColor: "#FFD700",
    glowRadius: 12,
    animation: "pop",
    animationDuration: 150,
    activeWordScale: 1.12,
    fadeInMs: 60,
    fadeOutMs: 80,
    textStroke: { width: 3, color: "rgba(0,0,0,0.9)" },
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // ARCHIVE — Reference: V1/V4 style picker thumbnail
  //   "THE GUIDELINE TO ACHIEVE" — condensed uppercase, gold accent, dark mood
  //
  // Oswald condensed, uppercase, off-white with gold keyword accents.
  // Strong shadow for dramatic/cinematic feel. No glow, no pill.
  // Documentary/archive aesthetic — serious, authoritative.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  archive: {
    fontFamily: "Oswald",
    fontWeight: 700,
    lineHeight: 1.05,
    textTransform: "uppercase",
    maxWordsPerGroup: 4,
    position: "lower-third",
    yPercent: 75,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#E8E8E8",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.40)",
    keywordColors: ["#C8AA6E", "#D4AF37", "#BFA15A"],
    shadowLayers: SHADOW_STRONG,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "spring",
    animationDuration: 200,
    activeWordScale: 1.1,
    fadeInMs: 80,
    fadeOutMs: 100,
    textStroke: { width: 2, color: "rgba(0,0,0,0.85)" },
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // LUMEN — Reference: V2/V4 style picker thumbnail
  //   "one thing I can do" + "ENCOURAGE" label — teal/green accent, pill bg
  //
  // Clean Poppins, lowercase. Teal/green keyword colors.
  // Semi-transparent dark pill background for text readability.
  // Wave animation for smooth word-by-word reveal. Elegant, modern.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  lumen: {
    fontFamily: "Poppins",
    fontWeight: 700,
    lineHeight: 1.15,
    textTransform: "lowercase",
    maxWordsPerGroup: 4,
    position: "center",
    yPercent: 65,
    pillEnabled: true,
    pillColor: "rgba(0,0,0,0.35)",
    pillRadius: 12,
    pillPadding: [16, 10],
    textColor: "#FFFFFF",
    activeColor: "#FFFFFF",
    dimColor: "rgba(255,255,255,0.50)",
    keywordColors: ["#00E5A0", "#00D4AA", "#26A69A"],
    shadowLayers: SHADOW_SOFT,
    glowEnabled: false,
    glowColor: "transparent",
    glowRadius: 0,
    animation: "wave",
    animationDuration: 180,
    activeWordScale: 1.06,
    fadeInMs: 80,
    fadeOutMs: 100,
    backgroundShape: "pill",
    speakerColors: SPEAKER_COLORS,
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // REBEL — Reference: V2 style picker thumbnail
  //   Bold green/lime text, energetic, italic feel
  //
  // Montserrat ExtraBold, lowercase. Lime/green keyword pops.
  // Subtle glow on keywords. Strong shadow. Edgy, youthful.
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  rebel: {
    fontFamily: "Montserrat",
    fontWeight: 800,
    lineHeight: 1.05,
    textTransform: "lowercase",
    maxWordsPerGroup: 3,
    position: "lower-third",
    yPercent: 72,
    pillEnabled: false,
    pillColor: "transparent",
    pillRadius: 0,
    pillPadding: [0, 0],
    textColor: "#FFFFFF",
    activeColor: "#CDDC39",
    dimColor: "rgba(255,255,255,0.45)",
    keywordColors: ["#CDDC39", "#76FF03", "#C6FF00"],
    shadowLayers: SHADOW_STRONG,
    glowEnabled: true,
    glowColor: "#76FF03",
    glowRadius: 10,
    animation: "spring",
    animationDuration: 180,
    activeWordScale: 1.1,
    fadeInMs: 70,
    fadeOutMs: 90,
    textStroke: { width: 2.5, color: "rgba(0,0,0,0.85)" },
    speakerColors: SPEAKER_COLORS,
  },
};

export function getStyleConfig(styleName: string): StyleConfig {
  const first = Object.values(STYLE_PRESETS)[0];
  return STYLE_PRESETS[styleName] || first;
}
