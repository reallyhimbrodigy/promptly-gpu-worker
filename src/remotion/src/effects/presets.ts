import type { VisualEffect, CutPoint, EmphasisMoment, OverlayInput } from "../types";

/**
 * Vibe-based effect presets.
 * Given a vibe, cuts, and emphasis moments, generates the right
 * combination of visual effects automatically.
 *
 * Simplified to only generate the 4 effects we actually render:
 * impact_flash, vignette_pulse, color_flash, glitch.
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

/**
 * Generate visual effects for the entire video based on vibe, cuts, and emphasis moments.
 */
export function generateEffects(input: OverlayInput): VisualEffect[] {
  const effects: VisualEffect[] = [];
  const vibeCategory = classifyVibe(input.vibe);
  const { cuts, emphasisMoments, duration } = input;

  // === CUT-BASED EFFECTS ===

  const cutTimes = cuts.map((c) => c.time).filter((ct) => ct > 0.5 && ct < duration - 0.5);

  for (let i = 0; i < cutTimes.length; i++) {
    const ct = cutTimes[i];

    if (vibeCategory === "hype" || vibeCategory === "comedy") {
      // Glitch on every 3rd cut, impact flash on the rest
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
      // Color flash (blue) on cuts
      if (i % 2 === 0) {
        effects.push({
          type: "color_flash",
          start: ct - 0.05,
          end: ct + 0.2,
          params: { color: "blue", intensity: 0.35 },
        });
      }
      // Impact flash on every 3rd cut
      if (i % 3 === 0) {
        effects.push({
          type: "impact_flash",
          start: ct - 0.02,
          end: ct + 0.08,
          params: { color: "white", intensity: 0.6 },
        });
      }
    } else if (vibeCategory === "motivational") {
      // Impact flash on all cuts
      effects.push({
        type: "impact_flash",
        start: ct - 0.02,
        end: ct + 0.1,
        params: { color: "warm", intensity: 0.7 },
      });
    }
    // default/aesthetic/chill/retro/professional: no cut effects
  }

  // === EMPHASIS-BASED EFFECTS ===

  for (const em of emphasisMoments) {
    const emT = em.t;
    const isHigh = em.intensity === "high";

    // Vignette pulse on ALL emphasis moments (all vibes)
    effects.push({
      type: "vignette_pulse",
      start: emT - 0.05,
      end: emT + (isHigh ? 0.5 : 0.3),
      params: {
        intensity: isHigh ? 0.7 : 0.45,
      },
    });

    // Impact flash on all high-intensity punchline/revelation moments (all vibes)
    if (isHigh && (em.type === "punchline" || em.type === "revelation")) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.08,
        params: { color: "white", intensity: 0.75 },
      });
    }

    // Hype/comedy: glitch on every 3rd emphasis, impact flash on high
    if ((vibeCategory === "hype" || vibeCategory === "comedy") && isHigh) {
      const emIdx = emphasisMoments.indexOf(em);
      if (emIdx % 3 === 0) {
        effects.push({
          type: "glitch",
          start: emT - 0.03,
          end: emT + 0.15,
          params: { intensity: 0.7 },
        });
      } else {
        effects.push({
          type: "impact_flash",
          start: emT - 0.02,
          end: emT + 0.1,
          params: { color: "white", intensity: 0.7 },
        });
      }
    }

    // Cinematic/dramatic: color flash (blue) on high emphasis
    if ((vibeCategory === "cinematic" || vibeCategory === "dramatic") && isHigh) {
      effects.push({
        type: "color_flash",
        start: emT - 0.02,
        end: emT + 0.25,
        params: { color: "blue", intensity: 0.3 },
      });
    }

    // Motivational: impact flash on all high emphasis
    if (vibeCategory === "motivational" && isHigh) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.1,
        params: { color: "warm", intensity: 0.7 },
      });
    }

    // Default: impact flash on high emphasis only
    if (vibeCategory === "default" && isHigh) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.08,
        params: { color: "white", intensity: 0.65 },
      });
    }
  }

  return effects;
}
