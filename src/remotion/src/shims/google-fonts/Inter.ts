// Shim for @remotion/google-fonts/Inter. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Inter");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
