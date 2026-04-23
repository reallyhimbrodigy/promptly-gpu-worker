// Shim for @remotion/google-fonts/DMSans. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("DM Sans");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
