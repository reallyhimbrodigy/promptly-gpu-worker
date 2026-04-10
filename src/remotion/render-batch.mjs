#!/usr/bin/env node
/**
 * Remotion Batch Render CLI — renders multiple frame ranges with ONE Chrome browser.
 *
 * Eliminates Chrome startup overhead (2-3s) per segment by reusing a single browser
 * instance across all renderFrames calls.
 *
 * Usage: node render-batch.mjs --input <json_path> --segments <segments_json>
 *        [--concurrency N] [--gl mode]
 *
 * segments_json format: [{"frameStart": 0, "frameEnd": 79, "outputDir": "/path/to/seg0"}, ...]
 */

import { bundle } from "@remotion/bundler";
import { renderFrames, selectComposition, openBrowser } from "@remotion/renderer";
import { readFileSync, existsSync, mkdirSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PREBUNDLE_DIR = "/remotion/bundle";

// Parse CLI args
const args = process.argv.slice(2);
let inputPath = null;
let segmentsPath = null;
let concurrency = 8;
let glMode = "angle-egl";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--segments" && args[i + 1]) segmentsPath = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
  else if (args[i] === "--gl" && args[i + 1]) glMode = args[++i];
}

if (!inputPath || !segmentsPath) {
  console.error("Usage: node render-batch.mjs --input <json> --segments <segments_json> [--concurrency N]");
  process.exit(1);
}

const raw = JSON.parse(readFileSync(inputPath, "utf-8"));
const segments = JSON.parse(readFileSync(segmentsPath, "utf-8"));

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
  durationInFrames: 0,
  fontDir: raw.fontDir || "/assets/fonts",
  vibe: raw.vibe || "",
};
input.durationInFrames = Math.max(1, Math.round(input.duration * input.fps));

console.log(
  `[remotion-batch] ${segments.length} segments, ${input.captionStyle} captions (${input.words.length} words), ` +
  `${input.durationInFrames} total frames`
);

const t0 = Date.now();

// Use pre-built bundle
let bundleLocation;
if (existsSync(resolve(PREBUNDLE_DIR, "index.html"))) {
  bundleLocation = PREBUNDLE_DIR;
} else {
  bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });
}

const inputProps = { input };

const chromePath = existsSync("/usr/local/bin/chrome-headless-shell")
  ? "/usr/local/bin/chrome-headless-shell"
  : undefined;

// Open ONE browser instance — reused across ALL segment renders
const tBrowser = Date.now();
const browser = await openBrowser("chrome-headless-shell", {
  gl: glMode,
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    disableWebSecurity: true,
    enableMultiProcessOnLinux: true,
  },
});
console.log(`[remotion-batch] Browser opened in ${((Date.now() - tBrowser) / 1000).toFixed(2)}s`);

// selectComposition ONCE (shared across all segments)
const tComp = Date.now();
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "VideoOverlay",
  inputProps,
  puppeteerInstance: browser,
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    disableWebSecurity: true,
  },
});
console.log(`[remotion-batch] selectComposition: ${((Date.now() - tComp) / 1000).toFixed(2)}s`);

composition.durationInFrames = input.durationInFrames;
composition.width = input.width;
composition.height = input.height;
composition.fps = input.fps;

// Render each segment's frame range, reusing the same browser
for (let si = 0; si < segments.length; si++) {
  const seg = segments[si];
  const frameRange = [seg.frameStart, seg.frameEnd];
  const outputDir = seg.outputDir;
  const nFrames = frameRange[1] - frameRange[0] + 1;

  mkdirSync(outputDir, { recursive: true });

  const tSeg = Date.now();
  await renderFrames({
    serveUrl: bundleLocation,
    composition,
    inputProps,
    outputDir,
    imageFormat: "png",
    concurrency,
    frameRange,
    logLevel: "error",
    puppeteerInstance: browser,
    chromiumOptions: {
      gl: glMode,
      ...(chromePath ? { executablePath: chromePath } : {}),
      disableWebSecurity: true,
      enableMultiProcessOnLinux: true,
    },
    onStart: () => {},
    onFrameUpdate: () => {},
  });
  const segElapsed = ((Date.now() - tSeg) / 1000).toFixed(2);
  console.log(`[remotion-batch] Segment ${si}: ${nFrames} frames [${frameRange[0]}-${frameRange[1]}] in ${segElapsed}s → ${outputDir}`);
}

// Close the shared browser
await browser.close();

const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`[remotion-batch] All ${segments.length} segments rendered in ${elapsed}s (1 browser instance)`);
