// Shim for @remotion/google-fonts/Lora. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Lora");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
