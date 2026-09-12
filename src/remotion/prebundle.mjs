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
import { createHash } from "crypto";
import { readFileSync, writeFileSync, readdirSync, statSync } from "fs";
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
// ONE MAP, TWO BUNDLERS. It lived only here while remotion_batch.mjs —
// the path that renders every job — bundled without it.
import { GOOGLE_FONT_ALIASES, REMOTION_MEDIA_ALIAS } from "./font-aliases.mjs";


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

// BUNDLE-FRESHNESS FINGERPRINT (Zac 2026-08-02): a TSX change ships INERT if a
// redeploy reuses a cached bundle without re-running this prebundle — SafeImg
// itself nearly shipped that way. Hash every .ts/.tsx/.mjs under src/ and stamp
// it into the built bundle; the worker asserts at startup that the DEPLOYED
// bundle carries the hash of the DEPLOYED source. Mismatch = stale bundle =
// loud failure, never a silent inert render.
function _srcFiles(dir) {
  let out = [];
  for (const e of readdirSync(dir)) {
    const p = resolve(dir, e);
    if (statSync(p).isDirectory()) { if (e !== "node_modules") out = out.concat(_srcFiles(p)); }
    else if (/\.(tsx?|mjs)$/.test(e)) out.push(p);
  }
  return out;
}
const _srcDir = resolve(__dirname, "src");
const _h = createHash("sha256");
for (const f of _srcFiles(_srcDir).sort()) { _h.update(f.slice(_srcDir.length)); _h.update(readFileSync(f)); }
const _hash = _h.digest("hex");
writeFileSync(resolve(BUNDLE_DIR, ".src_hash"), _hash);
console.log(`[prebundle] src fingerprint sha256:${_hash.slice(0, 16)}… → bundle/.src_hash`);
