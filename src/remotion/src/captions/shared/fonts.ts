import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadMontserrat } from "@remotion/google-fonts/Montserrat";
import { loadFont as loadPoppins } from "@remotion/google-fonts/Poppins";
import { loadFont as loadPlayfairDisplay } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadDMSerifDisplay } from "@remotion/google-fonts/DMSerifDisplay";
import { loadFont as loadDMSans } from "@remotion/google-fonts/DMSans";
import { loadFont as loadCormorantGaramond } from "@remotion/google-fonts/CormorantGaramond";
import { loadFont as loadLora } from "@remotion/google-fonts/Lora";
import { loadFont as loadSpaceMono } from "@remotion/google-fonts/SpaceMono";
import { loadFont as loadTeko } from "@remotion/google-fonts/Teko";

const inter = loadInter();
const montserrat = loadMontserrat();
const poppins = loadPoppins();
const playfairDisplay = loadPlayfairDisplay();
const dmSerifDisplay = loadDMSerifDisplay();
const dmSans = loadDMSans();
const cormorantGaramond = loadCormorantGaramond();
const lora = loadLora();
const spaceMono = loadSpaceMono();
const teko = loadTeko();

// MULTILINGUAL A2.1 — deliberate script-aware fallback. Chromium (Remotion's
// headless renderer) resolves font-family PER GLYPH via fontconfig against the
// system Noto fonts installed in A1: the Latin caption font renders Latin, and
// each Noto-for-script fills every non-Latin glyph — no tofu — deliberately,
// rather than leaving the choice to fontconfig's default. Noto Color Emoji closes
// the UGC-emoji case. Appending (not replacing) keeps every existing Latin render
// byte-identical: the primary font still wins for every glyph it has.
export const NOTO_FALLBACK = [
  "'Noto Sans'",
  "'Noto Sans Devanagari'", "'Noto Sans Arabic'", "'Noto Sans Hebrew'",
  "'Noto Sans Thai'", "'Noto Sans Bengali'", "'Noto Sans Tamil'",
  "'Noto Sans Telugu'", "'Noto Sans Kannada'", "'Noto Sans Malayalam'",
  "'Noto Sans Gurmukhi'", "'Noto Sans Gujarati'", "'Noto Sans Sinhala'",
  "'Noto Sans CJK SC'", "'Noto Sans CJK JP'", "'Noto Sans CJK KR'",
  "'Noto Color Emoji'",
  "sans-serif",
].join(", ");

const withNoto = (family: string): string => `${family}, ${NOTO_FALLBACK}`;

export const CAPTION_FONTS = {
  inter: withNoto(inter.fontFamily),
  montserrat: withNoto(montserrat.fontFamily),
  poppins: withNoto(poppins.fontFamily),
  playfairDisplay: withNoto(playfairDisplay.fontFamily),
  dmSerifDisplay: withNoto(dmSerifDisplay.fontFamily),
  dmSans: withNoto(dmSans.fontFamily),
  cormorantGaramond: withNoto(cormorantGaramond.fontFamily),
  lora: withNoto(lora.fontFamily),
  spaceMono: withNoto(spaceMono.fontFamily),
  teko: withNoto(teko.fontFamily),
} as const;
