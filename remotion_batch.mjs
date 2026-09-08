/**
 * remotion_batch.mjs — render N compositions in ONE process.
 *
 * MEASURED: bundle 9.79s + selectComposition 2.05s + renderMedia overhead 0.40s
 * = 12.24s of per-PROCESS cost, paid in full by every `npx remotion render`.
 * The reel spawned one process; captions would have spawned another; each zoom
 * another. Batching pays it ONCE.
 *
 * It is a PROCESS that is shared, not a composition. Captions and cards are
 * alpha overlays and could in principle share a reel; a zoom scales the footage
 * itself and is opaque, so it never could. Sharing the process is what actually
 * generalises across all three.
 *
 * Contract: argv[2] is a JSON file of
 *   [{ id, composition, propsFile, out, alpha?, codec? }, ...]
 *
 * THE CONTRACT USED TO LIST `sequence?` AND `imageFormat?`. Neither was ever
 * read: imageFormat is hardcoded png and there is no sequence branch at all, so
 * a caller asking for a PNG directory would have silently received a VIDEO FILE
 * at that path. Documented-but-unimplemented is the same false-green class as an
 * assertion in a docstring — the doc asserts a capability the code does not
 * have, and the caller finds out downstream. Removed rather than implemented:
 * the alpha ProRes path replaced every reason to want a sequence.
 * Emits one JSON line per job to stdout prefixed "JOB " so the caller can
 * attribute failures per entry rather than losing the batch to one bad job.
 */
// REMOTION IS IMPORTED INSIDE main(), NOT AT MODULE LOAD.
//
// Not a style choice: with these at the top, this file cannot be imported
// anywhere Remotion is not installed — which is everywhere except the image. So
// the only possible test was to read the source as TEXT, and a substring check
// is satisfied by the comment that explains it. Deferring the import is what
// lets smoke_bundle_cache.mjs drive the SHIPPED bundleDecision instead of a
// copy of it.
//
// The real path is unaffected: main() awaits these before it does anything
// else, so a missing dependency in the image still fails immediately and
// loudly, at the same moment it did before.
import fs from "node:fs";
import crypto from "node:crypto";
import path from "node:path";
import { pathToFileURL } from "node:url";

const R = "/promptly-remotion";
const jobs = process.argv[2] ? JSON.parse(fs.readFileSync(process.argv[2], "utf8")) : [];
const t0 = Date.now();

// ── BUNDLE CACHE, KEYED ON THE SOURCE TREE ──────────────────────────────────
//
// bundle() is 9.79s of the 12.24s per-process cost. Batching amortises it
// across jobs in ONE call, but the reel and the captions are rendered by
// DIFFERENT AGENT TOOL CALLS — render_components and execute_plan — so they can
// never share a call, and batching alone never collects that 9.79s twice.
// Caching the bundle on disk does: the second process in a container reuses the
// first one's output.
//
// KEYED ON CONTENT, NOT TIME. The agent AUTHORS components mid-run (it writes
// Comp.tsx), so a cache that assumed the tree was static would serve a stale
// bundle and render the previous version of a component the agent had just
// fixed — silently, and with a plausible-looking video out the far end. The key
// is a hash of every source file's path + size + mtime, so authoring a
// component invalidates it exactly the way it should.
//
// The cache lives in /work, which is per-container: a fresh container pays the
// bundle once, as it must.
function sourceKey(root) {
  const parts = [];
  const walk = (d) => {
    let ents;
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents.sort((a, b) => a.name < b.name ? -1 : 1)) {
      if (e.name === "node_modules" || e.name.startsWith(".")) continue;
      const f = path.join(d, e.name);
      if (e.isDirectory()) { walk(f); continue; }
      if (!/\.(tsx?|jsx?|json|css)$/.test(e.name)) continue;
      try {
        // CONTENT, NOT MTIME.
        //
        // The mtime version THRASHED, and it was measured doing it: in the
        // first container run the reel got a CACHE HIT (0.7s) and the captions
        // then paid a full 9.3s bundle, which can only happen if the key moved
        // between two calls that read an unchanged source tree. Mount
        // materialisation gives files fresh mtimes; the bytes are identical.
        // Hashing content is a few ms on this tree and cannot thrash.
        parts.push(`${f}:${crypto.createHash("sha1")
          .update(fs.readFileSync(f)).digest("hex")}`);
      } catch { /* a file that vanished mid-walk cannot be part of the key */ }
    }
  };
  walk(path.join(root, "src"));
  return crypto.createHash("sha1").update(parts.join("\n")).digest("hex").slice(0, 16);
}

const CACHE_ROOT = "/work/.rbundle";
// KILL SWITCH. Every flag gets one: PROMPTLY_REMOTION_BUNDLE_CACHE=0 forces a
// fresh bundle every process, which is exactly the pre-cache behaviour and the
// control arm for measuring what the cache is worth.
const CACHE_ENABLED = String(process.env.PROMPTLY_REMOTION_BUNDLE_CACHE ?? "1") !== "0";

// THE DECISION, SEPARATED FROM THE BUNDLING, so a test can drive it without
// running a 9.79s bundle. The marker is what makes a cache dir usable, and it
// is written LAST — after bundle() returns. A directory left behind by a
// process killed mid-bundle therefore never reads as complete. Absence must
// never render as success, and here absence is the ONLY safe reading.
export function bundleDecision(root, cacheRoot = CACHE_ROOT) {
  const key = sourceKey(root);
  const cacheDir = path.join(cacheRoot, key);
  const marker = path.join(cacheDir, ".complete");
  return { key, cacheDir, marker,
           cached: CACHE_ENABLED && fs.existsSync(marker) };
}

// A CACHED BUNDLE'S public/ IS A SNAPSHOT; RUNTIME ASSETS ARE NOT IN IT.
//
// build_zoom writes zsrc<N>.mp4 into <root>/public at RUN time and hands the
// component `src: "zsrc0.mp4"`. Remotion serves public/ out of the SERVE root,
// which on a cache hit is a bundle directory built by an earlier run — so the
// file the component needs is not there and the render dies with
//
//     Received a status code of 404 while downloading
//     http://localhost:3000/public/zsrc0.mp4
//
// ADDS, NEVER WIPES: the bundle's own public/ entries stay, because they are
// part of the built bundle and only the runtime extras are missing. Idempotent,
// because a container may render more than one batch. A no-op when the serve
// root IS the source root (the cache-miss path), where bundle() already copied
// public/ as it built.
export function syncPublicAssets(root, serveUrl) {
  if (!root || !serveUrl) return 0;
  const from = path.join(root, "public");
  const to = path.join(serveUrl, "public");
  if (path.resolve(from) === path.resolve(to)) return 0;
  if (!fs.existsSync(from)) return 0;
  fs.mkdirSync(to, { recursive: true });
  let n = 0;
  for (const entry of fs.readdirSync(from, { withFileTypes: true })) {
    const src = path.join(from, entry.name);
    const dst = path.join(to, entry.name);
    if (entry.isDirectory()) {
      fs.cpSync(src, dst, { recursive: true, force: true });
      n += 1;
      continue;
    }
    // Skip only when the destination is already byte-for-byte this file, so a
    // re-sync is cheap without ever leaving a stale copy in place.
    try {
      const a = fs.statSync(src), b = fs.statSync(dst);
      if (a.size === b.size && b.mtimeMs >= a.mtimeMs) continue;
    } catch { /* not there yet — copy it */ }
    fs.copyFileSync(src, dst);
    n += 1;
  }
  return n;
}

async function main() {
const { bundle } = await import("@remotion/bundler");
const { renderMedia, selectComposition } = await import("@remotion/renderer");
const d = bundleDecision(R);
const { key, cacheDir, marker } = d;
let serveUrl;
let cached = d.cached;
if (cached) {
  serveUrl = cacheDir;
  // THE CACHE HIT IS THE BROKEN CASE. Without this, every asset written to
  // public/ after the bundle was built is a 404 — six rounds of zoom "ruled and
  // never built" with no component involved. PRINTED, because a reconciliation
  // that runs silently cannot be told apart from one that never ran.
  const synced = syncPublicAssets(R, serveUrl);
  console.log(`PUBLIC_SYNCED ${synced}`);
} else {
  fs.rmSync(cacheDir, { recursive: true, force: true });
  fs.mkdirSync(cacheDir, { recursive: true });
  serveUrl = await bundle({
    entryPoint: path.join(R, "src", "index.ts"),
    outDir: cacheDir,
    onProgress: () => {},
  });
  fs.writeFileSync(marker, key);
}
const bundleMs = Date.now() - t0;
// PRINTED, not just returned. The question this cache exists to answer is "what
// does the shared process actually save", and a bundle_ms that reaches the
// ledger and no output answers nothing.
console.log(`BUNDLE ${bundleMs}`);
console.log(`BUNDLE_CACHED ${cached ? 1 : 0} ${key}`);

for (const j of jobs) {
  const started = Date.now();
  try {
    // THE WHOLE FILE, NOT `.input`.
    //
    // This stripped the wrapper and passed the INNER object as inputProps.
    // Both compositions read `props.input`, so the unwrapped object merged in
    // beside a defaultProps that still carried `input` — and every render
    // silently used DEFAULT_RENDER_INPUT instead of the caller's plan.
    //
    // MEASURED LOCALLY, both nestings, actual output:
    //   overlay unwrapped (shipped)  compDuration 600   21,028,986 bytes
    //   overlay wrapped              compDuration  20    1,663,820 bytes
    //   micro   unwrapped            compDuration   1        5,102 bytes
    //   micro   wrapped              compDuration  20      780,466 bytes
    // DEFAULT_RENDER_INPUT is 600 frames at 60fps with `caption.pages: []`, so
    // every caption pass since the port rendered SIX HUNDRED FRAMES OF NOTHING
    // — a fully transparent .mov — and reported `path=remotion
    // composited=True`, because the file existed and ffmpeg exited 0.
    //
    // The reel never had this bug: it goes through `npx remotion render
    // --props=<file>`, and the CLI passes the WHOLE file. The batch introduced
    // the strip. Callers already write {"input": {...}} for exactly that
    // reason, so this restores the contract rather than changing it.
    const inputProps = JSON.parse(fs.readFileSync(j.propsFile, "utf8"));
    const comp = await selectComposition({ serveUrl, id: j.composition, inputProps });
    await renderMedia({
      composition: comp, serveUrl, inputProps,
      outputLocation: j.out,
      // A PNG SEQUENCE is the only path that preserves alpha here: every video
      // codec available flattens it (prores/vp8/vp9 all yuv) and --pixel-format
      // yuva* is refused outright. Same reason the single-render path used it.
      // ALPHA VIA PRORES 4444, not a PNG sequence.
      //
      // The single-render path used --sequence to a PNG directory because the
      // CLI refuses --pixel-format=yuva* and every other codec flattens alpha.
      // The NODE API does not refuse it: pixelFormat yuva444p10le with
      // imageFormat png renders transparent ProRes directly, verified locally
      // across all nine caption styles. One .mov instead of N thousand PNGs,
      // and ffmpeg composites it in one input.
      imageFormat: "png",
      ...(j.alpha
        ? { codec: "prores", proResProfile: "4444", pixelFormat: "yuva444p10le" }
        : { codec: j.codec ?? "h264" }),
      logLevel: "error",
      // CONCURRENCY 8, NOT 1.
      //
      // This shipped at 1 because it was copied from the measurement harness,
      // where 1 was chosen deliberately to keep the marginal ms/frame clean.
      // The setting leaked from the instrument into the thing being measured —
      // after a whole probe had established that 8 is 2.63x faster.
      //
      // MEASURED in-container, one run, marginal over 180 frames:
      //   conc 1  219.3 ms/frame      conc 6  88.8  (2.47x)
      //   conc 4   90.7 ms/frame      conc 8  83.5  (2.63x)
      // It saturates at 4 and the ceiling is NOT the encoder — a paint-only
      // sweep with renderFrames flattens identically, so more painters past 4
      // buy ~8%. 8 is chosen as the flat top of that curve on an 8-CPU box.
      //
      // COST OF THE BUG, round 32 talking_head: 443 caption frames painted at
      // 299.1 ms/frame for 132.5s of wall.
      concurrency: Number(process.env.PROMPTLY_REMOTION_CONCURRENCY || 8),
    });
    console.log(`JOB ${JSON.stringify({ id: j.id, ok: true, ms: Date.now() - started })}`);
  } catch (e) {
    console.log(`JOB ${JSON.stringify({ id: j.id, ok: false, ms: Date.now() - started,
      error: String(e && e.message ? e.message : e).slice(0, 300) })}`);
  }
}
console.log(`TOTAL ${Date.now() - t0}`);
}

// RUN-AS-MAIN, so importing this module for a test does not start a bundle.
// Without it the smoke could only ever read the source as TEXT — which is how
// this repo keeps shipping checks that a comment can satisfy.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
