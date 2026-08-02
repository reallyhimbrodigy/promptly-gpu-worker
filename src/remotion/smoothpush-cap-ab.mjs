import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
const R="/Users/zaclibman/promptly-gpu-worker/promptly-smoothness/src/remotion";
const out=path.join(R,"velocity-cap-out","smoothpush"); fs.mkdirSync(out,{recursive:true});
const EVENTS=[{startMs:1600,durationMs:1200,scale:1.22,originX:0.5,originY:0.42}];
const b=await bundle({entryPoint:path.join(R,"src","index.ts"),onProgress:()=>{}});
for(const [name,smooth] of [["OFF",false],["OFF2",false],["CAP",true]]){
  const inputProps={events:EVENTS,smoothGraphics:smooth,src:"vcap_head.mp4",punch:false};
  const c=await selectComposition({serveUrl:b,id:"SmoothPushProbe30",inputProps});
  const t=Date.now();
  await renderMedia({composition:c,serveUrl:b,outputLocation:path.join(out,`${name}.mp4`),
    codec:"h264",inputProps,logLevel:"error",concurrency:1});
  console.log(`${name} ${( (Date.now()-t)/1000 ).toFixed(1)}s`);
}
console.log("OUT",out);
