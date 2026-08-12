"""GPU FRAME-DRAW TEST (Zac GO 2026-08-02, ~$0.50): the render is frame-draw bound
at ~1fps (swangle software ANGLE). Does a GPU + --gl=angle-egl accelerate OUR
components (MG shadows/gradients/blurs, caption fonts)? Render the SAME probe
single-stream (concurrency=1 — single-stream draw speed is the axis that matters
at 1fps) on L4 and T4 (angle-egl) vs CPU (swangle). Report overall_fps + the
slowest (warmup) frame + peak memory (the ANGLE long-render leak caveat).

  modal run cert_gpu_fps.py"""
import sys
sys.path.insert(0, "/")   # so the container can import modal_app from /modal_app.py
import modal, modal_app
# add_local_file is an add_local step (not a build step) so it may follow
# modal_app.image's own add_local layers — the container re-imports THIS module,
# which imports modal_app, so modal_app.py must be present in the container.
image = modal_app.image.add_local_file("modal_app.py", "/modal_app.py")
app = modal.App("cert-gpu-fps", image=image)
# NVIDIA_DRIVER_CAPABILITIES MUST be present at container LAUNCH (the NVIDIA runtime
# reads it to decide which GPU libs to mount — graphics/display/EGL, not just
# compute/video). Can't add an image build-step after modal_app.image's
# add_local_* layers, so inject it as a Secret (container env at creation time).
# Without graphics caps, angle-egl has no EGL context and Chromium hangs.
GPU_CAPS = modal.Secret.from_dict({"NVIDIA_DRIVER_CAPABILITIES": "all"})

# Node probe: render one composition from the PRE-BUILT /remotion/bundle at
# concurrency=1 with a chosen gl backend; emit overall fps + slowest frames.
PROBE_JS = r'''
import { selectComposition, renderMedia } from "@remotion/renderer";
const serveUrl = "/remotion/bundle";
const composition = process.argv[2];
const gl = process.argv[3];
const frameCap = process.argv[4] ? parseInt(process.argv[4], 10) : null;  // preflight: render only N frames
const t0 = Date.now();
const comp = await selectComposition({ serveUrl, id: composition });
const nFrames = frameCap ? Math.min(frameCap, comp.durationInFrames) : comp.durationInFrames;
const result = await renderMedia({
  serveUrl, composition: comp, codec: "h264",
  outputLocation: `/tmp/out_${gl}.mp4`,
  browserExecutable: "/usr/local/bin/chrome-headless-shell",  // the build-time Chromium (top-level, not chromiumOptions)
  chromiumOptions: { gl, enableMultiProcessOnLinux: true },
  concurrency: 1,
  logLevel: "error",
  ...(frameCap ? { frameRange: [0, nFrames - 1] } : {}),
});
const elapsed = (Date.now() - t0) / 1000;
const sf = (result.slowestFrames || []).slice(0, 3).map(f => ({frame: f.frame, ms: Math.round(f.time)}));
console.log("PROBE_RESULT " + JSON.stringify({
  composition, gl, frames: nFrames, elapsed_s: +elapsed.toFixed(1),
  overall_fps: +(nFrames / elapsed).toFixed(2), slowest3: sf,
}));
'''

def _run(gl, composition):
    import subprocess, os, threading, json
    # PREFLIGHT: can Chromium even init this gl backend? Render EGLProbe (a trivial
    # 2-frame composition) with a HARD 75s cap. If angle-egl can't get a context it
    # hangs — the cap turns that into a fast, cheap "not viable headless" answer
    # instead of a 30-minute GPU bill.
    # `import "@remotion/renderer"` resolves node_modules from the FILE's dir, so
    # the probe must sit somewhere with /remotion/node_modules reachable. Prefer
    # /remotion (writable overlay); fall back to /tmp + a node_modules symlink if
    # /remotion is a read-only mount.
    probe_path = "/remotion/probe.mjs"
    try:
        with open(probe_path, "w") as f:
            f.write(PROBE_JS)
    except OSError:
        if not os.path.exists("/tmp/node_modules"):
            os.symlink("/remotion/node_modules", "/tmp/node_modules")
        probe_path = "/tmp/probe.mjs"
        with open(probe_path, "w") as f:
            f.write(PROBE_JS)
    out = {"gl": gl, "composition": composition}
    try:
        pf = subprocess.run(["node", probe_path, "MGAttackProbe", gl, "2"],
                            capture_output=True, text=True, cwd="/remotion", timeout=75)
    except subprocess.TimeoutExpired:
        out["error"] = f"PREFLIGHT HANG: {gl} could not init a GL context in 75s (headless EGL/display missing)"
        return out
    if not any(l.startswith("PROBE_RESULT ") for l in (pf.stdout or "").splitlines()):
        out["error"] = f"PREFLIGHT FAIL ({gl}): " + (pf.stderr or "")[-500:]
        return out
    # Real timed run (full frame count), hard 200s cap so a mid-run stall can't bill forever.
    peak = [0]; stop = threading.Event()
    def samp():
        while not stop.wait(0.5):
            try:
                with open("/sys/fs/cgroup/memory.current") as fh:
                    m = int(fh.read().strip())
                if m > peak[0]:
                    peak[0] = m
            except Exception:
                pass
    th = threading.Thread(target=samp, daemon=True); th.start()
    try:
        r = subprocess.run(["node", probe_path, composition, gl],
                           capture_output=True, text=True, cwd="/remotion", timeout=200)
    except subprocess.TimeoutExpired:
        stop.set()
        out["error"] = f"RUN TIMEOUT: {gl} stalled >200s (peak_mem={round(peak[0]/1024/1024)}MB)"
        return out
    stop.set()
    out["peak_mem_mb"] = round(peak[0] / 1024 / 1024)
    line = next((l for l in (r.stdout or "").splitlines() if l.startswith("PROBE_RESULT ")), None)
    if line:
        out.update(json.loads(line[len("PROBE_RESULT "):]))
    else:
        out["error"] = (r.stderr or "")[-800:]
    return out


@app.function(gpu="L4", timeout=900, secrets=[GPU_CAPS])
def l4(comp):
    return _run("angle-egl", comp)


@app.function(gpu="T4", timeout=900, secrets=[GPU_CAPS])
def t4(comp):
    return _run("angle-egl", comp)


@app.function(cpu=4, timeout=900)
def cpu(comp):
    return _run("swangle", comp)


@app.local_entrypoint()
def main():
    COMP = "MGAttackProbe"   # StatCard MG: shadows/gradients — the advisor's flagged GPU-accelerable CSS
    print(f"=== GPU frame-draw test: {COMP}, single-stream, angle-egl(L4/T4) vs swangle(CPU) ===")
    fL4 = l4.spawn(COMP); fT4 = t4.spawn(COMP); fCPU = cpu.spawn(COMP)
    rows = [("CPU swangle", fCPU.get()), ("L4 angle-egl", fL4.get()), ("T4 angle-egl", fT4.get())]
    print(f"\n  {'config':>14} {'fps':>7} {'elapsed':>9} {'slowest_ms':>11} {'peak_mem':>9}")
    base = None
    for name, r in rows:
        if r.get("error"):
            print(f"  {name:>14}  ERROR: {r['error'][:120]}"); continue
        fps = r.get("overall_fps"); sl = (r.get("slowest3") or [{}])[0].get("ms", "?")
        if base is None: base = fps
        spd = f"{fps/base:.1f}x" if base else ""
        print(f"  {name:>14} {fps:>7} {r.get('elapsed_s'):>8}s {sl:>9}ms {r.get('peak_mem_mb'):>7}MB   {spd} vs CPU")
    print("\n→ GPU/CPU fps ratio = whether OUR draw is GPU-accelerable. Slowest_ms = does the warmup frame shrink too?")
