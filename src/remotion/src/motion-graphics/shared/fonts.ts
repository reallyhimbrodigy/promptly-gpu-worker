import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadAnton } from "@remotion/google-fonts/Anton";
import { loadFont as loadDMSerifDisplay } from "@remotion/google-fonts/DMSerifDisplay";
import { loadFont as loadPlayfairDisplay } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadCaveatBrush } from "@remotion/google-fonts/CaveatBrush";
import { loadFont as loadOswald } from "@remotion/google-fonts/Oswald";
import { loadFont as loadRoboto } from "@remotion/google-fonts/Roboto";
import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";

const inter = loadInter();
const anton = loadAnton();
const dmSerifDisplay = loadDMSerifDisplay();
const playfairDisplay = loadPlayfairDisplay();
const caveatBrush = loadCaveatBrush();
const oswald = loadOswald();
const roboto = loadRoboto();
const jetBrainsMono = loadJetBrainsMono();

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
