// Shim for @remotion/google-fonts/CormorantGaramond. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Cormorant Garamond");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
