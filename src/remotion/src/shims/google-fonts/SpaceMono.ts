// Shim for @remotion/google-fonts/SpaceMono. See _shared.ts.
import { makeShim } from "./_shared";
const shim = makeShim("Space Mono");
export const loadFont = shim.loadFont;
export const fontFamily = shim.fontFamily;
