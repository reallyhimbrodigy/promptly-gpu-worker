// Shim for @remotion/google-fonts/Oswald. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Oswald");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
