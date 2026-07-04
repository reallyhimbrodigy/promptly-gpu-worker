// Behind-layer Phase 1: alpha-format decode probe + specimen renderer.
// Bundle once; render BehindSpecimen per case; report wall-clock per format.
// Usage: node behind-probe.mjs cases.json outDir
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const outDir = process.argv[3];
fs.mkdirSync(outDir, { recursive: true });

const bundled = await bundle({
  entryPoint: path.join(__dirname, "src", "index.ts"),
  onProgress: () => {},
});

for (const c of cases) {
  const t0 = Date.now();
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "BehindSpecimen",
    inputProps: c.props,
  });
  const out = path.join(outDir, `${c.name}.mp4`);
  try {
    await renderMedia({
      composition: { ...composition, durationInFrames: c.frames ?? 150 },
      serveUrl: bundled,
      codec: "h264",
      outputLocation: out,
      inputProps: c.props,
      logLevel: "error",
    });
    const s = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`SPECIMEN_OK ${c.name} render_s=${s}`);
  } catch (err) {
    console.log(`SPECIMEN_FAIL ${c.name} :: ${String(err).slice(0, 300)}`);
  }
}
console.log("PROBE_DONE");
