// Shim for @remotion/google-fonts/PlayfairDisplay. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Playfair Display");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
