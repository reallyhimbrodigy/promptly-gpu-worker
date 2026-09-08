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
 *   [{ id, composition, propsFile, out, sequence?, imageFormat? }, ...]
 * Emits one JSON line per job to stdout prefixed "JOB " so the caller can
 * attribute failures per entry rather than losing the batch to one bad job.
 */
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const R = "/promptly-remotion";
const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const t0 = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(R, "src", "index.ts"), onProgress: () => {} });
const bundleMs = Date.now() - t0;
console.log(`BUNDLE ${bundleMs}`);

for (const j of jobs) {
  const started = Date.now();
  try {
    const inputProps = JSON.parse(fs.readFileSync(j.propsFile, "utf8")).input;
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
