// Shim for @remotion/google-fonts/JetBrainsMono. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("JetBrains Mono");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
