// MULTILINGUAL A2 — script contact sheet. Renders REAL hard-case strings per
// script family through a caption style (Prime) → one still each. The hardest
// honest test: shaping bugs only show on real letter combinations. Drives:
//   node script-battery.mjs <outDir>
// Then inspect the PNGs for tofu / wrong direction / broken breaks.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = process.argv[2] || path.join(__dirname, "script-out");
fs.mkdirSync(outDir, { recursive: true });

// Real hard cases — not transliterated filler. Each exposes a specific shaping
// or coverage risk that only appears on genuine letter combinations.
const CASES = [
  { key: "1-arabic-joining", words: ["بِسْمِ", "اللَّه"], note: "Arabic joining + shadda/kasra marks" },
  { key: "2-arabic-lamalef", words: ["لا", "إلا"], note: "lam-alef ligature" },
  { key: "3-hebrew-rtl", words: ["שָׁלוֹם", "עוֹלָם"], note: "Hebrew RTL + niqqud" },
  { key: "4-devanagari-conjunct", words: ["क्षत्रिय", "त्रिशूल"], note: "kṣa (क्ष) + tra (त्र) conjuncts" },
  { key: "5-thai-stacked", words: ["ที่นี่", "ปัญหา"], note: "Thai stacked vowels + tone marks" },
  { key: "6-cjk-latin-mix", words: ["AI技術で", "日本語"], note: "CJK + Latin in one caption (font-mix)" },
  { key: "7-emoji", words: ["Let's", "go🔥💯🚀"], note: "UGC color emoji" },
  { key: "8-latin-control", words: ["DOWNLOAD", "PROMPTLY"], note: "Latin control — must be byte-identical to before" },
];

const STYLE = "Prime"; // a clean style that shows the glyphs plainly
const SCAN_FRAME = 45;

const bundled = await bundle({
  entryPoint: path.join(__dirname, "src", "index.ts"),
  onProgress: () => {},
});

let failed = 0;
for (const c of CASES) {
  const props = { style: STYLE, words: c.words, keywords: [], position: "center" };
  const composition = await selectComposition({ serveUrl: bundled, id: "FitSpecimen", inputProps: props });
  const out = path.join(outDir, `${c.key}.png`);
  try {
    await renderStill({ composition, serveUrl: bundled, output: out, frame: SCAN_FRAME, inputProps: props, logLevel: "warn" });
    console.log(`SHEET_OK ${c.key} :: ${c.note}`);
  } catch (err) {
    failed++;
    console.log(`SHEET_FAIL ${c.key} :: ${String(err).slice(0, 300)}`);
  }
}
console.log(`SHEET_DONE rendered=${CASES.length - failed} failed=${failed}`);
process.exit(failed > 0 ? 1 : 0);
