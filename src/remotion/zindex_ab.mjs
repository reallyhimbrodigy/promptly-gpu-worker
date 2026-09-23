// DOES zIndex CHANGE THE PAINT? Render the pair and look.
//
// ChatCut's validator refuses `zIndex` outright, and the refusal text says why:
// "the renderer paints elements in DOM order ... The preview would show it and
// the exported video would not." So a local render of a body that STILL HAS
// zIndex is the WRONG control — our renderer honours it and theirs does not.
//
// But a local render with zIndex REMOVED is exactly what ChatCut will paint.
// So the question is asked as a PAIR:
//
//   WITH zIndex     = the intended appearance
//   WITHOUT zIndex  = DOM order only = what ChatCut exports
//
//   identical  -> deleting is safe, AND the current body would have exported
//                 correctly anyway
//   different  -> THE CURRENT BODY IS ALREADY BROKEN AT EXPORT, and the fix is
//                 a DOM reorder, not a deletion
//
// Byte-identity is the bar, per the render-determinism law: on a fixed plan any
// difference is a defect, not variance.
//
// AND IT RENDERS A CONTROL PAIR FIRST. Two bundles of the SAME source must come
// back byte-identical, or a difference in the real pair could be the harness
// rather than the component — the shared-path root produces a false RED too.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "zindex-ab-out");
fs.mkdirSync(OUT, { recursive: true });

const TYPES = (process.argv[2] || "DropCard,EditorialQuote,PillMarquee,PullQuote,Timeline,TimelineRoadmap").split(",");
const FRAMES = (process.env.FRAMES || "0,4,8,14,22,32,48,64").split(",").map(Number);

const reg = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "chatcut_registry_baked.json"), "utf8"));

// The zIndex declarations live in the .tsx tree, which is what this renders.
const srcFor = (t) => path.join(__dirname, "src", "motion-graphics", t, `${t}.tsx`);

// STRIP, NOT REORDER. This mutation asks ONLY "did zIndex matter" — it must
// not also change the DOM, or the answer describes two changes at once.
// COMMENTS ARE NOT CODE, AND COUNTING MATCHES IS NOT READING WHERE THEY LAND.
// The fix comments written for these very components say the word "zIndex", so
// the first version counted them, found them still present after the strip,
// and reported HARNESS FAILURE on two correctly-fixed components. Third time
// in one session: the NO STILL scan, the currentColor grep, and now this. A
// check that reads source cannot tell code from prose unless it is told to.
function codeOnly(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "")
            .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
            .replace(/(^|[^:])\/\/[^\n]*/g, (m, p1) => p1);
}

function stripZIndex(src) {
  const before = (codeOnly(src).match(/zIndex\s*:/g) || []).length;
  const out = src.replace(/^\s*zIndex\s*:\s*[^,\n]+,?\s*$/gm, "")
                 .replace(/zIndex\s*:\s*[^,}\n]+,\s*/g, "");
  const after = (codeOnly(out).match(/zIndex\s*:/g) || []).length;
  return { out, before, after };
}

async function renderSet(tag, type, props) {
  const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
  const inputProps = { type, props, motionBlur: false };
  const composition = await selectComposition({ serveUrl, id: "MGCraftProbe", inputProps });
  const hashes = [];
  for (const frame of FRAMES) {
    const png = path.join(OUT, `${type}_${tag}_f${String(frame).padStart(3, "0")}.png`);
    await renderStill({ composition, serveUrl, output: png, frame, inputProps,
                        chromiumOptions: { gl: "angle" } });
    hashes.push(crypto.createHash("sha256").update(fs.readFileSync(png)).digest("hex").slice(0, 16));
  }
  return hashes;
}

// THE PROBE RENDERS THE .tsx TREE, WHICH STILL TAKES ARRAYS. Flattening moved
// the REGISTRY to numbered scalars (pill1..pill12, paletteColor1..3), so the
// registered defaults alone hand a component that destructures `pills` an
// undefined, and it dies on `pills.length` — which is a PROBE fault reported
// as a component fault. PillMarquee failed exactly this way on the first run.
//
// So the fixture's own arrays and objects are merged in, the way __mapped
// rebuilds them at render time. Same thing measure_mg_box.mjs does for baked
// keys, generalised: any list or dict in the fixture is content the component
// expects to receive whole.
const fixtures = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "catalogue_props.json"), "utf8"));

function propsFor(type) {
  const entry = reg.components[type];
  if (!entry) throw new Error(`no ${type} in the baked registry`);
  const props = {};
  for (const p of entry.properties) props[p.key] = p.defaultValue;
  for (const [k, v] of Object.entries(fixtures[type] || {})) {
    if (v && typeof v === "object") props[k] = v;
  }
  return props;
}

const results = [];
for (const type of TYPES) {
  const file = srcFor(type);
  if (!fs.existsSync(file)) { console.log(`${type}: NO TSX — skipped`); continue; }
  const original = fs.readFileSync(file, "utf8");
  const { out: stripped, before, after } = stripZIndex(original);
  if (before === 0) {
    console.log(`${type}: NO zIndex IN THE TSX — nothing to compare (checked, not assumed)`);
    results.push({ type, verdict: "NO_ZINDEX", before });
    continue;
  }
  if (after !== 0) {
    console.log(`${type}: HARNESS FAILURE — ${after} of ${before} zIndex survived the strip`);
    results.push({ type, verdict: "HARNESS_FAILURE", before, after });
    continue;
  }

  const props = propsFor(type);
  try {
    const a = await renderSet("with", type, props);
    // CONTROL: same source, second bundle. Must match `a` byte for byte.
    const ctl = await renderSet("ctl", type, props);
    const controlOk = ctl.join() === a.join();

    fs.writeFileSync(file, stripped);
    let b;
    try { b = await renderSet("without", type, props); }
    finally { fs.writeFileSync(file, original); }

    if (fs.readFileSync(file, "utf8") !== original) {
      console.log(`${type}: HARNESS FAILURE — residue left in ${file}`);
      results.push({ type, verdict: "RESIDUE" });
      continue;
    }

    const same = a.join() === b.join();
    const diffFrames = FRAMES.filter((_, i) => a[i] !== b[i]);
    const verdict = !controlOk ? "CONTROL_FAILED" : (same ? "IDENTICAL" : "DIFFERENT");
    console.log(`${type}: ${verdict}  zIndex=${before}  control=${controlOk ? "ok" : "FAILED"}`
      + (same ? "" : `  frames differing: ${diffFrames.join(",")}`));
    results.push({ type, verdict, zIndexCount: before, controlOk, diffFrames });
  } catch (e) {
    console.log(`${type}: RENDER FAILED — ${e.message}`);
    results.push({ type, verdict: "RENDER_FAILED", why: e.message });
  }
}

fs.writeFileSync(path.join(OUT, "verdicts.json"), JSON.stringify(results, null, 1));
console.log("\n" + JSON.stringify(results.map((r) => `${r.type}=${r.verdict}`), null, 0));
