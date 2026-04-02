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
 */
export function generateEffects(input: OverlayInput): VisualEffect[] {
  const effects: VisualEffect[] = [];
  const vibeCategory = classifyVibe(input.vibe);
  const { cuts, emphasisMoments, duration } = input;
  const colors = VIBE_COLORS[vibeCategory];

  // === CUT-BASED EFFECTS ===
  const cutTimes = cuts.map((c) => c.time).filter((ct) => ct > 0.5 && ct < duration - 0.5);

  for (let i = 0; i < cutTimes.length; i++) {
    const ct = cutTimes[i];

    // Impact flash on cuts — observed on every cut in V1/V2
    if (vibeCategory === "hype" || vibeCategory === "comedy") {
      if (i % 3 === 0) {
        effects.push({
          type: "glitch",
          start: ct - 0.05,
          end: ct + 0.12,
          params: { intensity: 0.8 },
        });
      } else {
        effects.push({
          type: "impact_flash",
          start: ct - 0.02,
          end: ct + 0.08,
          params: { color: "white", intensity: 0.65 },
        });
      }
    } else if (vibeCategory === "cinematic" || vibeCategory === "dramatic") {
      // Alternate between color flash and impact flash
      if (i % 3 === 0) {
        effects.push({
          type: "color_flash",
          start: ct - 0.05,
          end: ct + 0.2,
          params: { color: "blue", intensity: 0.35 },
        });
      }
      if (i % 2 === 0) {
        effects.push({
          type: "impact_flash",
          start: ct - 0.02,
          end: ct + 0.08,
          params: { color: "white", intensity: 0.6 },
        });
      }
    } else if (vibeCategory === "motivational") {
      effects.push({
        type: "impact_flash",
        start: ct - 0.02,
        end: ct + 0.1,
        params: { color: "warm", intensity: 0.7 },
      });
    } else if (vibeCategory === "aesthetic" || vibeCategory === "chill") {
      // Subtle warm flash on every 3rd cut — gentle, not aggressive
      if (i % 3 === 0) {
        effects.push({
          type: "warm_flash",
          start: ct - 0.05,
          end: ct + 0.3,
          params: { intensity: 0.4 },
        });
      }
    } else {
      // Default: impact flash on every other cut
      if (i % 2 === 0) {
        effects.push({
          type: "impact_flash",
          start: ct - 0.02,
          end: ct + 0.08,
          params: { color: "white", intensity: 0.6 },
        });
      }
    }

    // Whip pan blur: on every 5th cut for dynamic vibes (observed in V3)
    if (i % 5 === 2 && (vibeCategory === "hype" || vibeCategory === "dramatic" || vibeCategory === "default")) {
      effects.push({
        type: "whip_pan_blur",
        start: ct - 0.08,
        end: ct + 0.12,
        params: { intensity: 0.7, direction: i % 2 === 0 ? "right" : "left" },
      });
    }

    // Warm flash as scene divider: once per ~10 cuts (observed in V1)
    // Reduced intensity — it was drowning out cascade echo text
    if (i > 0 && i % 8 === 0 && vibeCategory !== "chill" && vibeCategory !== "professional") {
      effects.push({
        type: "warm_flash",
        start: ct - 0.1,
        end: ct + 0.25,
        params: { intensity: 0.45 },
      });
    }
  }

  // === EMPHASIS-BASED EFFECTS ===

  let cascadeCount = 0; // Limit cascade echo to max 2-3 per video
  let impactTextCount = 0; // Limit impact text to max 3-4 per video
  let blurCardCount = 0; // Limit blur cards to max 1-2 per video

  // Track time ranges where cascade_echo or impact_text are active
  // so we can suppress warm_flash/impact_flash that would drown them out
  const emphasisActiveRanges: { start: number; end: number }[] = [];

  for (let emIdx = 0; emIdx < emphasisMoments.length; emIdx++) {
    const em = emphasisMoments[emIdx];
    const emT = em.t;
    const isHigh = em.intensity === "high";
    const emDuration = em.duration || (isHigh ? 2.5 : 1.5);
    const hasWord = !!em.word;

    // ── Vignette pulse on ALL emphasis moments (all vibes) ──────────────
    effects.push({
      type: "vignette_pulse",
      start: emT - 0.05,
      end: emT + (isHigh ? 0.5 : 0.3),
      params: { intensity: isHigh ? 0.7 : 0.45 },
    });

    // ── Cascade Echo: high-intensity punchline/revelation with a word ────
    // The dramatic "SKEPTIC" / "RESULT" / "EDITING" stacked text effect
    if (
      isHigh &&
      hasWord &&
      cascadeCount < 3 &&
      (em.type === "punchline" || em.type === "revelation" || em.type === "statement")
    ) {
      const ceStart = emT - 0.1;
      const ceEnd = emT + emDuration;
      effects.push({
        type: "cascade_echo",
        start: ceStart,
        end: ceEnd,
        params: {
          word: em.word!.toUpperCase(),
          color: colors.primary,
          outlineColor: colors.primary,
          rows: 5,
          italic: true,
        },
      });
      emphasisActiveRanges.push({ start: ceStart, end: ceEnd });
      cascadeCount++;
    }
    // ── Impact Text: feature callouts, dramatic statements ───────────────
    // The "EASY EDITING" / "CREATE CONTENT" / "dynamic transitions" effect
    else if (
      isHigh &&
      hasWord &&
      impactTextCount < 4
    ) {
      // Two-tone: split on space if multi-word
      const words = em.word!.split(" ");
      const isMultiWord = words.length >= 2;
      const text = isMultiWord
        ? words.slice(0, Math.ceil(words.length / 2)).join(" ") +
          "\n" +
          words.slice(Math.ceil(words.length / 2)).join(" ")
        : em.word!;

      const itStart = emT - 0.1;
      const itEnd = emT + emDuration;
      effects.push({
        type: "impact_text",
        start: itStart,
        end: itEnd,
        params: {
          text: text.toUpperCase(),
          color1: colors.secondary,
          color2: colors.primary,
          position: em.type === "revelation" ? "center" : "top",
          scanlines: vibeCategory === "hype" || vibeCategory === "retro",
        },
      });
      emphasisActiveRanges.push({ start: itStart, end: itEnd });
      impactTextCount++;
    }

    // ── Blur Card: for medium-intensity moments with text ────────────────
    // The V4 heavy-blur-with-sharp-text effect
    if (
      !isHigh &&
      hasWord &&
      blurCardCount < 2 &&
      em.type === "statement" &&
      vibeCategory !== "chill"
    ) {
      effects.push({
        type: "blur_card",
        start: emT - 0.1,
        end: emT + emDuration,
        params: {
          text: em.word!.toUpperCase(),
          color: "#FFFFFF",
          bgOpacity: 0.65,
        },
      });
      blurCardCount++;
    }

    // ── Impact flash on high-intensity punchline/revelation ──────────────
    if (isHigh && (em.type === "punchline" || em.type === "revelation")) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.08,
        params: { color: "white", intensity: 0.75 },
      });
    }

    // ── Vibe-specific emphasis effects ───────────────────────────────────
    if ((vibeCategory === "hype" || vibeCategory === "comedy") && isHigh) {
      if (emIdx % 3 === 0) {
        effects.push({
          type: "glitch",
          start: emT - 0.03,
          end: emT + 0.15,
          params: { intensity: 0.7 },
        });
      }
    }

    if ((vibeCategory === "cinematic" || vibeCategory === "dramatic") && isHigh) {
      effects.push({
        type: "color_flash",
        start: emT - 0.02,
        end: emT + 0.25,
        params: { color: "blue", intensity: 0.3 },
      });
    }

    if (vibeCategory === "motivational" && isHigh) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.1,
        params: { color: "warm", intensity: 0.7 },
      });
    }
  }

  // Filter out warm_flash effects that overlap with cascade_echo / impact_text
  // These full-screen color washes drown out the emphasis text
  if (emphasisActiveRanges.length > 0) {
    const overlaps = (start: number, end: number) =>
      emphasisActiveRanges.some(
        (r) => start < r.end && end > r.start
      );

    return effects.filter((e) => {
      if (e.type === "warm_flash" && overlaps(e.start, e.end)) return false;
      // Suppress impact_flash that lands inside cascade_echo / impact_text
      // — the bright white flash washes out the emphasis text
      if (e.type === "impact_flash" && overlaps(e.start, e.end)) return false;
      return true;
    });
  }

  return effects;
}
