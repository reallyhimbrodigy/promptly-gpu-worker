#!/usr/bin/env node
/**
 * Remotion Video Overlay Render CLI
 *
 * Renders captions + visual effects as a single transparent VP8 WebM.
 *
 * Usage: node render-cli.mjs --input <json_path> --output <webm_path>
 *        [--concurrency N] [--gl mode] [--frame-range start-end]
 *
 * Input JSON: OverlayInput (see types.ts)
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
let concurrency = 24;
let glMode = "angle-egl"; // GPU-accelerated; falls back to swiftshader
let frameRange = null; // [startFrame, endFrame] for chunk rendering

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--output" && args[i + 1]) outputPath = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
  else if (args[i] === "--gl" && args[i + 1]) glMode = args[++i];
  else if (args[i] === "--frame-range" && args[i + 1]) {
    const parts = args[++i].split("-").map(Number);
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      frameRange = parts;
    }
  }
}

if (!inputPath || !outputPath) {
  console.error("Usage: node render-cli.mjs --input <json> --output <webm> [--frame-range start-end]");
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
  width: raw.width || 1080,
  height: raw.height || 1920,
  fps: raw.fps || 30,
  duration: raw.duration || 30,
  durationInFrames: 0, // computed below
  fontDir: raw.fontDir || "/assets/fonts",
  vibe: raw.vibe || "",
};
input.durationInFrames = Math.max(1, Math.round(input.duration * input.fps));

const rangeStr = frameRange
  ? ` [chunk ${frameRange[0]}-${frameRange[1]} of ${input.durationInFrames}]`
  : "";

console.log(
  `[remotion] Rendering: ${input.captionStyle} captions (${input.words.length} words), ` +
  `${input.cuts.length} cuts, ${input.emphasisMoments.length} emphasis moments, vibe="${input.vibe}", ` +
  `${input.durationInFrames} frames (${input.duration.toFixed(1)}s @ ${input.fps}fps)${rangeStr}`
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

// Select the VideoOverlay composition (captions + effects)
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

// Render to transparent VP8 WebM — fast encode, alpha via libvpx
// CRF 16: this is an intermediate overlay composited into the final video.
// The final FFmpeg pass determines visible quality, not this encode.
// CRF 16 vs default 9 = ~2x faster encode, no perceptible difference after compositing.
const renderOptions = {
  composition,
  serveUrl: bundleLocation,
  codec: "vp8",
  crf: 16,
  pixelFormat: "yuva420p",
  imageFormat: "png",
  outputLocation: outputPath,
  inputProps,
  concurrency,
  logLevel: "verbose",
  chromiumOptions: {
    gl: glMode,
    ...(chromePath ? { executablePath: chromePath } : {}),
    disableWebSecurity: true,
    enableMultiProcessOnLinux: true,
  },
  // Speed up libvpx: deadline=realtime + cpu-used=8 = ~2-3x faster VP8 encode.
  // Safe because this is an intermediate overlay, not the final deliverable.
  ffmpegOverride: ({ type, args }) => {
    if (type === "stitcher") {
      return [...args, "-deadline", "realtime", "-cpu-used", "8"];
    }
    return args;
  },
  onProgress: ({ progress }) => {
    const pct = Math.round(progress * 100);
    if (pct % 10 === 0) {
      process.stdout.write(`\r[remotion] ${pct}%`);
    }
  },
};

// Add frame range for chunk rendering
if (frameRange) {
  renderOptions.frameRange = frameRange;
}

const tRender = Date.now();
await renderMedia(renderOptions);
const renderElapsed = ((Date.now() - tRender) / 1000).toFixed(2);

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
const framesRendered = frameRange
  ? frameRange[1] - frameRange[0] + 1
  : input.durationInFrames;
console.log(`\n[remotion] renderMedia: ${renderElapsed}s | total: ${elapsed}s (${framesRendered} frames) → ${outputPath}`);
