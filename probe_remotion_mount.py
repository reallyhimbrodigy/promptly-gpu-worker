"""PROBE — does the REAL component catalogue render standalone in a container?

Zac's scope, exactly: mount src/remotion with ITS OWN package.json at 4.0.450,
render a probe composition standalone, report yes/no WITH THE ACTUAL ERROR if no.
Then per-segment hybrid cost against the 59s ffmpeg-only baseline.

WHY ITS OWN package.json AND NOT THE AGENT IMAGE'S: two independent mismatches,
either of which makes a working component look broken.
    agentic image : remotion 4.0.517, react 19.0.0
    src/remotion  : remotion 4.0.450, react 18.3.1   <- what they were written against
A react MAJOR difference is not a version nit; 19 changed ref/JSX behaviour that
component code relies on. Diagnosing "the catalogue is broken" from a runtime the
catalogue never targeted would be a wasted session and a wrong conclusion.

WHICH COMPOSITION: FrameCompProbe and MGCraftProbe carry defaultProps, so they
render with no external input. PromptlyOverlay / PromptlyMicroSegments take
plan-shaped props that handler.py assembles (calculateOverlayMetadata +
DEFAULT_RENDER_INPUT) and are NOT the honest standalone test.
"""
import os
import time

import modal

app = modal.App("probe-remotion-mount")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REMOTION_SRC = os.path.abspath(os.path.join(_HERE, "..", "..", "src", "remotion"))

IMG = (modal.Image.debian_slim(python_version="3.11")
       .apt_install(
           "ffmpeg", "curl", "ca-certificates",
           "libnss3", "libdbus-1-3", "libatk1.0-0", "libasound2", "libxrandr2",
           "libxkbcommon0", "libxfixes3", "libxcomposite1", "libxdamage1",
           "libgbm1", "libpango-1.0-0", "libcairo2", "libatk-bridge2.0-0",
           "libcups2", "libxext6", "libx11-6", "libglib2.0-0")
       .run_commands(
           "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
           "apt-get install -y nodejs")
       # THE MOUNT. copy=True so npm install can run at BUILD time against the
       # real package.json rather than inside the measured render.
       .add_local_dir(_REMOTION_SRC, "/promptly-remotion", copy=True,
                      ignore=["node_modules", "*-out", ".git"])
       .run_commands(
           "cd /promptly-remotion && npm install --no-audit --no-fund",
           "cd /promptly-remotion && npx remotion browser ensure")
       .pip_install(["boto3"]))

SECRETS = [modal.Secret.from_name("promptly-secrets")]


@app.function(image=IMG, secrets=SECRETS, timeout=3600, cpu=8, memory=16384)
def probe(comps: str = "FrameCompProbe,MGCraftProbe", frames: int = 60,
          props_json: str = "") -> dict:
    import json
    import subprocess

    out = {"versions": {}, "renders": [], "ok": False}

    # What ACTUALLY installed -- pins in a package.json are an intention, and the
    # whole point of this probe is not to infer the runtime.
    for pkg in ("remotion", "react"):
        p = subprocess.run(
            f"node -p \"require('/promptly-remotion/node_modules/{pkg}/package.json').version\"",
            shell=True, capture_output=True, text=True, timeout=120)
        out["versions"][pkg] = (p.stdout or p.stderr).strip()[:40]

    p = subprocess.run("cd /promptly-remotion && npx remotion compositions 2>&1",
                       shell=True, capture_output=True, text=True, timeout=900)
    out["compositions_listed"] = (p.stdout or "")[-1500:]
    out["compositions_rc"] = p.returncode

    for comp in [c.strip() for c in comps.split(",") if c.strip()]:
        dst = f"/tmp/{comp}.mp4"
        t0 = time.time()
        # --frames bounds the render so cost is a MEASUREMENT, not a surprise.
        _pf = ""
        if props_json:
            # Write props to a FILE: a --props='{...}' inline JSON is what an
            # agent would try, and shell quoting is a plausible failure all by
            # itself. Isolate the PROP SHAPE question from the quoting question.
            with open("/tmp/props.json", "w") as _fh:
                _fh.write(props_json)
            _pf = " --props=/tmp/props.json"
        cmd = (f"cd /promptly-remotion && npx remotion render {comp} {dst} "
               f"--frames=0-{max(0, frames - 1)}{_pf} --log=verbose 2>&1")
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=2400)
        wall = round(time.time() - t0, 1)
        ok = r.returncode == 0 and os.path.exists(dst) and os.path.getsize(dst) > 1000
        rec = {"composition": comp, "rc": r.returncode, "wall_s": wall,
               "rendered": ok, "frames": frames}
        if ok:
            rec["bytes"] = os.path.getsize(dst)
            rec["ms_per_frame"] = round(wall * 1000.0 / max(frames, 1), 1)
            pr = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries",
                 "stream=width,height,codec_name", "-of", "json", dst],
                capture_output=True, text=True, timeout=120)
            try:
                rec["probe"] = json.loads(pr.stdout)["streams"][0]
            except Exception:
                rec["probe"] = None
        else:
            # THE ACTUAL ERROR, per Zac -- not "it failed".
            rec["error_tail"] = (r.stdout or r.stderr or "")[-2500:]
        out["renders"].append(rec)

    out["ok"] = any(x["rendered"] for x in out["renders"])
    return out


@app.local_entrypoint()
def main(comps: str = "FrameCompProbe,MGCraftProbe", frames: int = 60,
         props_json: str = ""):
    r = probe.remote(comps, frames, props_json)
    print("\n" + "=" * 68)
    print("  REMOTION MOUNT PROBE — real catalogue, its own package.json")
    print("=" * 68)
    print(f"  installed remotion : {r['versions'].get('remotion')}")
    print(f"  installed react    : {r['versions'].get('react')}")
    print(f"  `remotion compositions` rc={r.get('compositions_rc')}")
    for rec in r["renders"]:
        print(f"\n  --- {rec['composition']} ---")
        if rec["rendered"]:
            pb = rec.get("probe") or {}
            print(f"    RENDERED YES  {rec['frames']} frames in {rec['wall_s']}s "
                  f"= {rec['ms_per_frame']} ms/frame")
            print(f"    {pb.get('width')}x{pb.get('height')} {pb.get('codec_name')} "
                  f"{rec.get('bytes',0)/1e6:.2f}MB")
            # The number that decides the hybrid.
            for secs in (3, 5):
                cost_s = rec["ms_per_frame"] * 30 * secs / 1000.0
                print(f"    -> {secs}s of component at 30fps = {cost_s:.0f}s of paint")
        else:
            print(f"    RENDERED NO   rc={rec['rc']} after {rec['wall_s']}s")
            print("    ACTUAL ERROR:")
            for ln in (rec.get("error_tail") or "").strip().split("\n")[-30:]:
                print(f"      {ln[:150]}")
    print(f"\n  VERDICT: {'components render standalone from the mount' if r['ok'] else 'NO component rendered — see error above'}")
