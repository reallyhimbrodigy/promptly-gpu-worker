// CODEC OFFSET CHECK (Zac 2026-08-02). The tag swap shifts luma by a uniform
// ~1.3 levels. A uniform offset is invisible; UNEQUAL offsets between components
// would put a STEP at every cut, which an eye does catch. Decode-level shifts
// can depend on colour metadata, so this renders the SAME component on sources
// with different range/primaries and reports the offset for each.
//   node src/remotion/codec-offset-check.mjs <old|new>
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R = path.dirname(fileURLToPath(import.meta.url));
const arm = process.argv[2] || "old";
const out = path.join(R, "velocity-cap-out", "codec"); fs.mkdirSync(out, { recursive: true });
const EV = [{ startMs: 400, durationMs: 1400, scale: 1.25, originX: 0.5, originY: 0.45 }];
const b = await bundle({ entryPoint: path.join(R, "src", "index.ts"), onProgress: () => {} });
for (const src of ["vcap_head.mp4", "alt_bt601.mp4", "alt_full.mp4"]) {
  const inputProps = { component: "FocusWindow", events: EV, src };
  const c = await selectComposition({ serveUrl: b, id: "ZoomTagProbe", inputProps });
  await renderMedia({ composition: c, serveUrl: b, inputProps, codec: "h264",
    outputLocation: path.join(out, `${src.replace(".mp4","")}_${arm}.mp4`),
    logLevel: "error", concurrency: 1 });
  console.log(`${arm} ${src}`);
}
