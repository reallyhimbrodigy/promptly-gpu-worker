// Word-visibility law: render the divider layer ALONE at both specimen
// placements (v1 regression, v2 shipped) for the per-word measurement.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
const outDir = process.argv[2];
const bundled = await bundle({ entryPoint: "src/index.ts", onProgress: () => {} });
for (const [name, dx, dy] of [["divider_v5_leftcol", -220, 0]]) {
  const inputProps = { candidate: "SectionDivider_band_top", dx, dy };
  const composition = await selectComposition({ serveUrl: bundled, id: "FootprintProbe", inputProps });
  await renderStill({ composition, serveUrl: bundled, output: `${outDir}/${name}.png`,
                      frame: 120, inputProps, imageFormat: "png", logLevel: "error" });
  console.log(`WORDVIS_OK ${name}`);
}
