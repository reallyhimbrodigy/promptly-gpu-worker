// ZOOM VELOCITY CAP — local A/B on REAL footage, $0 Modal spend (renders on the laptop).
//
// Zac's ruling 2026-08-01: run OFF / CAP / CAP+BLUR, on a REAL talking head, and
// produce consecutive-frame crops that read to his eye. SnapReframe (76.3 px/f)
// and StepZoom (244.8 px/f) are NOT capped — punch-lands-on-the-moment makes that
// velocity the point of them; they are blur candidates only.
//
// FOUR arms, because RULE 3 needs a determinism floor as well as a pair:
//   OFF   — today's cubic StagedPush
//   OFF2  — byte-identical repeat of OFF (the determinism floor)
//   CAP   — smoothGraphics ON (the velocity cap)
//   BLUR  — CAP + CameraMotionBlur on the residual (samples=3, shutter=180)
// CAP and BLUR differ by ONE flag, so the blur's contribution is isolated.
//
// SOURCE: a PINNED 6s window of a real 1080x1920/30fps vertical talking head —
// native resolution and native frame rate, so nothing is upscaled or resampled
// and the judder measured is the renderer's, not a format conversion's.
//
// MEASURED AT 30fps (StagedPushProbe30), the delivery format. The 60fps probe
// halves per-frame displacement and understates the whole defect by 2x.
//
// Usage: node velocity-cap-ab.mjs [outDir]
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(__dirname, "velocity-cap-out");
fs.mkdirSync(outDir, { recursive: true });

const PUBLIC = path.join(__dirname, "public");
const SRC_NAME = "vcap_head.mp4";
const SRC = path.join(PUBLIC, SRC_NAME);
// PINNED fixture + window. Both are part of the measurement: change either and
// the numbers below are not comparable.
const SRC_MASTER = "/Users/zaclibman/content-studio/reference-videos/snaptik_7611180844715101470_hd.mp4";
const SRC_START_S = 12;
const SRC_DUR_S = 6;   // >= the 5s composition, so the source NEVER runs out

const ff = (args) => execFileSync("ffmpeg", ["-y", "-loglevel", "error", ...args]);

if (!fs.existsSync(SRC)) {
  if (!fs.existsSync(SRC_MASTER)) {
    console.error(`missing pinned master: ${SRC_MASTER}`);
    process.exit(1);
  }
  console.log("cutting pinned 4s window from the real talking head…");
  ff(["-ss", String(SRC_START_S), "-i", SRC_MASTER, "-t", String(SRC_DUR_S),
    "-an", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "14",
    "-pix_fmt", "yuv420p", "-x264-params", "threads=1", SRC]);
}
console.log(`source: ${SRC}`);

const EVENTS = [{
  stages: [
    { atMs: 1000, scale: 1.08 },
    { atMs: 1800, scale: 1.16 },
    { atMs: 2600, scale: 1.24 },
  ],
  cutTerminated: false,
}];

const ARMS = [
  ["OFF", { smoothGraphics: false }],
  ["OFF2", { smoothGraphics: false }],
  ["CAP", { smoothGraphics: true }],
  ["BLUR", { smoothGraphics: true, motionBlur: true, motionBlurSamples: 3, motionBlurShutterAngle: 180 }],
];

const bundled = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts"), onProgress: () => {} });
const files = {};
const renderMs = {};
for (const [name, flags] of ARMS) {
  const inputProps = { events: EVENTS, src: SRC_NAME, ...flags };
  const out = path.join(outDir, `${name}.mp4`);
  const composition = await selectComposition({ serveUrl: bundled, id: "StagedPushProbe30", inputProps });
  const t0 = Date.now();
  await renderMedia({
    composition, serveUrl: bundled, outputLocation: out, codec: "h264",
    inputProps, logLevel: "error", concurrency: 1,
  });
  renderMs[name] = Date.now() - t0;
  files[name] = out;
  console.log(`rendered ${name}  (${(renderMs[name] / 1000).toFixed(1)}s)`);
}

// ── PSNR: prove the arms differ, against a determinism floor ────────────────
const psnr = (a, b) => {
  const r = execFileSync("ffmpeg", ["-i", files[a], "-i", files[b], "-lavfi", "psnr",
    "-f", "null", "-"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] })
    + execFileSync("/bin/sh", ["-c",
      `ffmpeg -i ${files[a]} -i ${files[b]} -lavfi psnr -f null - 2>&1 | tail -3`],
      { encoding: "utf8" });
  const m = /average:([0-9.]+|inf)/.exec(r);
  return m ? m[1] : "?";
};

// ── per-frame MAD (luma) ────────────────────────────────────────────────────
const madSeries = (file) => {
  const dir = fs.mkdtempSync(path.join(outDir, "frames-"));
  ff(["-i", file, "-vf", "format=gray", path.join(dir, "f%04d.pgm")]);
  const out = execFileSync("python3", ["-c", `
import sys, glob, numpy as np
def rd(p):
    with open(p,'rb') as f:
        assert f.readline().strip()==b'P5'
        l=f.readline()
        while l.startswith(b'#'): l=f.readline()
        w,h=map(int,l.split()); f.readline()
        return np.frombuffer(f.read(w*h),dtype=np.uint8).reshape(h,w).astype(np.int16)
fs_=sorted(glob.glob(sys.argv[1]+'/f*.pgm'))
prev=None; out=[]
for p in fs_:
    cur=rd(p)
    if prev is not None: out.append(float(np.abs(cur-prev).mean()))
    prev=cur
print(' '.join(f'{v:.3f}' for v in out))
`, dir], { encoding: "utf8" });
  fs.rmSync(dir, { recursive: true, force: true });
  return out.trim().split(/\s+/).map(Number);
};

const stat = (s) => {
  const sorted = [...s].sort((a, b) => a - b);
  return { peak: Math.max(...s), p95: sorted[Math.floor(sorted.length * 0.95)],
    median: sorted[Math.floor(sorted.length * 0.5)] };
};

console.log("\n=== RULE 3: do the arms differ? (PSNR dB, inf = identical) ===");
console.log(`  OFF  vs OFF2  determinism floor : ${psnr("OFF", "OFF2")}`);
console.log(`  OFF  vs CAP   the cap           : ${psnr("OFF", "CAP")}`);
console.log(`  CAP  vs BLUR  the blur alone    : ${psnr("CAP", "BLUR")}`);

console.log("\n=== per-frame MAD (luma) — REAL talking head, 1080x1920 @30fps ===");
const rows = {};
for (const k of ["OFF", "CAP", "BLUR"]) {
  const s = madSeries(files[k]);
  rows[k] = s;
  const st = stat(s);
  console.log(`  ${k.padEnd(5)} peak=${st.peak.toFixed(2)}  p95=${st.p95.toFixed(2)}  median=${st.median.toFixed(2)}`);
}
const top = (s) => [...s].sort((a, b) => b - a).slice(0, 8).map((v) => v.toFixed(1)).join(" ");
for (const k of ["OFF", "CAP", "BLUR"]) console.log(`  ${k.padEnd(5)} top8: ${top(rows[k])}`);

// ── consecutive-frame crops at the PEAK-MOTION frame ────────────────────────
// Cropped far from the transform origin, where displacement is largest (it scales
// with distance from the origin) and where the burned-in text gives hard edges:
// clean edges + a big jump = temporal sampling; smeared = blur/encode.
const peakFrame = rows.OFF.indexOf(Math.max(...rows.OFF)) + 1;
const CROPS = [
  { name: "topband", x: 300, y: 240, w: 480, h: 200 },  // hard-edged burned text
  { name: "face", x: 300, y: 800, w: 480, h: 300 },     // glasses / eye detail
];
const cropDir = path.join(outDir, "crops");
fs.mkdirSync(cropDir, { recursive: true });
for (const c of CROPS) {
  const tiles = [];
  for (const k of ["OFF", "CAP", "BLUR"]) {
    for (const off of [0, 1]) {
      const n = peakFrame + off;
      const t = path.join(cropDir, `_${k}_${c.name}_${off}.png`);
      ff(["-i", files[k], "-vf",
        `select=eq(n\\,${n}),crop=${c.w}:${c.h}:${c.x}:${c.y}`,
        "-frames:v", "1", t]);
      tiles.push(t);
    }
  }
  const sheet = path.join(cropDir, `${c.name}_f${peakFrame}-${peakFrame + 1}.png`);
  ff([...tiles.flatMap((t) => ["-i", t]),
    "-filter_complex",
    "[0:v][1:v]hstack[a];[2:v][3:v]hstack[b];[4:v][5:v]hstack[c];[a][b][c]vstack=inputs=3[o]",
    "-map", "[o]", sheet]);
  tiles.forEach((t) => fs.rmSync(t, { force: true }));
  console.log(`crop sheet -> ${sheet}`);
}
console.log(`\npeak-motion frame in OFF = ${peakFrame} (rows: OFF / CAP / BLUR, cols: frame n | n+1)`);
console.log("\n=== render cost (local, 150 frames @1080x1920/30) ===");
for (const [k] of ARMS) console.log(`  ${k.padEnd(5)} ${(renderMs[k] / 1000).toFixed(1)}s`);
fs.writeFileSync(path.join(outDir, "mad.json"), JSON.stringify(rows, null, 1));
