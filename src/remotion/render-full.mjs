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
// Vulkan is the only renderer mode in @remotion/renderer 4.0.450 that
// passes `--enable-gpu` and `--ignore-gpu-blocklist` (see
// node_modules/@remotion/renderer/dist/open-browser.js getOpenGlRenderer()).
// Other modes (angle-egl, swiftshader, etc.) just set the GL backend
// without explicitly enabling the GPU, so headless Chromium silently
// falls through to SwiftShader. NVIDIA H100 has first-class Vulkan via
// the NVIDIA driver; this is the most reliable hardware path on Modal.
let glMode = "vulkan";
// Two-renderer split: "PromptlyBase" (h264, video + transitions + zoom +
// broll) or "PromptlyOverlay" (ProRes 4444 with alpha — captions + MGs +
// text overlays on transparent canvas). handler.py launches one of each
// in parallel and FFmpeg composites the alpha overlay onto the base in
// the final mux step.
let compositionId = "PromptlyBase";
// Chunked rendering (Remotion's documented distributed-rendering pattern):
// each chunk worker renders a subrange of the timeline. frameRange = [start, end]
// inclusive bounds; compositionStart tells Remotion that frame 0 of THIS chunk
// is actually frame N of the overall composition, so animations using
// useCurrentFrame() return the correct global frame number. Without
// compositionStart, animations would restart per chunk → broken output.
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
      console.error(`[render-full] --frame-range must be "start,end" with two integers, got "${args[i]}"`);
      process.exit(1);
    }
    frameRangeStart = parts[0];
    frameRangeEnd = parts[1];
  }
  else if (args[i] === "--composition-start" && args[i + 1]) {
    compositionStart = parseInt(args[++i], 10);
    if (Number.isNaN(compositionStart)) {
      console.error(`[render-full] --composition-start must be an integer, got "${args[i]}"`);
      process.exit(1);
    }
  }
}

if (!inputPath || !outputPath || !publicDir) {
  console.error("Usage: node render-full.mjs --input <json> --output <mp4|mov> --public-dir <dir> [--concurrency N] [--gl mode] [--composition PromptlyBase|PromptlyOverlay] [--frame-range start,end] [--composition-start N]");
  process.exit(1);
}

if (compositionId !== "PromptlyBase" && compositionId !== "PromptlyOverlay") {
  console.error(`[render-full] --composition must be "PromptlyBase" or "PromptlyOverlay", got "${compositionId}"`);
  process.exit(1);
}

const isOverlay = compositionId === "PromptlyOverlay";

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
const frameRangeLabel = isChunked ? `frames ${frameRangeStart}..${frameRangeEnd}` : `frames 0..${inputJson.totalDurationInFrames - 1}`;

console.log(
  `[render-full] composition=${compositionId} (${isOverlay ? "ProRes 4444 alpha" : "h264"}) ` +
  `${frameRangeLabel}, compositionStart=${compositionStart}, ` +
  `${inputJson.clips?.length ?? 0} clips, ${inputJson.transitions?.length ?? 0} transitions, ` +
  `${inputJson.broll?.length ?? 0} broll, ${inputJson.motionGraphics?.length ?? 0} MG, ` +
  `${inputJson.totalDurationInFrames} frames total, concurrency=${resolvedConcurrency}`,
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
// render (~86 MB). This bug was masking the build-time-baked binary
// completely. Fixed below by lifting it to the right place.
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

// ── DIAGNOSTIC: Probe Chromium's actual WebGL renderer ─────────────────────
// We need to know whether Chromium is hardware-accelerated (NVIDIA H100) or
// software-rendering (SwiftShader). 32 parallel software-rendered tabs at
// 1080×1920 with SVG filter chains is the most likely cause of the 152s
// render — software renderer's pixel throughput on this composition is
// roughly 9 fps × 32 tabs = ~288 fps total, exactly what we'd see.
try {
  // @remotion/renderer 4.0.450 internal browser.newPage() destructures a
  // mandatory options object — calling without args throws
  // "Cannot destructure property 'context' of 'undefined'". Provide the
  // minimum stub fields so the diagnostic actually runs.
  const _gpuPage = await browser.newPage({
    context: () => null,
    logLevel: 'info',
    indent: false,
    pageIndex: 0,
    onBrowserLog: null,
    onLog: () => {},
  });
  // Remotion's internal Page class has no .setContent() — only .goto() and
  // .evaluate(). Navigate to a data: URL with the canvas inline, then run
  // the WebGL probe via evaluate.
  await _gpuPage.goto({
    url: 'data:text/html,<canvas id="c" width="100" height="100"></canvas>',
    timeout: 5000,
  });
  const _glInfo = await _gpuPage.evaluate(() => {
    const c = document.getElementById('c');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return { error: 'no WebGL context available' };
    const ext = gl.getExtension('WEBGL_debug_renderer_info');
    const renderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    const vendor   = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)   : gl.getParameter(gl.VENDOR);
    return {
      renderer: String(renderer),
      vendor: String(vendor),
      version: String(gl.getParameter(gl.VERSION)),
      shadingLanguage: String(gl.getParameter(gl.SHADING_LANGUAGE_VERSION)),
      maxTextureSize: gl.getParameter(gl.MAX_TEXTURE_SIZE),
    };
  });
  await _gpuPage.close();
  console.log(`[gpu-info] WebGL renderer: ${_glInfo.renderer || _glInfo.error}`);
  console.log(`[gpu-info] WebGL vendor:   ${_glInfo.vendor || ''}`);
  console.log(`[gpu-info] WebGL version:  ${_glInfo.version || ''}`);
  console.log(`[gpu-info] Max texture:    ${_glInfo.maxTextureSize || ''}`);
  // Heuristic flag — if the renderer string contains "SwiftShader", "llvmpipe",
  // or "Software", we're in software fallback regardless of what the
  // gl=angle-egl flag suggested.
  const _rs = (_glInfo.renderer || '').toLowerCase();
  const _isSoftware =
    _rs.includes('swiftshader') ||
    _rs.includes('llvmpipe') ||
    _rs.includes('software') ||
    _rs.includes('mesa');
  if (_isSoftware) {
    console.log(`[gpu-info] *** SOFTWARE RENDERER DETECTED *** — Chromium is NOT using the H100. This is almost certainly the bottleneck.`);
  } else if (_rs.includes('nvidia') || _rs.includes('h100') || _rs.includes('cuda')) {
    console.log(`[gpu-info] Hardware GPU rendering active.`);
  } else {
    console.log(`[gpu-info] Renderer not recognized as software or NVIDIA — inspect manually.`);
  }
} catch (e) {
  console.log(`[gpu-info] WebGL probe failed: ${e.message}`);
}

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

// DIAGNOSTIC: per-progress-update timing samples. Tells us if render speed
// degrades over time (memory pressure, cache eviction) or is uniformly slow
// (composition cost). Captures rendered/encoded split — if rendered is
// keeping up but encoded is lagging, encoder is the bottleneck; if rendered
// is slow, composition/decode is the bottleneck.
let _lastProgressTime = Date.now();
let _lastRenderedFrames = 0;
let _lastEncodedFrames = 0;
const _intervalSamples = [];

await renderMedia({
  serveUrl: bundleLocation,
  composition,
  // Two-renderer split codec selection:
  //   PromptlyBase     → h264 yuv420p (no alpha, fast encode, small file)
  //   PromptlyOverlay  → ProRes 4444 yuva444p10le (alpha, fast encode, larger
  //                      but acceptable since file is short-lived intermediate)
  // imageFormat="png" is REQUIRED for alpha output. Remotion validates that
  // alpha-bearing pixel formats (yuva*) only work with PNG intermediates
  // (JPEG can't carry alpha). Throws "Pixel format was set to 'yuva444p10le'
  // but the image format is not PNG" otherwise. PNG is slower per frame in
  // theory, but the overlay canvas is mostly transparent so PNG compression
  // is near-instant — net cost is negligible.
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
  // Chunked rendering: limit work to a frame range, with compositionStart
  // telling Remotion the global frame offset so animations using
  // useCurrentFrame() return the correct frame numbers across chunk
  // boundaries. Both fields are required together for distributed renders.
  ...(isChunked ? { frameRange: [frameRangeStart, frameRangeEnd] } : {}),
  compositionStart,
  ...(chromePath ? { browserExecutable: chromePath } : {}),
  chromiumOptions: {
    gl: glMode,
    enableMultiProcessOnLinux: true,
    disableWebSecurity: true,
  },
  // NOTE: hardwareAcceleration in Remotion controls the ENCODER (NVENC vs
  // libx264), NOT Chromium's GL backend. H100 has no NVENC ASIC (the
  // Modal startup log says so explicitly), so 'required' would always fail
  // on this hardware. The actual GPU paint path is fully controlled by
  // chromiumOptions.gl='vulkan', which adds --enable-gpu /
  // --ignore-gpu-blocklist / --use-angle=vulkan / --use-vulkan=native at
  // browser launch. That's what engages the H100 for the per-frame paint.
  // The encode stays on libx264 ultrafast — which is fine because in v51
  // we measured the encoder catching up at 65 fps; the bottleneck was
  // never the encode, it was Chromium painting in software.
  // OffthreadVideo cache. Sized for chunked workers (16 GB RAM each).
  // 1 GB is plenty per chunk: each chunk renders a subrange (~177 frames
  // per base chunk), seek footprint is bounded by the chunk's frame range,
  // and the overlay composition reads no video at all. A 16 GB cache here
  // would OOM the worker (16 GB tab cache + 8 Chromium tabs × 1 GB each
  // + Node + bundle ≈ 30 GB).
  offthreadVideoCacheSizeInBytes: 1 * 1024 * 1024 * 1024, // 1 GB
  // info-level logging: keeps the [render-full] interval-fps lines visible
  // without flooding stderr with thousands of per-frame compositor lines.
  logLevel: "info",
  onProgress: (info) => {
    const { progress, encodedFrames, renderedFrames } = info || {};
    const now = Date.now();
    const pct = Math.round((progress || 0) * 100);
    // Emit a sample roughly every 10% AND record rate-over-interval.
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
// DIAGNOSTIC: summarise interval samples — degrading vs uniform slowness.
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
// at this point, so we additionally swallow any cleanup error so a
// post-render browser-cleanup hiccup doesn't fail the whole render.
try {
  await browser.close({silent: false});
} catch (e) {
  console.log(`[render-full] browser.close() warning (render output already written): ${e.message}`);
}
