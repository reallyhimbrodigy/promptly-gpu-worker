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
// Default to the Modal-image path used at production build time. Overridable
// via env var so local smoke tests can prebundle into a project-local cache
// without colliding with /remotion/bundle (which doesn't exist on dev
// machines anyway).
const BUNDLE_DIR = process.env.PROMPTLY_BUNDLE_DIR || "/remotion/bundle";

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
// Redirect `@remotion/media` to a local shim that re-exports `OffthreadVideo`
// as `Video`. The five ABE.zip zoom components import `Video` from
// `@remotion/media`; on short pre-extracted zoom clips that WebCodecs path
// times out at frame 1-3 with "Timeout while extracting frame at time Nsec".
// OffthreadVideo uses Chromium's standard HTMLVideoElement + frame capture,
// which decodes every frame the components ask for. The component files
// remain byte-identical to ABE.zip — only the package resolution is
// redirected at build time.
const REMOTION_MEDIA_ALIAS = {
  "@remotion/media": resolve(__dirname, "src/shims/remotion-media.ts"),
};

console.log(`[prebundle] Aliasing ${Object.keys(GOOGLE_FONT_ALIASES).length} @remotion/google-fonts imports to local shims (no network fetches at render time).`);
console.log(`[prebundle] Aliasing @remotion/media → src/shims/remotion-media.ts (Video → OffthreadVideo, avoids WebCodecs frame-extract timeouts on short clips).`);
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
        ...REMOTION_MEDIA_ALIAS,
      },
    },
  }),
  outDir: BUNDLE_DIR,
});

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`[prebundle] Done in ${elapsed}s → ${bundleLocation}`);
