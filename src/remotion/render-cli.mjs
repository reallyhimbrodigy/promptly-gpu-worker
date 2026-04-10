#!/usr/bin/env node
/**
 * Remotion Video Overlay Render CLI
 *
 * Renders captions + visual effects as a PNG sequence with alpha transparency.
 * PNG output eliminates VP8 encoding entirely — Chrome screenshots are the only work.
 *
 * Usage: node render-cli.mjs --input <json_path> --output <png_dir>
 *        [--concurrency N] [--gl mode]
 *
 * Input JSON: OverlayInput (see types.ts)
 * Output: directory of element-NNNNNN.png files with RGBA transparency
 */

import { bundle } from "@remotion/bundler";
import { renderFrames, selectComposition } from "@remotion/renderer";
import { readFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PREBUNDLE_DIR = "/remotion/bundle";

// Parse CLI args
const args = process.argv.slice(2);
let inputPath = null;
let outputPath = null;
let concurrency = 24;
let glMode = "angle-egl"; // GPU-accelerated; falls back to swiftshader
let frameRangeArg = null; // "start-end" for per-segment rendering

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--output" && args[i + 1]) outputPath = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
  else if (args[i] === "--gl" && args[i + 1]) glMode = args[++i];
  else if (args[i] === "--frame-range" && args[i + 1]) frameRangeArg = args[++i];
}

// Parse frame range if provided (format: "start-end")
let frameRange = null;
if (frameRangeArg) {
  const parts = frameRangeArg.split("-").map(Number);
  if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
    frameRange = [parts[0], parts[1]];
  }
}

if (!inputPath || !outputPath) {
  console.error("Usage: node render-cli.mjs --input <json> --output <png_dir> [--concurrency N]");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(inputPath, "utf-8"));

// Normalize input — support both old CaptionInput and new OverlayInput formats
const input = {
  words: raw.words || [],
  captionStyle: raw.captionStyle || raw.style || "volt",
  keywords: raw.keywords || [],
  effects: raw.effects || [],
  cuts: raw.cuts || [],
  emphasisMoments: raw.emphasisMoments || raw.emphasis_moments || [],
  textOverlays: raw.textOverlays || [],
  width: raw.width || 1080,
  height: raw.height || 1920,
  fps: raw.fps || 30,
  duration: raw.duration || 30,
  durationInFrames: 0, // computed below
  fontDir: raw.fontDir || "/assets/fonts",
  vibe: raw.vibe || "",
};
input.durationInFrames = Math.max(1, Math.round(input.duration * input.fps));

console.log(
  `[remotion] Rendering: ${input.captionStyle} captions (${input.words.length} words), ` +
  `${input.cuts.length} cuts, ${input.emphasisMoments.length} emphasis moments, vibe="${input.vibe}", ` +
  `${input.durationInFrames} frames (${input.duration.toFixed(1)}s @ ${input.fps}fps)`
);

const t0 = Date.now();

// Use pre-built bundle if available
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

const inputProps = { input };

// Detect pre-installed Chrome Headless Shell to avoid runtime download
const chromePath = existsSync("/usr/local/bin/chrome-headless-shell")
  ? "/usr/local/bin/chrome-headless-shell"
  : undefined;
if (chromePath) console.log("[remotion] Using pre-installed Chrome:", chromePath);

// Select the VideoOverlay composition (resolves React component + props)
const tComp = Date.now();
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "VideoOverlay",
  inputProps,
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    disableWebSecurity: true,
  },
});
console.log(`[remotion] selectComposition: ${((Date.now() - tComp) / 1000).toFixed(2)}s`);

composition.durationInFrames = input.durationInFrames;
composition.width = input.width;
composition.height = input.height;
composition.fps = input.fps;

// Create output directory for PNG frames
mkdirSync(outputPath, { recursive: true });

// Render to PNG sequence — no video encoding, just Chrome screenshots.
// Each PNG has full RGBA transparency. This eliminates the VP8 stitching
// bottleneck entirely (was 219s for 106 frames with VP8, now 0s).
const actualFrameCount = frameRange
  ? (frameRange[1] - frameRange[0] + 1)
  : composition.durationInFrames;

let lastPct = -1;
const tRender = Date.now();
await renderFrames({
  serveUrl: bundleLocation,
  composition,
  inputProps,
  outputDir: outputPath,
  imageFormat: "png",
  concurrency,
  ...(frameRange ? { frameRange } : {}),
  logLevel: "verbose",
  chromiumOptions: {
    gl: glMode,
    ...(chromePath ? { executablePath: chromePath } : {}),
    disableWebSecurity: true,
    enableMultiProcessOnLinux: true,
  },
  onStart: ({ frameCount }) => {
    console.log(`[remotion] Rendering ${frameCount} PNG frames (concurrency=${concurrency})${frameRange ? ` [frames ${frameRange[0]}-${frameRange[1]}]` : ""}`);
  },
  onFrameUpdate: (rendered) => {
    const pct = Math.round(rendered / actualFrameCount * 100);
    if (pct % 10 === 0 && pct !== lastPct) {
      lastPct = pct;
      process.stdout.write(`\r[remotion] ${pct}%`);
    }
  },
});
const renderElapsed = ((Date.now() - tRender) / 1000).toFixed(2);

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`\n[remotion] renderFrames: ${renderElapsed}s | total: ${elapsed}s (${input.durationInFrames} frames) → ${outputPath}`);
