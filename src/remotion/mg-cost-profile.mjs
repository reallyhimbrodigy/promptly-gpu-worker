// FRAME-DRAW COST PER MOTION GRAPHIC (Zac 2026-08-02).
// Same probe, same frame count, same machine — only the COMPONENT differs. So a
// difference in frame time is the component's paint cost and nothing else.
// Pairs high-expensive-CSS components against low ones to test Remotion's claim
// that box-shadow / text-shadow / gradients / filter are slow without a GPU.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(R, "velocity-cap-out", "profile"); fs.mkdirSync(out, { recursive: true });
// [type, props, expensive-CSS count from the audit]
const CASES = [
  ["TimelineRoadmap", { items: [{label:"Phase 1"},{label:"Phase 2"},{label:"Phase 3"}], anchor:"center" }, 13],
  ["Reticle",         { anchor: "center" }, 11],
  ["Notification",    { notifications:[{app:"venmo",appName:"Venmo",title:"Sarah paid you",body:"$200.00"}], anchor:"center" }, 10],
  ["PullQuote",       { text:"this changed everything", anchor:"center" }, 7],
  ["DropBanner",      { text:"NEW DROP", anchor:"center" }, 1],
  ["ChatThread",      { messages:[{sender:"them",text:"you up?"},{sender:"me",text:"always"}], anchor:"center" }, 1],
];
const b = await bundle({ entryPoint: path.join(R,"src","index.ts"), onProgress: () => {} });
const rows = [];
for (const [type, props, css] of CASES) {
  const inputProps = { type, props };
  const c = await selectComposition({ serveUrl: b, id: "MGAttackProbe", inputProps });
  const t0 = Date.now();
  const res = await renderMedia({
    composition: c, serveUrl: b, outputLocation: path.join(out, `${type}.mp4`),
    codec: "h264", inputProps, logLevel: "error", concurrency: 1,
  });
  const wall = Date.now() - t0;
  const sf = (res && res.slowestFrames) || [];
  // frame 0 is BROWSER WARM-UP (measured 556ms vs 51ms for frame 1), not paint
  // cost — excluded, or it swamps the very comparison being made.
  const paint = sf.filter(f => f.frame !== 0);
  const slow = paint.slice(0, 5).map(f => `f${f.frame}:${f.time}ms`).join(" ");
  const worst = paint.length ? paint[0].time : NaN;
  const medSlow = paint.length ? paint[Math.floor(paint.length / 2)].time : NaN;
  const warm = (sf.find(f => f.frame === 0) || {}).time;
  rows.push({ type, css, wall, worst, medSlow, slow, n: c.durationInFrames });
  console.log(`${type.padEnd(17)} css=${String(css).padStart(2)} wall=${(wall/1000).toFixed(1)}s `
    + `warmup(f0)=${warm}ms worstPaint=${worst}ms  top5: ${slow}`);
}
console.log("\n=== SORTED BY WORST FRAME ===");
rows.sort((a,b2)=>b2.worst-a.worst);
console.log("component        expensiveCSS  worstFrame  medianOfSlowest10  wall");
for (const r of rows) console.log(
  `${r.type.padEnd(17)}${String(r.css).padStart(8)}${r.worst.toFixed(0).padStart(12)}ms`
  + `${r.medSlow.toFixed(0).padStart(16)}ms${(r.wall/1000).toFixed(1).padStart(8)}s`);
