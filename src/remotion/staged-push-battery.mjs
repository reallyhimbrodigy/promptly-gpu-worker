// StagedPush isolated LOOK battery — bundle once, render the multi-stage emphasis
// zoom in three shapes so the animation quality is judgeable in isolation BEFORE any
// Gemini wiring: a 3-part continuing (ease-out release), a 3-part cut-terminated (ends
// at the cut, no release), and a 2-part. Peaks are at fixed onsets; equal +8% steps.
// Usage: node staged-push-battery.mjs <outDir>
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(__dirname, "staged-push-out");
fs.mkdirSync(outDir, { recursive: true });

const CASES = {
  "3part_continuing": [
    {
      stages: [
        { atMs: 1000, scale: 1.08 },
        { atMs: 1800, scale: 1.16 },
        { atMs: 2600, scale: 1.24 },
      ],
      cutTerminated: false,
    },
  ],
  "3part_cut": [
    {
      stages: [
        { atMs: 1000, scale: 1.08 },
        { atMs: 1800, scale: 1.16 },
        { atMs: 2600, scale: 1.24 },
      ],
      cutTerminated: true,
    },
  ],
  "2part_continuing": [
    {
      stages: [
        { atMs: 1000, scale: 1.08 },
        { atMs: 1800, scale: 1.16 },
      ],
      cutTerminated: false,
    },
  ],
};

const bundled = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts"), onProgress: () => {} });

let ok = 0, fail = 0;
for (const [name, events] of Object.entries(CASES)) {
  const out = path.join(outDir, `${name}.mp4`);
  try {
    const composition = await selectComposition({ serveUrl: bundled, id: "StagedPushProbe", inputProps: { events } });
    await renderMedia({
      composition, serveUrl: bundled, outputLocation: out, codec: "h264",
      inputProps: { events },
      logLevel: "error",
    });
    console.log(`OK   ${name} -> ${out}`);
    ok++;
  } catch (e) {
    console.log(`FAIL ${name}: ${String(e).slice(0, 200)}`);
    fail++;
  }
}
console.log(`\nStagedPush battery: ${ok} ok, ${fail} fail -> ${outDir}`);
