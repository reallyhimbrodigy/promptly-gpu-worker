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

export const CAPTION_FONTS = {
  inter: inter.fontFamily,
  montserrat: montserrat.fontFamily,
  poppins: poppins.fontFamily,
  playfairDisplay: playfairDisplay.fontFamily,
  dmSerifDisplay: dmSerifDisplay.fontFamily,
  dmSans: dmSans.fontFamily,
  cormorantGaramond: cormorantGaramond.fontFamily,
  lora: lora.fontFamily,
  spaceMono: spaceMono.fontFamily,
  teko: teko.fontFamily,
} as const;
