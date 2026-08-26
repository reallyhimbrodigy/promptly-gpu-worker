import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadDMSerifDisplay } from "@remotion/google-fonts/DMSerifDisplay";
import { loadFont as loadPlayfairDisplay } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadCaveatBrush } from "@remotion/google-fonts/CaveatBrush";
import { loadFont as loadOswald } from "@remotion/google-fonts/Oswald";
import { loadFont as loadRoboto } from "@remotion/google-fonts/Roboto";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadNotoSansDevanagari } from "@remotion/google-fonts/NotoSansDevanagari";
import { loadFont as loadNotoSansBengali } from "@remotion/google-fonts/NotoSansBengali";
import { loadFont as loadNotoSansTelugu } from "@remotion/google-fonts/NotoSansTelugu";
import { loadFont as loadNotoSansArabic } from "@remotion/google-fonts/NotoSansArabic";

// Remotion convention (adopted 2026-08-24, their own AGENTS.md guidance): an
// optionless loadFont() downloads EVERY weight and subset — our archive logs
// printed the SDK's own warning (63-126 requests per family per render).
// Weights below are the census of what the catalogue actually sets
// (including the FONT_WEIGHT indirection maps); subsets latin + latin-ext
// (user tags carry accents). A weight not listed here silently synthesizes —
// add it HERE when a component starts using it.
const SUBSETS = ["latin", "latin-ext"] as const;
// Cyrillic is 2.8% of measured MG traffic and an AVAILABLE subset of the
// body faces — loading it is nearly free (catalogue font-coverage census,
// 2026-08-26). The display faces (Anton/DMSerif/Playfair/CaveatBrush) have
// no Cyrillic; mgTextFont routes Cyrillic display text to Oswald.
const inter = loadInter("normal", { weights: ["400", "500", "600", "700", "800", "900"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
const anton = loadAnton("normal", { weights: ["400"], subsets: [...SUBSETS] });
const dmSerifDisplay = loadDMSerifDisplay("normal", { weights: ["400"], subsets: [...SUBSETS] });
const playfairDisplay = loadPlayfairDisplay("normal", { weights: ["400", "700"], subsets: [...SUBSETS] });
const caveatBrush = loadCaveatBrush("normal", { weights: ["400"], subsets: [...SUBSETS] });
const oswald = loadOswald("normal", { weights: ["400", "600", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
const roboto = loadRoboto("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS, "cyrillic", "cyrillic-ext"] });
const jetBrainsMono = loadJetBrainsMono("normal", { weights: ["400", "500", "700"], subsets: [...SUBSETS] });
// Devanagari coverage (pass #9): the display faces above are latin-only —
// Anton has NO Devanagari, so a Hindi title silently fell back to an unstyled
// system face (render-caught on SectionDivider's live placement). Components
// that show USER/model text detect script by Unicode range and route here.
const notoSansDevanagari = loadNotoSansDevanagari("normal", { weights: ["400", "700"], subsets: ["devanagari", "latin"] });
// Bengali 2.8% / Telugu 1.5% / Arabic 1.0% of measured MG traffic (14d
// census). CJK (1.0%) deliberately NOT loaded — a Chinese face roughly
// doubles the font payload for 1% of traffic; CJK placements render the
// preferred face's fallback and are FLAGGED for a separate ruling (see
// mgTextFont).
const notoSansBengali = loadNotoSansBengali("normal", { weights: ["400", "700"], subsets: ["bengali", "latin"] });
const notoSansTelugu = loadNotoSansTelugu("normal", { weights: ["400", "700"], subsets: ["telugu", "latin"] });
const notoSansArabic = loadNotoSansArabic("normal", { weights: ["400", "700"], subsets: ["arabic"] });

export const MG_FONTS = {
  inter: inter.fontFamily,
  anton: anton.fontFamily,
  dmSerifDisplay: dmSerifDisplay.fontFamily,
  playfairDisplay: playfairDisplay.fontFamily,
  caveatBrush: caveatBrush.fontFamily,
  oswald: oswald.fontFamily,
  roboto: roboto.fontFamily,
  jetBrainsMono: jetBrainsMono.fontFamily,
  notoSansDevanagari: notoSansDevanagari.fontFamily,
  notoSansBengali: notoSansBengali.fontFamily,
  notoSansTelugu: notoSansTelugu.fontFamily,
  notoSansArabic: notoSansArabic.fontFamily,
} as const;
