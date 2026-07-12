// WS2 caption fade-bound sample battery — bundle ONCE, renderMedia the
// CaptionFadeProbe for each style at a watchable scale. Run with a label arg
// (`before` / `after`); render the CURRENT code state, then git-stash the style
// edits and render the other label. `node caption-fade-battery.mjs after CleanCut Prime`
import path from "path";
import { fileURLToPath } from "url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const label = process.argv[2] || "after";
const styles = process.argv.slice(3);
const STYLES = styles.length ? styles : ["CleanCut", "Prime"];

const WORDS = ["this", "is", "the", "fastest", "way", "to", "grow", "your", "account", "right", "now", "today"];
const KEYWORDS = ["fastest", "grow"];
const WORD_MS = 170; // fast speech — the regime where a fixed fade overruns the word

const OUT = process.env.FADE_OUT_DIR || "/private/tmp/claude-501/-Users-zaclibman-promptly-gpu-worker-promptly-gpu-worker/0623ccac-66e9-4782-b62c-b235bcc403aa/scratchpad/fade";

const bundled = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts"), onProgress: () => {} });

for (const style of STYLES) {
  const out = path.join(OUT, `fade_${style}_${label}.mp4`);
  const inputProps = { style, words: WORDS, keywords: KEYWORDS, wordMs: WORD_MS, label: `${label}` };
  const composition = await selectComposition({ serveUrl: bundled, id: "CaptionFadeProbe", inputProps });
  await renderMedia({
    composition, serveUrl: bundled, outputLocation: out, codec: "h264",
    inputProps,
    scale: 0.5, // 540x960 — legible for fade timing, fast to render
    crf: 18,
  });
  console.log(`RENDERED ${style} [${label}] -> ${out}`);
}
console.log("BATTERY DONE");
