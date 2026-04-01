import type { VisualEffect, CutPoint, EmphasisMoment, OverlayInput } from "../types";

/**
 * Vibe-based effect presets.
 * Given a vibe, cuts, and emphasis moments, generates the right
 * combination of visual effects automatically.
 *
 * This is the intelligence layer — it knows which effects work
 * together and when to deploy them.
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

/** Random emoji for emphasis moments based on vibe */
const VIBE_EMOJIS: Record<VibeCategory, string[]> = {
  cinematic: [],
  hype: ["🔥", "💥", "⚡", "🚀", "💯", "😤"],
  motivational: ["💪", "🔥", "👑", "💰", "🏆"],
  aesthetic: [],
  comedy: ["😂", "💀", "🤣", "😭", "🫠"],
  dramatic: ["😱", "🤯"],
  chill: [],
  retro: [],
  professional: [],
  default: ["🔥", "💥"],
};

/**
 * Generate visual effects for the entire video based on vibe, cuts, and emphasis moments.
 */
export function generateEffects(input: OverlayInput): VisualEffect[] {
  const effects: VisualEffect[] = [];
  const vibeCategory = classifyVibe(input.vibe);
  const { cuts, emphasisMoments, duration } = input;

  // === AMBIENT EFFECTS (span most of the video) ===

  // Ambient particles based on vibe
  if (["cinematic", "aesthetic", "dramatic"].includes(vibeCategory)) {
    effects.push({
      type: "particle_ambient",
      start: 0,
      end: duration,
      params: { style: "bokeh", count: 20, intensity: 0.5 },
    });
  } else if (vibeCategory === "chill") {
    effects.push({
      type: "particle_ambient",
      start: 0,
      end: duration,
      params: { style: "dust", count: 18, intensity: 0.35 },
    });
  } else if (vibeCategory === "retro") {
    effects.push({
      type: "particle_ambient",
      start: 0,
      end: duration,
      params: { style: "dust", count: 16, intensity: 0.4 },
    });
  }

  // VHS grain for retro vibe
  if (vibeCategory === "retro") {
    effects.push({
      type: "vhs_grain",
      start: 0,
      end: duration,
      params: { style: "vhs", intensity: 0.5 },
    });
  } else if (vibeCategory === "cinematic") {
    effects.push({
      type: "vhs_grain",
      start: 0,
      end: duration,
      params: { style: "film", intensity: 0.25 },
    });
  }

  // === CUT-BASED EFFECTS (at transition points) ===

  const cutTimes = cuts.map((c) => c.time).filter((ct) => ct > 0.5 && ct < duration - 0.5);

  for (let i = 0; i < cutTimes.length; i++) {
    const ct = cutTimes[i];
    // Alternate between transition effects for variety
    if (vibeCategory === "hype" || vibeCategory === "comedy") {
      // Fast vibes: glitch on every other cut, whip pan on the rest
      if (i % 3 === 0) {
        effects.push({
          type: "glitch",
          start: ct - 0.05,
          end: ct + 0.12,
          params: { intensity: 0.8, color: "rgb" },
        });
      } else if (i % 3 === 1) {
        effects.push({
          type: "whip_pan",
          start: ct - 0.08,
          end: ct + 0.08,
          params: { direction: i % 2 === 0 ? "right" : "left", intensity: 0.7 },
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
      // Cinematic: zoom blur transitions, occasional light leak
      if (i % 2 === 0) {
        effects.push({
          type: "zoom_blur_transition",
          start: ct - 0.1,
          end: ct + 0.1,
          params: { intensity: 0.6, color: "dark" },
        });
      }
      if (i % 3 === 0) {
        effects.push({
          type: "light_leak",
          start: ct - 0.2,
          end: ct + 0.8,
          params: { color: vibeCategory === "dramatic" ? "cool" : "warm", intensity: 0.5 },
        });
      }
    } else if (vibeCategory === "aesthetic" || vibeCategory === "chill") {
      // Soft: light leaks on cuts
      if (i % 2 === 0) {
        effects.push({
          type: "light_leak",
          start: ct - 0.3,
          end: ct + 1.0,
          params: { color: "golden", intensity: 0.4 },
        });
      }
    } else if (vibeCategory === "motivational") {
      // Impact flashes + whip pans
      if (i % 2 === 0) {
        effects.push({
          type: "impact_flash",
          start: ct - 0.02,
          end: ct + 0.1,
          params: { color: "warm", intensity: 0.7 },
        });
      } else {
        effects.push({
          type: "whip_pan",
          start: ct - 0.06,
          end: ct + 0.06,
          params: { direction: i % 2 === 0 ? "right" : "left", intensity: 0.6 },
        });
      }
    } else {
      // Default: subtle zoom blur on cuts
      if (i % 2 === 0) {
        effects.push({
          type: "zoom_blur_transition",
          start: ct - 0.08,
          end: ct + 0.08,
          params: { intensity: 0.5 },
        });
      }
    }
  }

  // === EMPHASIS-BASED EFFECTS ===

  for (const em of emphasisMoments) {
    const emT = em.t;
    const isHigh = em.intensity === "high";

    // Vignette pulse on all emphasis moments
    effects.push({
      type: "vignette_pulse",
      start: emT - 0.05,
      end: emT + (isHigh ? 0.5 : 0.3),
      params: {
        intensity: isHigh ? 0.7 : 0.45,
        color: vibeCategory === "cinematic" ? "cool" : "black",
      },
    });

    // Edge glow on high-intensity moments
    if (isHigh) {
      const glowColors: Record<VibeCategory, string> = {
        cinematic: "blue",
        hype: "cyan",
        motivational: "gold",
        aesthetic: "pink",
        comedy: "purple",
        dramatic: "red",
        chill: "white",
        retro: "pink",
        professional: "cyan",
        default: "cyan",
      };
      effects.push({
        type: "edge_glow",
        start: emT - 0.05,
        end: emT + 0.4,
        params: { color: glowColors[vibeCategory], intensity: 0.6, pulse: false },
      });
    }

    // Impact flash on high-intensity punchlines/revelations
    if (isHigh && (em.type === "punchline" || em.type === "revelation")) {
      effects.push({
        type: "impact_flash",
        start: emT - 0.02,
        end: emT + 0.08,
        params: { color: "white", intensity: 0.75 },
      });
    }

    // Particle burst on high-intensity moments (hype/comedy/motivational)
    if (isHigh && ["hype", "comedy", "motivational"].includes(vibeCategory)) {
      effects.push({
        type: "particle_burst",
        start: emT - 0.02,
        end: emT + 0.8,
        params: {
          style: vibeCategory === "comedy" ? "confetti" : "sparkle",
          count: 40,
          originX: 0.5,
          originY: 0.4,
        },
      });
    }

    // Emoji pop on emphasis (hype/comedy/motivational only)
    const emojis = VIBE_EMOJIS[vibeCategory];
    if (emojis.length > 0 && isHigh) {
      const emojiIdx = emphasisMoments.indexOf(em) % emojis.length;
      effects.push({
        type: "emoji_pop",
        start: emT,
        end: emT + 0.8,
        params: { emoji: emojis[emojiIdx], size: 140, x: 0.8, y: 0.25 },
      });
    }

    // Color flash on reactions/questions
    if (em.type === "reaction" || em.type === "question") {
      const flashColors: Record<VibeCategory, string> = {
        cinematic: "blue",
        hype: "cyan",
        motivational: "gold",
        aesthetic: "pink",
        comedy: "purple",
        dramatic: "red",
        chill: "teal",
        retro: "orange",
        professional: "blue",
        default: "cyan",
      };
      effects.push({
        type: "color_flash",
        start: emT - 0.02,
        end: emT + 0.2,
        params: { color: flashColors[vibeCategory], intensity: 0.35 },
      });
    }
  }

  // === CINEMATIC LETTERBOX (dramatic/cinematic vibes only) ===

  if (vibeCategory === "cinematic" || vibeCategory === "dramatic") {
    // Letterbox on the most dramatic emphasis moment
    const highMoments = emphasisMoments.filter((em) => em.intensity === "high");
    if (highMoments.length > 0) {
      const peak = highMoments[0];
      effects.push({
        type: "letterbox_cinematic",
        start: peak.t - 0.3,
        end: peak.t + 1.5,
        params: { barHeight: 0.08 },
      });
    }
  }

  // === LIGHT LEAKS (cinematic/aesthetic ambient) ===

  if (["cinematic", "aesthetic", "chill"].includes(vibeCategory)) {
    // Scattered ambient light leaks throughout the video
    const leakInterval = vibeCategory === "aesthetic" ? 4 : 6;
    for (let lt = 2; lt < duration - 2; lt += leakInterval) {
      const leakColors = ["warm", "golden", "prismatic"];
      effects.push({
        type: "light_leak",
        start: lt,
        end: lt + 1.5,
        params: {
          color: leakColors[Math.floor(lt / leakInterval) % leakColors.length],
          intensity: 0.35,
        },
      });
    }
  }

  return effects;
}
