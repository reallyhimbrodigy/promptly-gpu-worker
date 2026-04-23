// Shim for @remotion/google-fonts/Poppins. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Poppins");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
