// SAFE IMAGE LAW — the live proof (Zac 2026-08-02, job 1047def9).
// Renders a real MG with a DEAD image src. Chromium must log the load failure
// AND the render must still COMPLETE. Before SafeImg this hung on an open
// <Img> delayRender handle until the 30000ms timeout and returned rc=1,
// costing the user the whole video.
//   node src/remotion/safeimg-degrade-proof.mjs
// PASS = "Failed to load resource" in the log AND "RENDER COMPLETED".
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import { fileURLToPath } from "node:url";
const R=path.dirname(fileURLToPath(import.meta.url));
const b=await bundle({entryPoint:path.join(R,"src","index.ts"),onProgress:()=>{}});
// A DEAD image URL: unroutable host, will never resolve inside Chromium.
const props={type:"TweetBubble",props:{name:"Jane",handle:"jane",text:"proof",
  verified:true,avatarSrc:"https://127.0.0.1:9/nonexistent-avatar.png",
  stats:{replies:1,reposts:1,likes:1,views:1},anchor:"center"},smoothGraphics:false};
const c=await selectComposition({serveUrl:b,id:"MGAttackProbe",inputProps:props});
const t=Date.now();
await renderMedia({composition:c,serveUrl:b,outputLocation:path.join(R,"velocity-cap-out","safeimg_proof.mp4"),
  codec:"h264",inputProps:props,scale:0.3,logLevel:"error",concurrency:1});
console.log(`RENDER COMPLETED in ${((Date.now()-t)/1000).toFixed(1)}s with a DEAD image src`);
