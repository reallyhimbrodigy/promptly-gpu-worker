// Shim for @remotion/google-fonts/CaveatBrush. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Caveat Brush");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
