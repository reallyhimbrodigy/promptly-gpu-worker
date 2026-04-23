// Shim for @remotion/google-fonts/DMSerifDisplay. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("DM Serif Display");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
