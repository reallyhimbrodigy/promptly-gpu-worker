// DOES CUTTING A KNOB CHANGE THE RENDER? It must not.
//
// A cut removes the key from __mapped, so the component receives `undefined`
// and ITS OWN parameter default applies. The claim is that this HARDCODES THE
// CURRENT DEFAULT — the registered default and the body default are the same
// value, so nothing moves.
//
// THAT CLAIM IS EXACTLY WHAT THIS LANE HAS BEEN WRONG ABOUT BEFORE. "The
// registered default IS the value" was written down here after 135 defaults
// were wrong and 0 of 14 components drew. If a registered default disagrees
// with the body's, a cut silently CHANGES the render and every check passes.
//
// So the pair is rendered: props FROM THE OLD REGISTRY against props from the
// new one, same component, same frames. Byte-identity is the bar, per the
// render-determinism law. A CONTROL PAIR runs first — the same props twice —
// because a difference could otherwise be the harness.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "knob-ab-out");
fs.mkdirSync(OUT, { recursive: true });

const BEFORE = JSON.parse(fs.readFileSync("/tmp/_reg_before.json", "utf8")).components;
const AFTER = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "chatcut_registry_baked.json"), "utf8")).components;
const fixtures = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "catalogue_props.json"), "utf8"));

const TYPES = (process.argv[2] || "Stamp,PullQuote,PillMarquee,SectionDivider,DropCard,ChatThread")
  .split(",");
const FRAMES = (process.env.FRAMES || "0,5,12,22,36,54").split(",").map(Number);

function propsFrom(reg, type) {
  const e = reg[type];
  if (!e) throw new Error(`no ${type}`);
  const p = {};
  for (const q of e.properties) p[q.key] = q.defaultValue;
  for (const [k, v] of Object.entries(fixtures[type] || {})) {
    if (v && typeof v === "object") p[k] = v;
  }
  return p;
}

let serveUrl = null;
async function renderSet(type, props, tag) {
  if (!serveUrl) serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
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

const results = [];
for (const type of TYPES) {
  try {
    const pb = propsFrom(BEFORE, type);
    const pa = propsFrom(AFTER, type);
    const cut = Object.keys(pb).filter((k) => !(k in pa));
    if (!cut.length) {
      console.log(`${type}: NO KNOBS CUT — nothing to compare (checked, not assumed)`);
      results.push({ type, verdict: "NO_CUT" });
      continue;
    }
    const a = await renderSet(type, pb, "before");
    const ctl = await renderSet(type, pb, "ctl");
    const controlOk = ctl.join() === a.join();
    const b = await renderSet(type, pa, "after");
    const same = a.join() === b.join();
    const diff = FRAMES.filter((_, i) => a[i] !== b[i]);
    const verdict = !controlOk ? "CONTROL_FAILED" : (same ? "IDENTICAL" : "DIFFERENT");
    console.log(`${type}: ${verdict}  cut=${cut.length}  control=${controlOk ? "ok" : "FAILED"}`
      + (same ? "" : `  frames differing: ${diff.join(",")}`));
    results.push({ type, verdict, cut, controlOk, diff });
  } catch (e) {
    console.log(`${type}: RENDER FAILED — ${e.message}`);
    results.push({ type, verdict: "RENDER_FAILED", why: e.message });
  }
}
fs.writeFileSync(path.join(OUT, "verdicts.json"), JSON.stringify(results, null, 1));
console.log("\n" + JSON.stringify(results.map((r) => `${r.type}=${r.verdict}`)));
