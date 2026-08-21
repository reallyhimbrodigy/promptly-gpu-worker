// MG catalogue render-proof. Bundles once, renderStill across a component's
// entrance/settle window via the existing MGAttackProbe (flat plate, startMs=0).
// No source video — the catalogue components are pure type. Usage:
//   node render-mg-proof.mjs <Type> <before|after>
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "mg-proof-out");
fs.mkdirSync(outDir, { recursive: true });

const TYPE = process.argv[2] || "StatCard";
const TAG = process.argv[3] || "before";
const BG = process.argv[4]; // optional footage filename in public/ (contrast-floor check)

// Palette like the job's deterministic extractor. Over FOOTAGE the overlay ink is
// LIGHT (the palette's video-overlay colour) so it reads on any luminance; on the
// flat gray PLATE (before/after comparison) dark ink shows the composition best.
const PAL = BG
  ? { number: "#FEFCFD", label: "#FEFCFD", accent: "#F4903E" }
  : { number: "#14141A", label: "#14141A", accent: "#8B350D" };
const PROPS = {
  StatCard: { value: 100000, label: "SUBSCRIBERS", numberColor: PAL.number, labelColor: PAL.label, accentColor: PAL.accent, anchor: "center" },
  Stamp: { text: "SOLD OUT", color: PAL.accent, anchor: "center" },
  PillCluster: { pills: ["mindset", "focus", "discipline"], accentColor: PAL.accent, anchor: "center" },
}[TYPE] || {};
const FRAMES = { StatCard: [4, 14, 28, 46], Stamp: [3, 8, 16, 46], PillCluster: [3, 12, 24, 46] }[TYPE] || [4, 14, 28, 46];

console.log(`[mg-proof] ${TYPE} (${TAG}) — bundling…`);
const serveUrl = await bundle({ entryPoint: path.resolve(__dirname, "src/index.ts") });
const inputProps = { type: TYPE, props: PROPS, motionBlur: true, ...(BG ? { bgVideo: BG } : {}) };
const composition = await selectComposition({ serveUrl, id: "MGCraftProbe", inputProps });
for (const frame of FRAMES) {
  const output = path.join(outDir, `${TYPE}_${TAG}_f${String(frame).padStart(2, "0")}.png`);
  await renderStill({ composition, serveUrl, output, frame, inputProps, chromiumOptions: { gl: "angle" } });
  console.log("[mg-proof] wrote", path.basename(output));
}
console.log("[mg-proof] DONE →", outDir);
