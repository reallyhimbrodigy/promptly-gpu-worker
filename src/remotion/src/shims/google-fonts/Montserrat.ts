// Shim for @remotion/google-fonts/Montserrat. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Montserrat");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
