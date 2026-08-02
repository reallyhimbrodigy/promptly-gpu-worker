// SURVIVING-LAYER PROOF (Zac 2026-08-02). A crossfade with one unloadable image
// layer must still paint REAL frames — the survivor holds the window as a cut.
// A naive drop would leave clipB at opacity 0 across the head (or clipA at the
// tail): black, the exact INTEGRITY_TRIP shape. PASS = no black frames.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R=path.dirname(fileURLToPath(import.meta.url));
const out=path.join(R,"velocity-cap-out","crossfade"); fs.mkdirSync(out,{recursive:true});
const DEAD="https://127.0.0.1:9/dead-layer.png";      // .png so isImage() routes it to SafeImg
const ARMS=[["both_ok","vcap_A.png","vcap_B.png"],["A_dead",DEAD,"vcap_B.png"],["B_dead","vcap_A.png",DEAD]];
const b=await bundle({entryPoint:path.join(R,"src","index.ts"),onProgress:()=>{}});
for(const [name,clipA,clipB] of ARMS){
  const inputProps={clipA,clipB};
  const c=await selectComposition({serveUrl:b,id:"CrossfadeProbe",inputProps});
  await renderMedia({composition:c,serveUrl:b,outputLocation:path.join(out,`${name}.mp4`),
    codec:"h264",inputProps,scale:0.25,logLevel:"error",concurrency:1});
  console.log(`rendered ${name}`);
}
console.log("OUT",out);
