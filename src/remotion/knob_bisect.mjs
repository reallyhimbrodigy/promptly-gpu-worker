// WHICH KNOB MOVED THE RENDER? Drop one at a time and look.
//
// Stamp came back DIFFERENT from the before/after pair, and every one of its
// six cut defaults AGREES with its registration when read out of the body:
// style -> "seal", fontKey -> d.fontKey -> "oswald", distress -> d.distress ->
// false, doubleRing -> true, entryScale -> 1.28, textShadow ->
// DEFAULT_TEXT_SHADOW. So reasoning says identical and the render says
// otherwise, which means the reasoning is wrong somewhere it cannot see.
//
// Bisect rather than argue: render the full BEFORE props, then BEFORE minus
// exactly one knob, six times. The one that differs is the cause.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(__dirname, "knob-bisect-out");
fs.mkdirSync(OUT, { recursive: true });
const BEFORE = JSON.parse(fs.readFileSync("/tmp/_reg_before.json", "utf8")).components;
const fixtures = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "catalogue_props.json"), "utf8"));

const TYPE = process.argv[2] || "Stamp";
const KNOBS = (process.argv[3] || "").split(",").filter(Boolean);
const FRAMES = [0, 12, 30, 54];

function baseProps() {
  const p = {};
  for (const q of BEFORE[TYPE].properties) p[q.key] = q.defaultValue;
  for (const [k, v] of Object.entries(fixtures[TYPE] || {})) {
    if (v && typeof v === "object") p[k] = v;
  }
  return p;
}

let serveUrl = null;
async function hashes(props, tag) {
  if (!serveUrl) serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
  const inputProps = { type: TYPE, props, motionBlur: false };
  const composition = await selectComposition({ serveUrl, id: "MGCraftProbe", inputProps });
  const out = [];
  for (const frame of FRAMES) {
    const png = path.join(OUT, `${TYPE}_${tag}_f${frame}.png`);
    await renderStill({ composition, serveUrl, output: png, frame, inputProps,
                        chromiumOptions: { gl: "angle" } });
    out.push(crypto.createHash("sha256").update(fs.readFileSync(png)).digest("hex").slice(0, 12));
  }
  return out.join();
}

const base = baseProps();
const ref = await hashes(base, "ref");
const ctl = await hashes(base, "ctl");
console.log(`control: ${ctl === ref ? "ok" : "FAILED — the harness is the difference"}`);
// ALL AT ONCE, because individually-same and collectively-different is an
// interaction and must be distinguished from a harness artefact.
if (process.env.ALL === "1") {
  const p = { ...base };
  for (const k of KNOBS) delete p[k];
  const h = await hashes(p, "no_all");
  console.log(`  drop ALL ${KNOBS.length}        ${h === ref ? "same" : "MOVED THE RENDER"}`);
}
for (const k of KNOBS) {
  const p = { ...base };
  delete p[k];
  const h = await hashes(p, `no_${k}`);
  console.log(`  drop ${k.padEnd(14)} ${h === ref ? "same" : "MOVED THE RENDER"}`);
}
