// TAG SWAP PROOF (Zac 2026-08-02). Renders FocusWindow + LetterboxPush and
// records ms/frame + the output, so BEFORE and AFTER the OffthreadVideo ->
// @remotion/media <Video> swap can be PSNR'd. Identical pixels + fewer ms/frame
// is the pass condition; a prop-existence check cannot prove startFrom is
// honoured, a frame-diff can.
//   node src/remotion/zoom-tag-swap-proof.mjs <before|after>
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R = path.dirname(fileURLToPath(import.meta.url));
const arm = process.argv[2] || "before";
const out = path.join(R, "velocity-cap-out", "tagswap"); fs.mkdirSync(out, { recursive: true });
const EV = [{ startMs: 400, durationMs: 1400, scale: 1.25, originX: 0.5, originY: 0.45 }];
const b = await bundle({ entryPoint: path.join(R, "src", "index.ts"), onProgress: () => {} });
for (const component of ["FocusWindow", "LetterboxPush"]) {
  const inputProps = { component, events: EV, src: "vcap_head.mp4" };
  const c = await selectComposition({ serveUrl: b, id: "ZoomTagProbe", inputProps });
  const t = Date.now();
  await renderMedia({ composition: c, serveUrl: b, inputProps, codec: "h264",
    outputLocation: path.join(out, `${component}_${arm}.mp4`), logLevel: "error", concurrency: 1 });
  const ms = Date.now() - t;
  console.log(`${arm.padEnd(6)} ${component.padEnd(14)} wall=${(ms/1000).toFixed(2)}s ms/frame=${(ms/c.durationInFrames).toFixed(1)}`);
}
