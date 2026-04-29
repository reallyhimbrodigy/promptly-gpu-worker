#!/usr/bin/env node
/**
 * Production render — single renderMedia call producing a silent video file.
 *
 * Args:
 *   --input <path>       Path to input JSON (PromptlyRenderInput for overlay,
 *                        PromptlyMicroSegmentsInput for micro-segments).
 *   --output <path>      Absolute path to the output video file.
 *   --public-dir <path>  REQUIRED. Directory Remotion serves local assets from.
 *                        All `src`/`sourceUrl` values in the input JSON are
 *                        BASENAMES resolved against this directory by
 *                        Remotion's bundle server.
 *   --composition <id>   "PromptlyOverlay"      → ProRes 4444 alpha (overlay).
 *                        "PromptlyMicroSegments" → h264 (transitions + complex
 *                                                  zoom clips, no alpha).
 *   --concurrency <N>    Optional. Default = half of CPU threads.
 *   --gl <mode>          Optional Chromium GL backend. Default: vulkan.
 *
 * The audio track is intentionally disabled (muted: true). Python builds the
 * full audio pipeline (speed-warped source, SFX mix, ducking, EQ, compressor)
 * in parallel and mux-concats it onto the final video in the composite pass
 * that runs after this render exits.
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

const VALID_COMPOSITIONS = new Set([
  "PromptlyOverlay",
  "PromptlyMicroSegments",
  "PromptlyBlendRender",
]);

// ── CLI ────────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
let inputPath = null;
let outputPath = null;
let publicDir = null;
let concurrency = null;
// Vulkan is the only renderer mode in @remotion/renderer 4.0.450 that
// passes `--enable-gpu` and `--ignore-gpu-blocklist` (see
// node_modules/@remotion/renderer/dist/open-browser.js getOpenGlRenderer()).
// Other modes (angle-egl, swiftshader, etc.) just set the GL backend
// without explicitly enabling the GPU, so headless Chromium silently
// falls through to SwiftShader. NVIDIA H100 has first-class Vulkan via
// the NVIDIA driver; this is the most reliable hardware path on Modal.
let glMode = "vulkan";
let compositionId = "PromptlyOverlay";
// Chunked rendering: split a composition timeline into N frame ranges
// rendered by independent processes. Required to break past Remotion's
// documented single-instance ~16-22 fps ceiling (issue #4664). Each chunk
// renders frames [start, end] inclusive; compositionStart tells Remotion
// the global frame offset so animations using useCurrentFrame() return
// correct numbers across chunk boundaries.
let frameRangeStart = null;
let frameRangeEnd = null;
let compositionStart = 0;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" && args[i + 1]) inputPath = args[++i];
  else if (args[i] === "--output" && args[i + 1]) outputPath = args[++i];
  else if (args[i] === "--public-dir" && args[i + 1]) publicDir = args[++i];
  else if (args[i] === "--concurrency" && args[i + 1]) concurrency = parseInt(args[++i], 10);
  else if (args[i] === "--gl" && args[i + 1]) glMode = args[++i];
  else if (args[i] === "--composition" && args[i + 1]) compositionId = args[++i];
  else if (args[i] === "--frame-range" && args[i + 1]) {
    const parts = args[++i].split(",").map((s) => parseInt(s.trim(), 10));
    if (parts.length !== 2 || parts.some((n) => Number.isNaN(n))) {
      console.error(`[render-full] --frame-range must be "start,end" with two integers`);
      process.exit(1);
    }
    frameRangeStart = parts[0];
    frameRangeEnd = parts[1];
  }
  else if (args[i] === "--composition-start" && args[i + 1]) {
    compositionStart = parseInt(args[++i], 10);
    if (Number.isNaN(compositionStart)) {
      console.error(`[render-full] --composition-start must be an integer`);
      process.exit(1);
    }
  }
}

if (!inputPath || !outputPath || !publicDir) {
  console.error(
    "Usage: node render-full.mjs --input <json> --output <file> --public-dir <dir> " +
    "[--composition PromptlyOverlay|PromptlyMicroSegments|PromptlyBlendRender] " +
    "[--concurrency N] [--gl mode] [--frame-range start,end --composition-start N]",
  );
  process.exit(1);
}

if (!VALID_COMPOSITIONS.has(compositionId)) {
  console.error(
    `[render-full] --composition must be one of ${[...VALID_COMPOSITIONS].join(" | ")}, got "${compositionId}"`,
  );
  process.exit(1);
}

const isOverlay = compositionId === "PromptlyOverlay";
// PromptlyBlendRender renders the full final video (clips + transitions +
// zoom + B-roll + captions w/ blend modes + MG + text overlays + outro)
// in one Remotion pass. Used only when caption_style is one of the blend-
// mode styles (GlitchHighlight, NegativeFlash, Prism). Codec/cache settings
// match PromptlyMicroSegments (h264, large OffthreadVideo cache because the
// source video is read heavily).
const isBlend = compositionId === "PromptlyBlendRender";

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

const isChunked = frameRangeStart !== null && frameRangeEnd !== null;
const frameRangeLabel = isChunked
  ? `chunk frames ${frameRangeStart}-${frameRangeEnd} (compositionStart=${compositionStart})`
  : `frames 0-${inputJson.totalDurationInFrames - 1}`;
const _summary = isOverlay || isBlend
  ? `${inputJson.caption?.pages?.length ?? 0} caption pages, ${inputJson.motionGraphics?.length ?? 0} MG, ${inputJson.textOverlays?.length ?? 0} text overlays` +
    (isBlend ? `, ${inputJson.clips?.length ?? 0} clips, ${inputJson.broll?.length ?? 0} broll` : "")
  : `${inputJson.segments?.length ?? 0} segments`;
console.log(
  `[render-full] composition=${compositionId} (${isOverlay ? "ProRes 4444 alpha" : "h264"}) ` +
  `${frameRangeLabel}, ${_summary}, concurrency=${resolvedConcurrency}`,
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

// ensureBrowser() unconditionally downloads Chromium to Remotion's managed
// location (~/.cache or node_modules/.remotion) — even when we have a
// build-time-baked binary. Skip it entirely if our symlink exists.
//
// CRITICAL: in @remotion/renderer 4.0.450, `executablePath` does NOT exist
// on `chromiumOptions`. The correct field is the TOP-LEVEL `browserExecutable`
// option on openBrowser/renderMedia. Passing executablePath inside
// chromiumOptions silently no-ops, leaving browserExecutable=null, which
// causes openBrowser → internalEnsureBrowser to download Chromium on every
// render (~86 MB).
if (!chromePath) {
  console.log("[render-full] No /usr/local/bin/chrome-headless-shell — calling ensureBrowser to download");
  await ensureBrowser({
    chromiumOptions: {
      gl: glMode,
      enableMultiProcessOnLinux: true,
      disableWebSecurity: true,
    },
  });
} else {
  console.log(`[render-full] Using build-time Chromium at ${chromePath} — skipping ensureBrowser`);
}

const tBrowser = Date.now();
const browser = await openBrowser("chrome", {
  ...(chromePath ? { browserExecutable: chromePath } : {}),
  chromiumOptions: {
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
  id: compositionId,
  inputProps,
  puppeteerInstance: browser,
  publicDir,
});
console.log(`[render-full] selectComposition: ${((Date.now() - tComp) / 1000).toFixed(2)}s (publicDir=${publicDir})`);

// ── Render ─────────────────────────────────────────────────────────────────
const tRender = Date.now();
let lastPctLogged = -10;

let _lastProgressTime = Date.now();
let _lastRenderedFrames = 0;
let _lastEncodedFrames = 0;
const _intervalSamples = [];

await renderMedia({
  serveUrl: bundleLocation,
  composition,
  // Codec selection by composition:
  //   PromptlyOverlay       → ProRes 4444 yuva444p10le (alpha required for
  //                           the alpha-composite step). PNG intermediates
  //                           are required by Remotion for any yuva pixel
  //                           format (JPEG can't carry alpha).
  //   PromptlyMicroSegments → h264 yuv420p (no alpha, fast encode, decoded
  //                           by FFmpeg in the final composite pass).
  //   PromptlyBlendRender   → h264 yuv420p (final video — no alpha needed
  //                           because the composition includes source video
  //                           and B-roll baked in. Audio is muxed onto this
  //                           output as the only post-Remotion step.)
  codec: isOverlay ? "prores" : "h264",
  ...(isOverlay
    ? {
        proResProfile: "4444",
        pixelFormat: "yuva444p10le",
        imageFormat: "png",
      }
    : { x264Preset: "ultrafast", crf: 18, pixelFormat: "yuv420p" }),
  outputLocation: outputPath,
  inputProps,
  concurrency: resolvedConcurrency,
  muted: true,
  enforceAudioTrack: false,
  overwrite: true,
  puppeteerInstance: browser,
  publicDir,
  ...(chromePath ? { browserExecutable: chromePath } : {}),
  chromiumOptions: {
    gl: glMode,
    enableMultiProcessOnLinux: true,
    disableWebSecurity: true,
  },
  // Chunked rendering: limit work to a frame range, with compositionStart
  // telling Remotion the global frame offset so animations using
  // useCurrentFrame() return correct frame numbers across chunk boundaries.
  // Both fields are required together for distributed renders.
  ...(isChunked ? { frameRange: [frameRangeStart, frameRangeEnd] } : {}),
  compositionStart,
  // OffthreadVideo cache, sized per composition. Overlay is a transparent
  // canvas — no source video reads — so a small cache suffices. Micro
  // segments seek heavily into source video for transitions + complex-zoom
  // clips. PromptlyBlendRender reads source video for every clip (full
  // timeline) plus B-roll cutaways, so it needs the largest cache.
  offthreadVideoCacheSizeInBytes: isOverlay
    ? 256 * 1024 * 1024     // 256 MB (overlay never reads video)
    : 4 * 1024 * 1024 * 1024, // 4 GB (micro & blend read source heavily)
  logLevel: "info",
  onProgress: (info) => {
    const { progress, encodedFrames, renderedFrames } = info || {};
    const now = Date.now();
    const pct = Math.round((progress || 0) * 100);
    if (pct >= lastPctLogged + 10) {
      const elapsedSec = (now - _lastProgressTime) / 1000;
      const rendDelta = (renderedFrames || 0) - _lastRenderedFrames;
      const encDelta = (encodedFrames || 0) - _lastEncodedFrames;
      const renderFps = elapsedSec > 0 ? rendDelta / elapsedSec : 0;
      const encodeFps = elapsedSec > 0 ? encDelta / elapsedSec : 0;
      console.log(
        `[render-full] progress ${pct}% rendered=${renderedFrames || 0} encoded=${encodedFrames || 0} ` +
        `interval_render_fps=${renderFps.toFixed(1)} interval_encode_fps=${encodeFps.toFixed(1)}`,
      );
      _intervalSamples.push({ pct, renderFps, encodeFps });
      lastPctLogged = pct;
      _lastProgressTime = now;
      _lastRenderedFrames = renderedFrames || 0;
      _lastEncodedFrames = encodedFrames || 0;
    }
  },
});

const renderElapsed = (Date.now() - tRender) / 1000;
if (_intervalSamples.length) {
  const fpsList = _intervalSamples.map((s) => s.renderFps);
  const avg = fpsList.reduce((a, b) => a + b, 0) / fpsList.length;
  const min = Math.min(...fpsList);
  const max = Math.max(...fpsList);
  console.log(
    `[render-full] render-fps over time: avg=${avg.toFixed(1)} min=${min.toFixed(1)} max=${max.toFixed(1)} (${_intervalSamples.length} samples)`,
  );
}
try {
  const size = statSync(outputPath).size;
  console.log(
    `[render-full] DONE in ${renderElapsed.toFixed(1)}s → ${outputPath} (${(size / 1024 / 1024).toFixed(1)}MB)`,
  );
} catch {
  console.log(`[render-full] DONE in ${renderElapsed.toFixed(1)}s → ${outputPath}`);
}

// browser.close() in newer @remotion/renderer destructures `silent` from
// its options arg — calling without args throws TypeError. Pass `{}` (or
// {silent: false}) to satisfy the API. The render output is already written
// at this point, so we additionally swallow any cleanup error.
try {
  await browser.close({ silent: false });
} catch (e) {
  console.log(`[render-full] browser.close() warning (render output already written): ${e.message}`);
}
