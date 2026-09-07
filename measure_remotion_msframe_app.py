"""In-container Remotion cost: is it 840 ms/frame, or 64, or neither?

THE DISCREPANCY. agentic_editor_app's header — the entire argument for the
ffmpeg path — says Remotion paints 840-1796 ms/frame in headless Chromium
(SmoothPush 840, StepZoom 785, LetterboxPush 1796). Rendering the SAME
component, same props, same frame count, concurrency 1, on an M-series Mac
measured 64 ms/frame. 13x.

BOTH CAN BE TRUE, and that is the hypothesis this run is built to separate.
A figure of (total wall)/(frames) folds three different costs together:

    bundle        webpack over the whole catalogue — ONE-OFF per process
    browser       headless Chromium launch          — ONE-OFF per process
    paint         the actual per-frame cost         — the only part that scales

Over few frames the one-offs dominate and the blended number looks enormous;
over many they vanish. build_reel took 48.3s for 4 cards, and if paint is really
~64ms then ~60 frames is 3.8s of painting and ~44s of startup — which is a
COMPLETELY different problem from per-frame cost, and one that batching already
knows how to fix.

So this reports the three separately and never as a single blended figure.
Same composition, same props, same concurrency as the local run, so the two
numbers are comparable rather than merely both true.

  modal run --detach measure_remotion_msframe_app.py
"""
import json, os, subprocess, time
import modal

_HERE = os.path.dirname(os.path.abspath(__file__))
_REMOTION_SRC = os.path.abspath(os.path.join(_HERE, "..", "..", "src", "remotion"))

IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install("ffmpeg", "nodejs", "npm", "libnss3", "libatk1.0-0",
                    "libatk-bridge2.0-0", "libcups2", "libdrm2", "libxkbcommon0",
                    "libxcomposite1", "libxdamage1", "libxfixes3", "libxrandr2",
                    "libgbm1", "libasound2", "libpango-1.0-0", "libcairo2")
       .add_local_dir(_REMOTION_SRC, "/promptly-remotion", copy=True,
                      ignore=["node_modules", "*-out", ".git"])
       .run_commands(
           "cd /promptly-remotion && npm install --no-audit --no-fund",
           "cd /promptly-remotion && npx remotion browser ensure"))

app = modal.App("remotion-msframe-probe", image=IMG)

SCRIPT = r"""
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";
const R = "/promptly-remotion";
const t0 = Date.now();
const serveUrl = await bundle({ entryPoint: path.join(R, "src", "index.ts"), onProgress: () => {} });
const tBundle = Date.now() - t0;

const inputProps = {
  events: [{ startMs: 1000, durationMs: 2000, scale: 1.12, originX: 0.5, originY: 0.5 }],
  smoothGraphics: false, punch: false, src: "msframe_pattern.mp4",
};
const t1 = Date.now();
const c = await selectComposition({ serveUrl, id: "SmoothPushProbe30", inputProps });
const tSelect = Date.now() - t1;

// TWO FRAME COUNTS on ONE process. The difference between them isolates paint
// from the per-process one-offs: (wall_long - wall_short) / (n_long - n_short)
// is the marginal cost of a frame, with bundle and browser launch cancelled out.
const runs = [];
for (const n of [30, 120]) {
  const t = Date.now();
  await renderMedia({
    composition: { ...c, durationInFrames: n }, serveUrl,
    outputLocation: `/tmp/out_${n}.mp4`, codec: "h264",
    inputProps, logLevel: "error", concurrency: 1,
  });
  runs.push({ frames: n, wall_ms: Date.now() - t });
}
const [a, b] = runs;
const marginal = (b.wall_ms - a.wall_ms) / (b.frames - a.frames);
console.log("RESULT " + JSON.stringify({
  bundle_ms: tBundle, select_ms: tSelect, runs,
  blended_ms_per_frame_short: a.wall_ms / a.frames,
  blended_ms_per_frame_long: b.wall_ms / b.frames,
  marginal_ms_per_frame: marginal,
  per_process_overhead_ms: a.wall_ms - marginal * a.frames,
}));
"""

@app.function(timeout=1800, cpu=8, memory=16384)
def probe():
    t_start = time.time()
    # The SAME constructed pattern the local run used, generated identically.
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "color=c=#080808:s=1080x1920:d=3:r=30",
         "-vf", "drawgrid=w=60:h=60:t=1:c=#282828,"
                "drawbox=x=261:y=471:w=18:h=18:c=white:t=fill,"
                "drawbox=x=801:y=471:w=18:h=18:c=white:t=fill,"
                "drawbox=x=261:y=1431:w=18:h=18:c=white:t=fill,"
                "drawbox=x=801:y=1431:w=18:h=18:c=white:t=fill",
         "-pix_fmt", "yuv420p", "-c:v", "libx264", "-crf", "12",
         "/promptly-remotion/public/msframe_pattern.mp4"],
        check=True, capture_output=True)
    with open("/promptly-remotion/probe.mjs", "w") as fh:
        fh.write(SCRIPT)
    r = subprocess.run(["node", "probe.mjs"], cwd="/promptly-remotion",
                       capture_output=True, text=True, timeout=1500)
    out = (r.stdout or "") + (r.stderr or "")
    line = next((l for l in out.splitlines() if l.startswith("RESULT ")), None)
    if not line:
        print("PROBE FAILED — no RESULT line")
        print(out[-2500:])
        return {"ok": False}
    d = json.loads(line[len("RESULT "):])
    print("\n=== IN-CONTAINER REMOTION COST (SmoothPushProbe30, 1080x1920, concurrency 1) ===")
    print(f"  bundle (one-off)          : {d['bundle_ms']/1000:7.2f}s")
    print(f"  selectComposition         : {d['select_ms']/1000:7.2f}s")
    for run in d["runs"]:
        print(f"  render {run['frames']:>3} frames        : {run['wall_ms']/1000:7.2f}s"
              f"   ({run['wall_ms']/run['frames']:6.1f} ms/frame blended)")
    print(f"\n  MARGINAL ms/frame         : {d['marginal_ms_per_frame']:7.1f}   <- the only figure that scales")
    print(f"  per-process overhead      : {d['per_process_overhead_ms']/1000:7.2f}s   <- paid once, not per frame")
    print(f"\n  header claims SmoothPush  :   840.0 ms/frame")
    print(f"  local (M-series Mac)      :    64.0 ms/frame")
    print(f"  probe wall                : {time.time()-t_start:7.1f}s")
    return d

@app.local_entrypoint()
def main():
    probe.remote()
