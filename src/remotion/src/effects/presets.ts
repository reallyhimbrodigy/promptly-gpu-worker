import type { VisualEffect, CutPoint, EmphasisMoment, OverlayInput } from "../types";

/**
 * Vibe-based effect presets — Captions AI quality.
 *
 * Given a vibe, cuts, emphasis moments, and word data, generates the complete
 * set of visual effects automatically:
 *
 * CUT-BASED: impact_flash, warm_flash, whip_pan_blur, glitch, color_flash
 * EMPHASIS-BASED: cascade_echo, impact_text, blur_card, vignette_pulse
 *
 * Design principles from studying V1-V4:
 * - V1/V2: Whoosh SFX + impact flash on every cut (~1.5-2s intervals)
 * - V1: Warm flash/light leak as scene divider
 * - V3: Whip pan blur transitions between scenes
 * - V4: Background blur text cards for dramatic emphasis
 * - All: Cascade echo and impact text for key emotional moments
 * - High-intensity emphasis moments get cascade_echo (stacked text) or
 *   impact_text (full-screen text), chosen based on emphasis type
 */

type VibeCategory =
  | "cinematic"
  | "hype"
  | "motivational"
  | "aesthetic"
  | "comedy"
  | "dramatic"
  | "chill"
  | "retro"
  | "professional"
  | "default";

const VIBE_KEYWORDS: Record<VibeCategory, string[]> = {
  cinematic: ["cinematic", "film", "movie", "dramatic", "epic", "dark", "moody", "suspense"],
  hype: ["hype", "energy", "fast", "trend", "viral", "lit", "fire", "crazy", "insane"],
  motivational: ["motivational", "grind", "hustle", "inspirational", "mindset", "success", "business"],
  aesthetic: ["aesthetic", "lifestyle", "travel", "beautiful", "dreamy", "soft", "vibes"],
  comedy: ["comedy", "funny", "humor", "skit", "joke", "meme", "chaotic"],
  dramatic: ["dramatic", "intense", "reveal", "suspense", "shocking", "emotional"],
  chill: ["chill", "calm", "relaxed", "peaceful", "lofi", "cozy", "gentle"],
  retro: ["retro", "vintage", "vhs", "analog", "throwback", "nostalgic", "90s", "80s"],
  professional: ["professional", "clean", "corporate", "polished", "premium"],
  default: [],
};

function classifyVibe(vibe: string): VibeCategory {
  const lower = vibe.toLowerCase();
  for (const [category, keywords] of Object.entries(VIBE_KEYWORDS) as [VibeCategory, string[]][]) {
    if (category === "default") continue;
    if (keywords.some((kw) => lower.includes(kw))) return category;
  }
  return "default";
}

// Color palettes per vibe for emphasis effects
const VIBE_COLORS: Record<VibeCategory, { primary: string; secondary: string; accent: string }> = {
  cinematic: { primary: "#FFFFFF", secondary: "#87CEEB", accent: "#3B82F6" },
  hype: { primary: "#FF3C64", secondary: "#FFD700", accent: "#00DCC8" },
  motivational: { primary: "#FFD700", secondary: "#FFFFFF", accent: "#FF8C00" },
  aesthetic: { primary: "#E0B0FF", secondary: "#87CEEB", accent: "#FFB6C1" },
  comedy: { primary: "#FFD700", secondary: "#FF3C64", accent: "#00DCC8" },
  dramatic: { primary: "#FFFFFF", secondary: "#FF3C64", accent: "#A855F7" },
  chill: { primary: "#87CEEB", secondary: "#FFFFFF", accent: "#00DCC8" },
  retro: { primary: "#FFD700", secondary: "#FF6B35", accent: "#A855F7" },
  professional: { primary: "#FFFFFF", secondary: "#00DCC8", accent: "#3B82F6" },
  default: { primary: "#00D4FF", secondary: "#FFD700", accent: "#FF3C64" },
};

/**
 * Generate visual effects for the entire video based on vibe, cuts, and emphasis moments.
 *
 * Captions AI style: clean video with ONLY captions — no flashes, glitches, shakes,
 * blur cards, whip pans, or vignette pulses. The video speaks for itself.
 * Only cascade_echo and impact_text are kept as they are the signature
 * Captions AI emphasis text overlays (large bold words at key moments).
 */
export function generateEffects(input: OverlayInput): VisualEffect[] {
  const effects: VisualEffect[] = [];
  const vibeCategory = classifyVibe(input.vibe);
  const { emphasisMoments } = input;
  const colors = VIBE_COLORS[vibeCategory];

  // Only generate emphasis text effects — no cut-based flashes/glitches/etc.
  let cascadeCount = 0;
  let impactTextCount = 0;

  for (const em of emphasisMoments) {
    const emT = em.t;
    const isHigh = em.intensity === "high";
    const emDuration = em.duration || (isHigh ? 2.5 : 1.5);
    const hasWord = !!em.word;

    // Cascade Echo: stacked text for punchline/revelation moments
    if (
      isHigh &&
      hasWord &&
      cascadeCount < 2 &&
      (em.type === "punchline" || em.type === "revelation")
    ) {
      effects.push({
        type: "cascade_echo",
        start: emT - 0.1,
        end: emT + emDuration,
        params: {
          word: em.word!.toUpperCase(),
          color: colors.primary,
          outlineColor: colors.primary,
          rows: 5,
          italic: true,
        },
      });
      cascadeCount++;
    }
    // Impact Text: large bold text for key statements
    else if (isHigh && hasWord && impactTextCount < 2) {
      const words = em.word!.split(" ");
      const isMultiWord = words.length >= 2;
      const text = isMultiWord
        ? words.slice(0, Math.ceil(words.length / 2)).join(" ") +
          "\n" +
          words.slice(Math.ceil(words.length / 2)).join(" ")
        : em.word!;

      effects.push({
        type: "impact_text",
        start: emT - 0.1,
        end: emT + emDuration,
        params: {
          text: text.toUpperCase(),
          color1: colors.secondary,
          color2: colors.primary,
          position: em.type === "revelation" ? "center" : "top",
          scanlines: false,
        },
      });
      impactTextCount++;
    }
  }

  return effects;
}
