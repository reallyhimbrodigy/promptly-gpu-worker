#!/usr/bin/env node
/**
 * Remotion Caption Overlay Render CLI
 *
 * Usage: node render-cli.mjs --input <json_path> --output <mov_path>
 *
 * Input JSON format:
 * {
 *   "words": [...],          // ProjectedWord[] from project_words_to_output
 *   "style": "captions_dynamic",
 *   "width": 1080,
 *   "height": 1920,
 *   "fps": 30,
 *   "duration": 25.5,        // seconds
 *   "keywords": ["word1", "word2"],
 *   "fontDir": "/assets/fonts"
 * }
 *
 * Output: Transparent ProRes 4444 MOV file for FFmpeg overlay compositing.
 * Uses pre-built bundle from /remotion/bundle/ (created at container build time).
 */

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { readFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PREBUNDLE_DIR = "/remotion/bundle";

// Parse CLI args
const args = process.argv.slice(2);
let inputPath = null;
let outputPath = null;
let concurrency = 1;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--output" && args[i + 1]) outputPath = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
}

if (!inputPath || !outputPath) {
  console.error("Usage: node render-cli.mjs --input <json> --output <mov>");
  process.exit(1);
}

const input = JSON.parse(readFileSync(inputPath, "utf-8"));
const durationInFrames = Math.max(1, Math.round((input.duration || 30) * (input.fps || 30)));

console.log(
  `[remotion] Rendering ${input.style} captions: ${input.words?.length || 0} words, ` +
  `${durationInFrames} frames (${input.duration?.toFixed(1)}s @ ${input.fps}fps)`
);

const t0 = Date.now();

// Use pre-built bundle if available (saves 5-10s), otherwise bundle on-the-fly
let bundleLocation;
if (existsSync(resolve(PREBUNDLE_DIR, "index.html"))) {
  bundleLocation = PREBUNDLE_DIR;
  console.log("[remotion] Using pre-built bundle");
} else {
  console.log("[remotion] Pre-built bundle not found — bundling...");
  bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });
}

const inputProps = {
  input: {
    words: input.words || [],
    style: input.style || "captions_dynamic",
    width: input.width || 1080,
    height: input.height || 1920,
    fps: input.fps || 30,
    durationInFrames,
    keywords: input.keywords || [],
    fontDir: input.fontDir || "/assets/fonts",
  },
};

// Select composition with input props
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "CaptionOverlay",
  inputProps,
});

// Override duration/dimensions from input
composition.durationInFrames = durationInFrames;
composition.width = input.width || 1080;
composition.height = input.height || 1920;
composition.fps = input.fps || 30;

// Render to transparent MOV (ProRes 4444 with alpha)
await renderMedia({
  composition,
  serveUrl: bundleLocation,
  codec: "prores",
  proResProfile: "4444",
  pixelFormat: "yuva444p10le",
  outputLocation: outputPath,
  inputProps,
  concurrency: concurrency || 1,
  chromiumOptions: {
    gl: "angle",
  },
  onProgress: ({ progress }) => {
    const pct = Math.round(progress * 100);
    if (pct % 10 === 0) {
      process.stdout.write(`\r[remotion] ${pct}%`);
    }
  },
});

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\n[remotion] Done in ${elapsed}s → ${outputPath}`);
