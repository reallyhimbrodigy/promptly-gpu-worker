// Footprint measurement: renderStill each candidate at holding frames (PNG,
// transparent bg), report per-frame outputs for the bbox scan.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";

const outDir = process.argv[2];
fs.mkdirSync(outDir, { recursive: true });
const CANDIDATES = ["DropBanner", "DropCard", "SectionDivider_band", "SectionDivider_full", "StepDivider"];
const FRAMES = [90, 180]; // 1.5s + 3.0s @60fps — entrance settled / point slides up

const bundled = await bundle({ entryPoint: "src/index.ts", onProgress: () => {} });
for (const cand of CANDIDATES) {
  const inputProps = { candidate: cand };
  const composition = await selectComposition({ serveUrl: bundled, id: "FootprintProbe", inputProps });
  for (const frame of FRAMES) {
    const out = path.join(outDir, `${cand}_f${frame}.png`);
    try {
      await renderStill({ composition, serveUrl: bundled, output: out, frame, inputProps,
                          imageFormat: "png", logLevel: "error" });
      console.log(`FOOTPRINT_OK ${cand} f${frame}`);
    } catch (e) {
      console.log(`FOOTPRINT_FAIL ${cand} f${frame} :: ${String(e).slice(0, 200)}`);
    }
  }
}
console.log("FOOTPRINT_DONE");
