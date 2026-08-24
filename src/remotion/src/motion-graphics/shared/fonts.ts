import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadDMSerifDisplay } from "@remotion/google-fonts/DMSerifDisplay";
import { loadFont as loadPlayfairDisplay } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadCaveatBrush } from "@remotion/google-fonts/CaveatBrush";
import { loadFont as loadOswald } from "@remotion/google-fonts/Oswald";
import { loadFont as loadRoboto } from "@remotion/google-fonts/Roboto";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";

// Remotion convention (adopted 2026-08-24, their own AGENTS.md guidance): an
// optionless loadFont() downloads EVERY weight and subset — our archive logs
// printed the SDK's own warning (63-126 requests per family per render).
// Weights below are the census of what the catalogue actually sets
// (including the FONT_WEIGHT indirection maps); subsets latin + latin-ext
// (user tags carry accents). A weight not listed here silently synthesizes —
// add it HERE when a component starts using it.
const SUBSETS = ["latin", "latin-ext"] as const;
const inter = loadInter("normal", { weights: ["400", "500", "600", "700", "800", "900"], subsets: [...SUBSETS] });
const anton = loadAnton("normal", { weights: ["400"], subsets: [...SUBSETS] });
const dmSerifDisplay = loadDMSerifDisplay("normal", { weights: ["400"], subsets: [...SUBSETS] });
const playfairDisplay = loadPlayfairDisplay("normal", { weights: ["400", "700"], subsets: [...SUBSETS] });
const caveatBrush = loadCaveatBrush("normal", { weights: ["400"], subsets: [...SUBSETS] });
const oswald = loadOswald("normal", { weights: ["400", "600", "700"], subsets: [...SUBSETS] });
const roboto = loadRoboto("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS] });
const jetBrainsMono = loadJetBrainsMono("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS] });

export const MG_FONTS = {
  inter: inter.fontFamily,
  anton: anton.fontFamily,
  dmSerifDisplay: dmSerifDisplay.fontFamily,
  playfairDisplay: playfairDisplay.fontFamily,
  caveatBrush: caveatBrush.fontFamily,
  oswald: oswald.fontFamily,
  roboto: roboto.fontFamily,
  jetBrainsMono: jetBrainsMono.fontFamily,
} as const;
