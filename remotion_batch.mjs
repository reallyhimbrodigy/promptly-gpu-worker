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
      logLevel: "error", concurrency: 1,
    });
    console.log(`JOB ${JSON.stringify({ id: j.id, ok: true, ms: Date.now() - started })}`);
  } catch (e) {
    console.log(`JOB ${JSON.stringify({ id: j.id, ok: false, ms: Date.now() - started,
      error: String(e && e.message ? e.message : e).slice(0, 300) })}`);
  }
}
console.log(`TOTAL ${Date.now() - t0}`);
