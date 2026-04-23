// Shim for @remotion/google-fonts/Anton. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Anton");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
