// MICRO SEEK-COST TEST (Zac 2026-08-02) — does seeking into a long source cost
// anything? Four arms: seek into 60s, a pre-extracted 2s span, two read heads
// 50s apart, two adjacent. RESULT: all within 2% (108.2-110.3 ms/frame), so
// pre-extraction buys ~1% and seek distance is NOT the micro cost.
//   node src/remotion/micro-seek-cost.mjs
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(R,"velocity-cap-out","seek"); fs.mkdirSync(out,{recursive:true});
const b=await bundle({entryPoint:path.join(R,"src","index.ts"),onProgress:()=>{}});
// SEEK arm: the production shape — full 60s source, both layers seeking to ~50s.
// PRE-EXTRACT arm: the proposed shape — a 2s span already cut, startFrom 0.
const ARMS=[
 ["seek_into_60s","seek_long.mp4",1500,1500],
 ["preextracted_2s","seek_short.mp4",0,0],
 // TWO DISTANT READ HEADS in one render — 0s and 50s apart in the same file.
 // This is the production shape a single-span test cannot reproduce: several
 // transitions scattered through one source, competing for the same cache.
 ["two_heads_50s_apart","seek_long.mp4",0,1500],
 ["two_heads_adjacent","seek_long.mp4",1500,1502],
];
for(const [name,src,sa,sb] of ARMS){
  const inputProps={clipA:src,clipB:src,startFromA:sa,startFromB:sb};
  const c=await selectComposition({serveUrl:b,id:"CrossfadeProbe",inputProps});
  const t=Date.now();
  const res=await renderMedia({composition:c,serveUrl:b,
    outputLocation:path.join(out,`${name}.mp4`),codec:"h264",inputProps,
    logLevel:"error",concurrency:1});
  const ms=Date.now()-t;
  const sf=(res.slowestFrames||[]).filter(f=>f.frame!==0);
  const worst=sf.length?sf[0].time:NaN;
  console.log(`${name.padEnd(18)} wall=${(ms/1000).toFixed(2)}s  ms/frame=${(ms/c.durationInFrames).toFixed(1)}  worstPaint=${worst}ms`);
}
