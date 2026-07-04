import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
const alphaUrl = fs.readFileSync(process.argv[2], "utf8").trim();
const bundled = await bundle({ entryPoint: "src/index.ts", onProgress: () => {} });
const composition = await selectComposition({ serveUrl: bundled, id: "AlphaProbe", inputProps: { alphaUrl } });
await renderStill({ composition, serveUrl: bundled, output: process.argv[3], frame: 15, inputProps: { alphaUrl }, logLevel: "verbose" }).then(
  () => console.log("ALPHA_PROBE_OK"),
  (e) => console.log("ALPHA_PROBE_FAIL", String(e).slice(0, 500)));
