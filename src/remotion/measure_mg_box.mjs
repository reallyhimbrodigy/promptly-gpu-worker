// PEAK-FRAME REGISTRATION BOX.
//
// THE BOX IS A CLIP BOX. ChatCut renders the motion graphic at the project
// canvas and the REGISTERED BOX crops it, so a box measured too small does not
// shrink the graphic — it CUTS it, and the cut looks like a broken component.
// RankedList's row 1 survives as an orange bar because Anton's "1" at 235px is
// what is left of it after the crop; PillCluster disappears entirely.
//
// WHY EVERY FRAME AND NOT A SAMPLE. My earlier boxes were measured at frames
// 15 and 45 and four of them came out too small, because a component's extent
// is NOT monotonic: Stamp peaks at local frame 2 (1080x718) and then
// UNDERSHOOTS at frame 8. Sampling two frames lands on whatever the curve is
// doing there. Entrance overshoot (pills pop from scale 1.28), rotation, drop
// and float all push ink outside the layout box, and each peaks at a different
// moment. So: sweep the window, take the bbox per frame, UNION them, and name
// the frame that set each edge.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, "box-measure-out");
fs.mkdirSync(outDir, { recursive: true });

const TYPE = process.argv[2] || "RankedList";
const LAST = Number(process.env.LAST || 80);
const STEP = Number(process.env.STEP || 1);

// The registered defaults, so the box describes WHAT SHIPS. A box measured on
// convenient props is a box for a placement nobody makes.
const reg = JSON.parse(fs.readFileSync(
  path.join(__dirname, "..", "..", "chatcut_registry_baked.json"), "utf8"));
const entry = reg.components[TYPE];
if (!entry) { console.error(`no ${TYPE} in the baked registry`); process.exit(1); }
const props = {};
for (const p of entry.properties) props[p.key] = p.defaultValue;
// Baked content (items/tags/notes) lives in the CODE, not the properties, so
// the probe must supply it the same way a placement would.
const baked = { RankedList: "items", PillCluster: "tags", StickyNotes: "notes" }[TYPE];
if (baked) {
  const m = entry.code.match(new RegExp(`${baked}:\\s*(\\[[\\s\\S]*?\\]),\\n`));
  if (m) props[baked] = JSON.parse(m[1]);
}
// OVERRIDES, so a box can be measured for the placement being asked about
// rather than for the defaults. Reticle's `label` defaults to "" and the tag
// is guarded on it, so the default box is the box of a component with its tag
// switched off — measuring that and calling it Reticle's box is measuring a
// different component.
if (process.env.PROPS_JSON) Object.assign(props, JSON.parse(process.env.PROPS_JSON));
console.log(`${TYPE}: ${Object.keys(props).length} registered props` +
  (baked && props[baked] ? `, ${props[baked].length} baked ${baked}` : ""));

const serveUrl = await bundle({ entryPoint: path.join(__dirname, "src", "index.ts") });
const inputProps = { type: TYPE, props, motionBlur: false };
const composition = await selectComposition({ serveUrl, id: "MGCraftProbe", inputProps });

const PLATE = [0x80, 0x80, 0x80];
const TOL = 10;   // a pixel is DRAWN if any channel differs from the plate by more
const rows = [];
for (let frame = 0; frame <= LAST; frame += STEP) {
  const png = path.join(outDir, `${TYPE}_f${String(frame).padStart(3, "0")}.png`);
  await renderStill({ composition, serveUrl, output: png, frame, inputProps,
                      chromiumOptions: { gl: "angle" } });
  const raw = path.join(outDir, "_f.rgb");
  execFileSync("ffmpeg", ["-nostdin", "-loglevel", "error", "-y", "-i", png,
                          "-f", "rawvideo", "-pix_fmt", "rgb24", raw]);
  const buf = fs.readFileSync(raw);
  const W = composition.width, H = composition.height;
  let x0 = W, y0 = H, x1 = -1, y1 = -1, n = 0;
  for (let y = 0; y < H; y += 1) {
    for (let x = 0; x < W; x += 1) {
      const i = (y * W + x) * 3;
      if (Math.abs(buf[i] - PLATE[0]) > TOL || Math.abs(buf[i + 1] - PLATE[1]) > TOL
          || Math.abs(buf[i + 2] - PLATE[2]) > TOL) {
        n += 1;
        if (x < x0) x0 = x; if (x > x1) x1 = x;
        if (y < y0) y0 = y; if (y > y1) y1 = y;
      }
    }
  }
  rows.push(n === 0 ? { frame, empty: true }
                    : { frame, x0, y0, x1, y1, w: x1 - x0 + 1, h: y1 - y0 + 1, px: n });
  fs.unlinkSync(png); fs.unlinkSync(raw);
}

const drawn = rows.filter((r) => !r.empty);
if (!drawn.length) { console.error("NOTHING DREW ON ANY FRAME — that is the finding, not an empty box."); process.exit(2); }
const U = {
  x0: Math.min(...drawn.map((r) => r.x0)), y0: Math.min(...drawn.map((r) => r.y0)),
  x1: Math.max(...drawn.map((r) => r.x1)), y1: Math.max(...drawn.map((r) => r.y1)),
};
U.w = U.x1 - U.x0 + 1; U.h = U.y1 - U.y0 + 1;
const at = (k, pick) => drawn.find((r) => r[k] === pick).frame;
const peak = drawn.reduce((a, r) => (r.w * r.h > a.w * a.h ? r : a), drawn[0]);
console.log(`\nframes drawn: ${drawn.length}/${rows.length}` +
  (rows.length - drawn.length ? `  (empty: ${rows.filter(r=>r.empty).map(r=>r.frame).join(",")})` : ""));
console.log(`largest SINGLE frame : f${peak.frame}  ${peak.w}x${peak.h} at (${peak.x0},${peak.y0})`);
console.log(`UNION across frames  : ${U.w}x${U.h} at (${U.x0},${U.y0})`);
console.log(`  left  edge set by f${at("x0", U.x0)}`);
console.log(`  top   edge set by f${at("y0", U.y0)}`);
console.log(`  right edge set by f${at("x1", U.x1)}`);
console.log(`  bot   edge set by f${at("y1", U.y1)}`);
console.log(`single-frame box would UNDER-measure by ${U.w - peak.w}px wide, ${U.h - peak.h}px tall`);
fs.writeFileSync(path.join(outDir, `${TYPE}_box.json`),
  JSON.stringify({ type: TYPE, canvas: [composition.width, composition.height],
                   union: U, peak_single_frame: peak, per_frame: rows }, null, 1));
