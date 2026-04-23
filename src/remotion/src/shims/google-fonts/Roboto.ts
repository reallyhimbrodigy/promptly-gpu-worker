// Shim for @remotion/google-fonts/Roboto. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Roboto");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
