#!/usr/bin/env node
/**
 * LUMEN REEL render (Wave-3, ephemeral — driven by lumen_reel_app.py only).
 * Renders the LumenReel composition (the REAL GeneratedSceneLayer at the
 * canonical 30fps, 1080x1920 vertical) straight to H.264. This is a demo
 * reel, not a pipeline intermediate, so the single lossy encode happens here.
 *
 * Usage: node lumen-reel-render.mjs <props.json> <output.mp4> <publicDir>
 */
import {
  renderMedia,
  selectComposition,
  openBrowser,
  ensureBrowser,
} from "@remotion/renderer";
import { existsSync, readFileSync } from "fs";
import os from "os";

const [propsPath, outputPath, publicDir] = process.argv.slice(2);
if (!propsPath || !outputPath || !publicDir) {
  console.error("Usage: node lumen-reel-render.mjs <props.json> <output.mp4> <publicDir>");
  process.exit(1);
}
const PREBUNDLE_DIR = process.env.PROMPTLY_BUNDLE_DIR || "/remotion/bundle";
const inputProps = JSON.parse(readFileSync(propsPath, "utf-8"));

const chromiumOptions = {
  gl: "swangle",
  enableMultiProcessOnLinux: true,
  disableWebSecurity: true,
};
const chromePath = existsSync("/usr/local/bin/chrome-headless-shell")
  ? "/usr/local/bin/chrome-headless-shell"
  : undefined;
if (!chromePath) {
  await ensureBrowser({ chromiumOptions });
}
const browser = await openBrowser("chrome", {
  ...(chromePath ? { browserExecutable: chromePath } : {}),
  chromiumOptions,
});

const composition = await selectComposition({
  serveUrl: PREBUNDLE_DIR,
  id: "LumenReel",
  inputProps,
  puppeteerInstance: browser,
  publicDir,
});
console.log(
  `[reel] composition ${composition.width}x${composition.height}@${composition.fps} ` +
  `${composition.durationInFrames}f — rendering`,
);

let lastPct = -10;
await renderMedia({
  serveUrl: PREBUNDLE_DIR,
  composition,
  codec: "h264",
  crf: 16,
  colorSpace: "bt709",
  outputLocation: outputPath,
  inputProps,
  muted: true,
  enforceAudioTrack: false,
  overwrite: true,
  puppeteerInstance: browser,
  publicDir,
  ...(chromePath ? { browserExecutable: chromePath } : {}),
  chromiumOptions,
  concurrency: Math.max(1, Math.floor(os.cpus().length / 2)),
  offthreadVideoCacheSizeInBytes: 1024 * 1024 * 1024,
  logLevel: "info",
  onProgress: ({ progress }) => {
    const pct = Math.round((progress || 0) * 100);
    if (pct >= lastPct + 10) {
      lastPct = pct;
      console.log(`[reel] ${pct}%`);
    }
  },
});
await browser.close({ silent: true });
console.log(`[reel] DONE ${outputPath}`);
process.exit(0);
