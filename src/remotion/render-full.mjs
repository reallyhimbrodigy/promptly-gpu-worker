#!/usr/bin/env node
/**
 * Production render — single renderMedia call producing a silent mp4.
 *
 * Args:
 *   --input <path>      Path to PromptlyRenderInput JSON
 *   --output <path>     Absolute path to the output mp4 file
 *   --public-dir <path> REQUIRED. Directory Remotion serves local assets from.
 *                       All `src`/`sourceUrl` values in the input JSON are
 *                       BASENAMES resolved against this directory by
 *                       Remotion's bundle server. Usually the job's work_dir.
 *   --concurrency <N>   Optional. Default = half of CPU threads.
 *   --gl <mode>         Optional Chromium GL backend (angle-egl | swiftshader).
 *
 * The audio track is intentionally disabled (muted: true). Python builds the
 * full audio pipeline (speed-warped source, SFX mix, ducking, EQ, compressor)
 * in parallel and mux-concats it onto this silent mp4 in a final ffmpeg pass
 * that stream-copies the video.
 */

import { bundle } from "@remotion/bundler";
import {
  renderMedia,
  selectComposition,
  openBrowser,
  ensureBrowser,
} from "@remotion/renderer";
import { existsSync, readFileSync, mkdirSync, statSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import os from "os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PREBUNDLE_DIR = "/remotion/bundle";

// ── CLI ────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
let inputPath = null;
let outputPath = null;
let publicDir = null;
let concurrency = null;
let glMode = "angle-egl";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--output" && args[i + 1]) outputPath = args[++i];
  else if (args[i] === "--public-dir" && args[i + 1]) publicDir = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
  else if (args[i] === "--gl" && args[i + 1]) glMode = args[++i];
}

if (!inputPath || !outputPath || !publicDir) {
  console.error("Usage: node render-full.mjs --input <json> --output <mp4> --public-dir <dir> [--concurrency N] [--gl mode]");
  process.exit(1);
}

if (!existsSync(inputPath)) {
  console.error(`[render-full] Input JSON not found: ${inputPath}`);
  process.exit(1);
}

if (!existsSync(publicDir)) {
  console.error(`[render-full] --public-dir does not exist: ${publicDir}`);
  process.exit(1);
}

mkdirSync(dirname(outputPath), { recursive: true });

const inputJson = JSON.parse(readFileSync(inputPath, "utf-8"));
const inputProps = { input: inputJson };

const cpuCount = os.cpus().length;
const resolvedConcurrency = concurrency && concurrency > 0 ? concurrency : Math.max(1, Math.floor(cpuCount / 2));

console.log(
  `[render-full] ${inputJson.clips?.length ?? 0} clips, ${inputJson.transitions?.length ?? 0} transitions, ` +
  `${inputJson.broll?.length ?? 0} broll, ${inputJson.motionGraphics?.length ?? 0} MG, ` +
  `${inputJson.totalDurationInFrames} frames, concurrency=${resolvedConcurrency}`,
);

// ── Bundle (use prebundle if present) ──────────────────────────────────────
let bundleLocation;
if (existsSync(resolve(PREBUNDLE_DIR, "index.html"))) {
  bundleLocation = PREBUNDLE_DIR;
  console.log(`[render-full] Using prebundle at ${bundleLocation}`);
} else {
  console.log("[render-full] No prebundle found — bundling at runtime");
  const t0 = Date.now();
  bundleLocation = await bundle({
    entryPoint: resolve(__dirname, "src/index.ts"),
    webpackOverride: (config) => config,
  });
  console.log(`[render-full] Bundled in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}

// ── Browser ────────────────────────────────────────────────────────────────
const chromePath = existsSync("/usr/local/bin/chrome-headless-shell")
  ? "/usr/local/bin/chrome-headless-shell"
  : undefined;

await ensureBrowser({
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    gl: glMode,
    enableMultiProcessOnLinux: true,
    disableWebSecurity: true,
  },
});

const tBrowser = Date.now();
const browser = await openBrowser("chrome-headless-shell", {
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    gl: glMode,
    enableMultiProcessOnLinux: true,
    disableWebSecurity: true,
  },
});
console.log(`[render-full] Browser opened in ${((Date.now() - tBrowser) / 1000).toFixed(2)}s`);

// ── Composition ────────────────────────────────────────────────────────────
const tComp = Date.now();
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "PromptlyRender",
  inputProps,
  puppeteerInstance: browser,
  publicDir,
});
console.log(`[render-full] selectComposition: ${((Date.now() - tComp) / 1000).toFixed(2)}s (publicDir=${publicDir})`);

// ── Render ─────────────────────────────────────────────────────────────────
const tRender = Date.now();
let lastPctLogged = -10;

await renderMedia({
  serveUrl: bundleLocation,
  composition,
  codec: "h264",
  outputLocation: outputPath,
  inputProps,
  concurrency: resolvedConcurrency,
  muted: true,
  x264Preset: "ultrafast",
  crf: 18,
  pixelFormat: "yuv420p",
  enforceAudioTrack: false,
  overwrite: true,
  puppeteerInstance: browser,
  publicDir,
  chromiumOptions: {
    ...(chromePath ? { executablePath: chromePath } : {}),
    gl: glMode,
    enableMultiProcessOnLinux: true,
    disableWebSecurity: true,
  },
  // Give the offthread cache generous headroom — we have 128 GB RAM.
  // The cache stores decoded source frames so repeated seeks across
  // transitions + captions don't re-decode from disk each time.
  offthreadVideoCacheSizeInBytes: 16 * 1024 * 1024 * 1024, // 16 GB
  logLevel: "info",
  onProgress: ({ progress }) => {
    const pct = Math.round(progress * 100);
    if (pct >= lastPctLogged + 10) {
      console.log(`[render-full] progress ${pct}%`);
      lastPctLogged = pct;
    }
  },
});

const renderElapsed = (Date.now() - tRender) / 1000;
try {
  const size = statSync(outputPath).size;
  console.log(
    `[render-full] DONE in ${renderElapsed.toFixed(1)}s → ${outputPath} (${(size / 1024 / 1024).toFixed(1)}MB)`,
  );
} catch {
  console.log(`[render-full] DONE in ${renderElapsed.toFixed(1)}s → ${outputPath}`);
}

await browser.close();
