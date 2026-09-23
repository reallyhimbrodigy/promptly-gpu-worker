// NATURAL_BOX for the twelve, re-measured against TODAY'S bodies.
//
// WHY ALL TWELVE AND NOT THE TWO THAT ARE KNOWN BAD. StatCard's 1012x301 was
// measured against an older layout and cut the accent spine and label off
// entirely; nothing said so until a frame was taken at a deliberately
// oversized box. A box measured against a body that has since changed is
// indistinguishable from a correct one, and every one of these bodies has
// changed at least once since its box was set.
//
// PEAK-FRAME, UNIONED. A component's extent is NOT monotonic — RankedList
// peaks at f40 at 1058x654 and then shrinks, and its four edges are set by
// four different frames. A sample lands wherever the curve happens to be.
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { execFileSync } from "node:child_process";

const ROOT = process.cwd();
const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "..", "..", "chatcut_registry_baked.json"), "utf8")).components;
const LAST = Number(process.env.LAST || 70), STEP = Number(process.env.STEP || 3);
const outDir = path.join(ROOT, "box-measure-out");
fs.mkdirSync(outDir, { recursive: true });

// The body a placement actually gets: registered defaults, plus the baked
// content the blob carries, plus — for the flattened ones — real text in the
// numbered slots, because an EMPTY slot is filtered out and a box measured on
// empty slots is the box of a component drawing nothing.
// THE PROBE RENDERS THE .tsx, WHICH STILL TAKES ARRAYS. The flattening into
// note1/row1Title/pill1 is a REGISTRATION-TIME transform inside bake_registry:
// the blob rebuilds the array from numbered scalars, the source never did.
// Passing the flattened names here handed the TSX undefined and it drew
// nothing — reported as "NOTHING DREW" for three components that draw fine.
// A harness fault wearing three findings.
const FILL = {
  StickyNotes: { notes: [{ text: "hook", color: "#FFE86B", rotation: -4 },
                         { text: "proof", color: "#9BE7A6", rotation: 3 },
                         { text: "close", color: "#FFB3C1", rotation: -2 }] },
  RankedList: { items: [{ rank: "1", label: "HOOK", value: "0-2s" },
                        { rank: "2", label: "PROOF", value: "2-8s" },
                        { rank: "3", label: "CLOSE", value: "8-12s" }] },
  PillCluster: { tags: ["FAST", "CHEAP", "GOOD", "NO WATERMARK"] },
  Reticle: { label: "REC" },
  StatCard: { value: 20000000, label: "NET NEW USERS", prefix: "$" },
  LowerThird: { name: "ALEX RIVERA", title: "FOUNDER, PROMPTLY" },
  PlainText: { text: "One bold line over the picture" },
  CaptionMatch: { text: "a line styled like the captions" },
  QuoteCard: { quote: "The gap is the story.", attribution: "Alex Rivera" },
  TornPaper: { topText: "BEFORE", bottomText: "AFTER" },
  EmojiCard: { emoji: "\u{1F92F}", caption: "a reaction beat" },
  Stamp: { text: "SOLD OUT" },
};
const TARGETS = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FILL);

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.ts") });
const PLATE = [0x80, 0x80, 0x80], TOL = 10;
// MERGE, DO NOT OVERWRITE. A partial re-run wrote a file containing only the
// components it re-measured, and the three from the first pass survived only
// in console scrollback. Transcribing a number out of scrollback into a record
// is how a stale identifier becomes a fact — re-measure or merge, never retype.
const OUTPATH = path.join(ROOT, "..", "..", "measured", "NATURAL_BOXES_2026-09-23.json");
let results = {};
try { results = JSON.parse(fs.readFileSync(OUTPATH, "utf8")); } catch (e) { results = {}; }
for (const TYPE of TARGETS) {
  const entry = reg[TYPE];
  const props = {};
  if (entry) for (const p of entry.properties) props[p.key] = p.defaultValue;
  Object.assign(props, FILL[TYPE] || {});
  let composition;
  try {
    composition = await selectComposition({ serveUrl, id: "MGCraftProbe",
      inputProps: { type: TYPE, props, motionBlur: false } });
  } catch (e) { results[TYPE] = { error: String(e).slice(0, 120) }; continue; }
  const rows = [];
  for (let frame = 0; frame <= LAST; frame += STEP) {
    const png = path.join(outDir, `_m.png`), raw = path.join(outDir, `_m.rgb`);
    try {
      await renderStill({ composition, serveUrl, output: png, frame,
        inputProps: { type: TYPE, props, motionBlur: false }, chromiumOptions: { gl: "angle" } });
    } catch (e) { rows.push({ frame, error: String(e).slice(0, 80) }); continue; }
    execFileSync("ffmpeg", ["-nostdin","-loglevel","error","-y","-i",png,"-f","rawvideo","-pix_fmt","rgb24",raw]);
    const buf = fs.readFileSync(raw), W = composition.width, H = composition.height;
    let x0=W,y0=H,x1=-1,y1=-1,n=0;
    for (let y=0;y<H;y+=1) for (let x=0;x<W;x+=1) {
      const i=(y*W+x)*3;
      if (Math.abs(buf[i]-PLATE[0])>TOL||Math.abs(buf[i+1]-PLATE[1])>TOL||Math.abs(buf[i+2]-PLATE[2])>TOL) {
        n+=1; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y;
      }
    }
    rows.push(n===0?{frame,empty:true}:{frame,x0,y0,x1,y1,w:x1-x0+1,h:y1-y0+1,px:n});
    fs.unlinkSync(png); fs.unlinkSync(raw);
  }
  const drawn = rows.filter(r=>!r.empty && !r.error);
  if (!drawn.length) { results[TYPE] = { error: "NOTHING DREW ON ANY FRAME" }; console.log(`${TYPE}: NOTHING DREW`); continue; }
  const U = { x0: Math.min(...drawn.map(r=>r.x0)), y0: Math.min(...drawn.map(r=>r.y0)),
              x1: Math.max(...drawn.map(r=>r.x1)), y1: Math.max(...drawn.map(r=>r.y1)) };
  U.w = U.x1-U.x0+1; U.h = U.y1-U.y0+1;
  const peak = drawn.reduce((a,r)=>(r.w*r.h>a.w*a.h?r:a),drawn[0]);
  results[TYPE] = { canvas:[composition.width,composition.height], union:U, peak_single_frame:peak,
                    frames_drawn: drawn.length, frames_total: rows.length, per_frame: rows };
  console.log(`${TYPE.padEnd(14)} ${String(U.w).padStart(4)}x${String(U.h).padStart(4)} at (${U.x0},${U.y0})   peak f${peak.frame} ${peak.w}x${peak.h}   drawn ${drawn.length}/${rows.length}`);
}
fs.writeFileSync(OUTPATH, JSON.stringify(results, null, 1));
console.log("\nwrote measured/NATURAL_BOXES_2026-09-23.json");
