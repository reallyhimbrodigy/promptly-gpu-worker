#!/usr/bin/env node
/**
 * Pre-bundles the Remotion project at container build time. Saves 5-10s per
 * render by avoiding webpack bundling at runtime.
 *
 * Also rewires every `@remotion/google-fonts/*` import to a local shim at
 * build time. The real package injects `@font-face` rules that make
 * Chromium download .woff2 files from fonts.gstatic.com for every weight
 * and subset on every render. With 32 concurrent tabs × a dozen components
 * × dozens of variants per family, that cumulative fanout overwhelms
 * Chromium's 30s browser-setup timeout. The shim returns the same object
 * shape components expect (`.fontFamily`, `.waitUntilDone`) but performs
 * zero network I/O and injects no `@font-face` rules — Chromium resolves
 * every font-family against the system font catalog built by fc-cache at
 * image build time (/usr/share/fonts/truetype contains every .ttf the
 * pack references).
 */
import { bundle } from "@remotion/bundler";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { mkdirSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BUNDLE_DIR = "/remotion/bundle";

// Every @remotion/google-fonts/FONTNAME subpath the pack imports → local shim.
// Keep this list in lock-step with src/shims/google-fonts/. If a new component
// imports a font not listed here, the real Google Fonts module will load and
// re-introduce network fetches at render time.
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

mkdirSync(BUNDLE_DIR, { recursive: true });

console.log("[prebundle] Bundling Remotion project...");
console.log(`[prebundle] Aliasing ${Object.keys(GOOGLE_FONT_ALIASES).length} @remotion/google-fonts imports to local shims (no network fetches at render time).`);
const t0 = Date.now();

const bundleLocation = await bundle({
  entryPoint: resolve(__dirname, "src/index.ts"),
  webpackOverride: (config) => ({
    ...config,
    resolve: {
      ...config.resolve,
      alias: {
        ...(config.resolve?.alias ?? {}),
        ...GOOGLE_FONT_ALIASES,
      },
    },
  }),
  outDir: BUNDLE_DIR,
});

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`[prebundle] Done in ${elapsed}s → ${bundleLocation}`);
