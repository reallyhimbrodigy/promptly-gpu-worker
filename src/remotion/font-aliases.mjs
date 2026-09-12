// THE FONT SHIM'S ALIAS MAP, IN ONE PLACE, BECAUSE TWO BUNDLERS NEED IT.
//
// THE DEFECT THIS CLOSES. prebundle.mjs wired these aliases through
// webpackOverride and its own header promises "zero network dependency";
// remotion_batch.mjs — the path that actually renders every job — called
// bundle() with NO webpackOverride, so the alias never applied and the REAL
// @remotion/google-fonts shipped. Measured inside the render loop on a zoom
// composition that draws no text at all:
//
//     Fetching Roboto font          n=96  total 253,971ms  max 3,460ms
//     Fetching Oswald font          n=96  total 252,243ms  max 3,458ms
//     Fetching JetBrains Mono font  n=48  total 144,816ms  max 3,489ms
//
// 240 network font fetches per render, while a file in the tree asserted
// there were none. A correct, documented fix, inert because the caller that
// mattered did not use it.
//
// Both bundlers import from here so the map cannot be right in one and absent
// in the other again.
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

const GOOGLE_FONT_ALIASES = {
  "@remotion/google-fonts/Anton":             resolve(__dirname, "src/shims/google-fonts/Anton.ts"),
  "@remotion/google-fonts/CaveatBrush":       resolve(__dirname, "src/shims/google-fonts/CaveatBrush.ts"),
  "@remotion/google-fonts/CormorantGaramond": resolve(__dirname, "src/shims/google-fonts/CormorantGaramond.ts"),
  "@remotion/google-fonts/DMSans":            resolve(__dirname, "src/shims/google-fonts/DMSans.ts"),
  "@remotion/google-fonts/DMSerifDisplay":    resolve(__dirname, "src/shims/google-fonts/DMSerifDisplay.ts"),
  "@remotion/google-fonts/Inter":             resolve(__dirname, "src/shims/google-fonts/Inter.ts"),
  "@remotion/google-fonts/JetBrainsMono":     resolve(__dirname, "src/shims/google-fonts/JetBrainsMono.ts"),
  "@remotion/google-fonts/Lora":              resolve(__dirname, "src/shims/google-fonts/Lora.ts"),
  "@remotion/google-fonts/Montserrat":        resolve(__dirname, "src/shims/google-fonts/Montserrat.ts"),
  "@remotion/google-fonts/Oswald":            resolve(__dirname, "src/shims/google-fonts/Oswald.ts"),
  "@remotion/google-fonts/PlayfairDisplay":   resolve(__dirname, "src/shims/google-fonts/PlayfairDisplay.ts"),
  "@remotion/google-fonts/Poppins":           resolve(__dirname, "src/shims/google-fonts/Poppins.ts"),
  "@remotion/google-fonts/Roboto":            resolve(__dirname, "src/shims/google-fonts/Roboto.ts"),
  "@remotion/google-fonts/SpaceMono":         resolve(__dirname, "src/shims/google-fonts/SpaceMono.ts"),
  "@remotion/google-fonts/Teko":              resolve(__dirname, "src/shims/google-fonts/Teko.ts"),
};

const REMOTION_MEDIA_ALIAS = {
  "@remotion/media": resolve(__dirname, "src/shims/remotion-media.ts"),
};
export { GOOGLE_FONT_ALIASES, REMOTION_MEDIA_ALIAS };
