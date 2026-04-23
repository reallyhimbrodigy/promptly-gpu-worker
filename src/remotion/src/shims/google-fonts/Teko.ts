// Shim for @remotion/google-fonts/Teko. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Teko");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
