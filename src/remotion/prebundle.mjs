#!/usr/bin/env node
/**
 * Pre-bundles the Remotion project at container build time.
 * This saves 5-10s per render by avoiding webpack bundling at runtime.
 */
import { bundle } from "@remotion/bundler";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { mkdirSync } from "fs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BUNDLE_DIR = "/remotion/bundle";

mkdirSync(BUNDLE_DIR, { recursive: true });

console.log("[prebundle] Bundling Remotion project...");
const t0 = Date.now();

const bundleLocation = await bundle({
  entryPoint: resolve(__dirname, "src/index.ts"),
  webpackOverride: (config) => config,
  outDir: BUNDLE_DIR,
});

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`[prebundle] Done in ${elapsed}s → ${bundleLocation}`);
