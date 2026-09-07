"""In-container caption paint cost — the number that decides the caption port.

Captions are alpha overlays like the cards, so they CAN composite over ffmpeg
output. The question is what they cost, and captions differ from every other
family in one way that matters: a card covers a 2-second window, captions cover
the WHOLE video. talking_head is 38.5s = 1155 frames.

Local measurement: 63-72 ms/frame across all nine styles. But local was 4.4x
optimistic for SmoothPush (64 vs 282 in-container), and that factor was measured
on a component compositing VIDEO — captions paint over transparency with no
decode, so the factor may not transfer. Extrapolating would be inventing a
number, so this measures it.

REUSES THE AGENTIC IMAGE. The last probe defined its own and paid a full apt+npm
build that the price did not include; this imports IMG, which already has
/promptly-remotion installed and browser-ensured and is cached from every round.

  modal run --detach measure_caption_cost_app.py
"""
import json, os, subprocess, time
import modal
from agentic_editor_app import IMG as _BASE

_AGENTIC_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "agentic_editor_app.py")
# Modal imports the defining module IN the container to locate the function, so
# `from agentic_editor_app import IMG` must resolve there too. It did not, and
# the first run died on ModuleNotFoundError before painting a frame. Mounting
# the module is one cheap layer on the already-cached image; hand-copying its
# 80-line spec would risk a cache miss and a full rebuild — the cost mistake
# from the previous probe.
IMG = _BASE.add_local_file(_AGENTIC_SRC, "/root/agentic_editor_app.py", copy=True)

# MOUNTED, NOT READ AT IMPORT. The first version read these three files with
# paths relative to this module — which the container also executes, where those
# paths do not exist. It died on FileNotFoundError before painting a frame, the
# second infrastructure failure in a row that cost a run without producing a
# number. Mount them; the container reads from a fixed path.
_RSRC = "/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion"
IMG = IMG.add_local_file(os.path.join(_RSRC, "src", "CaptionCostProbe.tsx"),
                         "/probe/CaptionCostProbe.tsx", copy=True)
IMG = IMG.add_local_file(os.path.join(_RSRC, "caption-cost-index.ts"),
                         "/probe/caption-cost-index.ts", copy=True)
IMG = IMG.add_local_file(os.path.join(_RSRC, "caption-cost.mjs"),
                         "/probe/caption-cost.mjs", copy=True)
app = modal.App("caption-cost-probe", image=IMG)


@app.function(timeout=1800, cpu=8, memory=16384)
def probe():
    t0 = time.time()
    R = "/promptly-remotion"
    import shutil
    shutil.copy("/probe/CaptionCostProbe.tsx", f"{R}/src/CaptionCostProbe.tsx")
    shutil.copy("/probe/caption-cost-index.ts", f"{R}/caption-cost-index.ts")
    src = open("/probe/caption-cost.mjs").read().replace(
        '"/Users/zaclibman/promptly-gpu-worker/promptly-gpu-worker/src/remotion"',
        '"/promptly-remotion"').replace("/tmp/zoomab/", "/tmp/")
    with open(f"{R}/caption-cost.mjs", "w") as fh:
        fh.write(src)
    r = subprocess.run(["node", "caption-cost.mjs"], cwd=R,
                       capture_output=True, text=True, timeout=1500)
    out = (r.stdout or "") + (r.stderr or "")
    for line in out.splitlines():
        if "ms/frame" in line or "style " in line:
            print(line, flush=True)
    if r.returncode != 0:
        print("PROBE FAILED:", out[-1500:], flush=True)
    print(f"\n  probe wall {time.time()-t0:.1f}s", flush=True)
    print(f"  local reference: 63-72 ms/frame across all nine styles", flush=True)
    print(f"  cards in-container: 188 ms/frame   SmoothPush: 282 ms/frame", flush=True)
    return {"ok": r.returncode == 0}


@app.local_entrypoint()
def main():
    probe.remote()
