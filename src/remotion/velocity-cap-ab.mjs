// ZOOM VELOCITY CAP — local A/B, $0 Modal spend (this renders on the laptop).
//
// Three arms, because RULE 3 requires a pair PROVEN to differ AND a determinism
// floor to prove the difference is the change and not the encoder:
//   OFF   — today's cubic StagedPush
//   OFF2  — byte-identical repeat of OFF (the determinism baseline)
//   CAP   — smoothGraphics ON (the velocity cap)
//
// The source is a CONSTRUCTED DURABLE pattern (seeded, band-limited noise held
// STATIC), never user media — per the durable-sources law. Static is the point:
// every pixel change between consecutive frames is then caused by the zoom and
// nothing else, so per-frame MAD is a clean read on motion.
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
const SRC_NAME = "vcap_pattern.mp4";
const SRC = path.join(PUBLIC, SRC_NAME);

// ── 1. Build the durable source (seeded => reproducible byte-for-byte) ───────
if (!fs.existsSync(SRC)) {
  console.log("building constructed source…");
  const png = path.join(outDir, "_pattern.png");
  execFileSync("python3", ["-c", `
import numpy as np, struct, zlib
rng = np.random.default_rng(20260801)          # PINNED seed
h, w = 1920, 1080
n = rng.normal(0, 1, (h + 16, w + 16, 3))
# cheap separable box blur x3 ~= gaussian: gives natural 1/f-ish spectrum instead
# of white noise, so MAD tracks real-footage sensitivity rather than aliasing.
for _ in range(3):
    n = (n + np.roll(n, 1, 0) + np.roll(n, -1, 0)) / 3
    n = (n + np.roll(n, 1, 1) + np.roll(n, -1, 1)) / 3
n = n[8:8 + h, 8:8 + w]
n = (n - n.min()) / (n.max() - n.min())
img = (n * 255).astype(np.uint8)
raw = b"".join(b"\\x00" + img[y].tobytes() for y in range(h))
def chunk(t, d):
    c = struct.pack(">I", len(d)) + t + d
    return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
png = (b"\\x89PNG\\r\\n\\x1a\\n"
       + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
open(${JSON.stringify(png)}, "wb").write(png)
`]);
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-loop", "1", "-i", png,
    "-t", "4", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "12",
    "-pix_fmt", "yuv420p", "-x264-params", "threads=1", SRC]);
  fs.rmSync(png, { force: true });
}
console.log(`source: ${SRC}`);

// ── 2. Render the three arms ────────────────────────────────────────────────
const EVENTS = [{
  stages: [
    { atMs: 1000, scale: 1.08 },
    { atMs: 1800, scale: 1.16 },
    { atMs: 2600, scale: 1.24 },
  ],
  cutTerminated: false,
}];

const bundled = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts"), onProgress: () => {} });
const ARMS = [["OFF", false], ["OFF2", false], ["CAP", true]];
const files = {};
for (const [name, smooth] of ARMS) {
  const inputProps = { events: EVENTS, smoothGraphics: smooth, src: SRC_NAME };
  const out = path.join(outDir, `${name}.mp4`);
  const composition = await selectComposition({ serveUrl: bundled, id: "StagedPushProbe", inputProps });
  await renderMedia({
    composition, serveUrl: bundled, outputLocation: out, codec: "h264",
    inputProps, logLevel: "error", concurrency: 1,
  });
  files[name] = out;
  console.log(`rendered ${name}`);
}

// ── 3. Measure ──────────────────────────────────────────────────────────────
const psnr = (a, b) => {
  const o = execFileSync("ffmpeg", ["-i", files[a], "-i", files[b], "-lavfi", "psnr",
    "-f", "null", "-"], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  const m = /average:([0-9.]+|inf)/.exec(o);
  return m ? m[1] : "?";
};

const madSeries = (file) => {
  const dir = fs.mkdtempSync(path.join(outDir, "frames-"));
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-i", file,
    "-vf", "format=gray", path.join(dir, "f%04d.pgm")]);
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
  return {
    peak: Math.max(...s),
    p95: sorted[Math.floor(sorted.length * 0.95)],
    median: sorted[Math.floor(sorted.length * 0.5)],
    over: s.filter((v) => v > 3).length,
  };
};

console.log("\n=== RULE 3: do the arms differ? (PSNR, inf = identical) ===");
console.log(`  OFF vs OFF2 (determinism floor) : ${psnr("OFF", "OFF2")}`);
console.log(`  OFF vs CAP  (the change)        : ${psnr("OFF", "CAP")}`);

console.log("\n=== per-frame MAD (luma), static source => all motion is the zoom ===");
const rows = {};
for (const k of ["OFF", "CAP"]) {
  const s = madSeries(files[k]);
  rows[k] = s;
  const st = stat(s);
  console.log(`  ${k.padEnd(4)} peak=${st.peak.toFixed(2)}  p95=${st.p95.toFixed(2)}  ` +
    `median=${st.median.toFixed(2)}  frames>3=${st.over}/${s.length}`);
}
const top = (s) => [...s].sort((a, b) => b - a).slice(0, 8).map((v) => v.toFixed(1)).join(" ");
console.log(`\n  OFF top8 MAD: ${top(rows.OFF)}`);
console.log(`  CAP top8 MAD: ${top(rows.CAP)}`);
fs.writeFileSync(path.join(outDir, "mad.json"), JSON.stringify(rows, null, 1));
console.log(`\nwrote ${path.join(outDir, "mad.json")}`);
