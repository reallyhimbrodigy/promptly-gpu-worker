import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path"; import fs from "node:fs";
import { fileURLToPath } from "node:url";
const R=path.dirname(fileURLToPath(import.meta.url));
const arm=process.argv[2]||"old";
const out=path.join(R,"velocity-cap-out","cfz"); fs.mkdirSync(out,{recursive:true});
const b=await bundle({entryPoint:path.join(R,"src","index.ts"),onProgress:()=>{}});
// NON-ZERO, UNEQUAL seeks — the whole point. If trimBefore were ignored the two
// layers would show the same frames and the diff would be enormous.
const A=Number(process.argv[3]??1500), B=Number(process.argv[4]??300);
const SA=process.argv[5]||"seek_long.mp4", SB=process.argv[6]||"seek_long.mp4";
const inputProps={clipA:SA,clipB:SB,startFromA:A,startFromB:B};
const c=await selectComposition({serveUrl:b,id:"CrossfadeProbe",inputProps});
const t=Date.now();
await renderMedia({composition:c,serveUrl:b,inputProps,codec:"h264",
  outputLocation:path.join(out,`cfz_${arm}.mp4`),logLevel:"error",concurrency:1});
console.log(`${arm} A=${A} B=${B} srcs=${SA}/${SB} wall=${((Date.now()-t)/1000).toFixed(2)}s ms/frame=${((Date.now()-t)/c.durationInFrames).toFixed(1)}`);
