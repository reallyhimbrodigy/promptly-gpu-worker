// F4 worst-case string battery — bundle ONCE, renderStill per case.
// Every case renders FitSpecimen (strict fit invariant armed: overflow
// THROWS and the still fails). test_caption_fit.py drives this and
// pixel-scans the output margins. Usage: node fit-battery.mjs <outDir>
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(__dirname, "fit-battery-out");
fs.mkdirSync(outDir, { recursive: true });

const STYLES = [
  "CleanCut",
  "Cove",
  "Gadzhi",
  "Lumen",
  "Prime",
  "Pulse",
  "Quintessence",
  "TwoTone",
  "TypewriterReveal",
];

// Worst-case strings. Production pages carry <=2 tokens (the 2-word page
// cap); the worst word goes LAST so single-word-at-a-time styles show it.
const CASES = [
  { key: "maxword", words: ["ENTREPRENEURSHIP"], keywords: [] },
  { key: "observed", words: ["DOWNLOAD", "PROMPTLY."], keywords: [] },
  {
    key: "twolong",
    words: ["INCOMPREHENSIBILITIES", "INTERNATIONALIZATION"],
    keywords: [],
  },
  {
    key: "kwmult", // exercises keyword/special/boxed/shine size multipliers
    words: ["DOWNLOAD", "ENTREPRENEURSHIP"],
    keywords: ["ENTREPRENEURSHIP"],
  },
];

const SCAN_FRAME = 45; // 0.75s @60fps — entrances settled, all words live

const jobs = [];
for (const style of STYLES) {
  for (const c of CASES) {
    jobs.push({
      name: `${style}__${c.key}`,
      props: { style, words: c.words, keywords: c.keywords, position: "bottom" },
    });
  }
  // top-position spot check for the anchored-edge styles
  jobs.push({
    name: `${style}__maxword_top`,
    props: { style, words: ["ENTREPRENEURSHIP"], keywords: [], position: "top" },
  });
}
jobs.push({
  name: "StickyNotes__longnote",
  props: {
    style: "StickyNotes",
    words: ["INCOMPREHENSIBILITIES", "INTERNATIONALIZATION"],
    keywords: [],
    position: "bottom",
  },
});
jobs.push({
  name: "StickyNotes__grounded",
  props: { style: "StickyNotes", words: ["HIT", "SEND"], keywords: [], position: "bottom" },
});

const bundled = await bundle({
  entryPoint: path.join(__dirname, "src", "index.ts"),
  onProgress: () => {},
});

let failed = 0;
for (const job of jobs) {
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "FitSpecimen",
    inputProps: job.props,
  });
  const out = path.join(outDir, `${job.name}.png`);
  try {
    await renderStill({
      composition,
      serveUrl: bundled,
      output: out,
      frame: SCAN_FRAME,
      inputProps: job.props,
      // Surface component console output (the [caption-fit] telemetry and
      // any strict-invariant throw) into this process's logs.
      logLevel: "warn",
    });
    console.log(`STILL_OK ${job.name}`);
  } catch (err) {
    failed++;
    console.log(`STILL_FAIL ${job.name} :: ${String(err).slice(0, 300)}`);
  }
}
console.log(`BATTERY_DONE rendered=${jobs.length - failed} failed=${failed}`);
process.exit(failed > 0 ? 1 : 0);
