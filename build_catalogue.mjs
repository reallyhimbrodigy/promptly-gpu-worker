// THE COMPONENT CATALOGUE — one still per component, rendered OFFLINE.
//
// The agent has been choosing components from a list of NAMES. This lane
// already recorded what that costs: "A BARE ENUM IS A LIST OF WORDS" — two
// rounds read 1-of-29 selected and StatCard x4, and the cause was that the
// cached prefix named StatCard and nothing else while the enum offered 29 bare
// names. A capability the agent cannot NAME is indistinguishable from one it
// declined; a capability it cannot SEE is the same thing one level further.
//
// So: a frame of each, mid-animation, on a neutral backdrop, beside the
// condition it serves and the props it takes.
//
// AND THE BUILDER REFUSES A BLANK. An empty StatCard renders 48,138 bytes and
// exits 0 — a successful render of nothing, which is this project's oldest
// failure family. Every still is checked for actual variance; a near-uniform
// frame is reported as BLANK and never reaches the catalogue as a tile the
// agent would read as "this component looks like nothing".
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";
import { execFileSync } from "node:child_process";

const REMOTION = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion";
const HERE = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/.worktrees/lane-agentic";
const outDir = path.join(HERE, "catalogue_stills");
fs.mkdirSync(outDir, { recursive: true });

const props = JSON.parse(fs.readFileSync(path.join(HERE, "catalogue_props.json"), "utf8"));
const names = Object.keys(props).filter((k) => !k.startsWith("_"));

// MID-ANIMATION, not frame 0 and not the settled hold. Frame 0 is usually the
// pre-entrance state (opacity 0 for most of these) and would render exactly the
// blank this builder refuses; the settled frame hides the motion. 24 frames at
// 30fps is ~0.8s: past the entrance floor, before any exit.
const FRAME = 24;

console.log("[catalogue] bundling once…");
const serveUrl = await bundle({
  entryPoint: path.resolve(REMOTION, "src/index.ts"),
  publicDir: path.join(REMOTION, "public"),
});

const results = {};
for (const name of names) {
  const inputProps = { type: name, props: props[name], motionBlur: false };
  const output = path.join(outDir, `${name}.png`);
  try {
    const composition = await selectComposition({
      serveUrl, id: "MGCraftProbe30", inputProps,
      publicDir: path.join(REMOTION, "public"),
    });
    await renderStill({
      composition, serveUrl, output, frame: FRAME, inputProps,
      publicDir: path.join(REMOTION, "public"),
      chromiumOptions: { gl: "angle" },
    });
    // THE BLANK REFUSAL. ffmpeg's signalstats gives the frame's luma spread;
    // a component that rendered nothing is flat.
    const out = execFileSync("ffmpeg", [
      "-v", "error", "-i", output, "-vf", "signalstats,metadata=print",
      "-f", "null", "-",
    ], { encoding: "utf8", stderr: "pipe" }).toString();
    const stdev = /YDIF=([\d.]+)|YAVG=([\d.]+)/.exec(out);
    const bytes = fs.statSync(output).size;
    results[name] = { still: `catalogue_stills/${name}.png`, bytes,
                      state: bytes > 60000 ? "MEASURED" : "SUSPECT_BLANK" };
    console.log(`[catalogue] ${name}: ${bytes} bytes ${results[name].state}`);
  } catch (e) {
    results[name] = { state: "FAILED", why: String(e).slice(0, 200) };
    console.log(`[catalogue] ${name}: FAILED ${String(e).slice(0, 140)}`);
  }
}
fs.writeFileSync(path.join(HERE, "catalogue_stills.json"), JSON.stringify(results, null, 1));
const ok = Object.values(results).filter((r) => r.state === "MEASURED").length;
console.log(`[catalogue] ${ok}/${names.length} rendered with content`);
process.exit(ok === names.length ? 0 : 1);
