"""PROBE: does caption paint scale with cores?

WHY. 94% of the render side is two Remotion renders, and caption paint alone
(~60s) is half the 120s law. concurrency is already 8 against cpu=8, and an
earlier probe found paint saturating at 4 painters — so more painters need more
cores, and cpu has never been tested.

WHY NOT THE FULL AGENT RUN. Token draw varies 1.7x on identical input, which
lands on wall and would swamp the signal. This renders ONE fixed caption
composition and nothing else, so the only thing that differs between arms is the
core count.

THE PLAN IS SYNTHETIC AND FIXED — 23 pages, 443 frames, Gadzhi @ 15fps, the
exact shape every talking_head run has produced. It does not depend on a
transcript, so it cannot drift between arms.

EVERY ARM PRINTS THE CONTAINER BENCHMARK. Identical bytes gave 49.0 and 134.2
ms/frame six hours apart; an arm without its machine measured is not comparable
to the arm beside it, even in the same sweep.

  ./run_modal.sh probe_cpu_sweep_app.py       (or: modal run probe_cpu_sweep_app.py)
"""
import json
import os
import time

import modal

from agentic_editor_app import (IMG, SECRETS, caption_overlay_plan,
                                caption_pages,
                                container_benchmark, render_remotion_batch,
                                _SUBPROCESS_ENV)

# THE PROBE'S OWN DEPENDENCY MUST BE IN THE IMAGE.
# agentic_editor_app is imported INSIDE the container (for caption_pages,
# caption_overlay_plan, render_remotion_batch and the benchmark), so it has to be
# mounted like any other module the image needs — the deferred-import/image-mount
# law. Without it the arm dies at import with ModuleNotFoundError.
# add_local_python_source, NOT add_local_file. The file-copy version put the
# module in the image and it still failed to import: Modal resolves local Python
# MODULES through this call, which is what puts it on the container's sys.path.
PROBE_IMG = IMG.add_local_python_source("agentic_editor_app")

app = modal.App("probe-cpu-sweep")

FRAMES = 443
FPS = 15
STYLE = "Gadzhi"
PAGES_N = 23


def _fixed_pages():
    """23 pages of 3 words, evenly spread over the 443-frame window.

    BUILT THROUGH caption_pages(), NOT HAND-ROLLED. The first version of this
    emitted page-level fromMs/toMs; the real shape is startMs/durationMs/text/
    tokens. Remotion would have rendered an empty caption layer and reported a
    fast, clean, meaningless ms/frame — a probe measuring nothing while looking
    like it measured something. Going through the producer means the shape
    cannot drift from it, today or when caption_pages next changes.
    """
    words, per_s = [], (FRAMES / FPS) / (PAGES_N * 3)
    for i in range(PAGES_N * 3):
        words.append({"s": i * per_s, "e": (i + 1) * per_s,
                      "w": ("THIS", "IS", "PAGE")[i % 3] + str(i // 3)})
    return caption_pages(words, 3)


def _one_arm(label):
    os.makedirs("/work", exist_ok=True)
    bench = container_benchmark()
    plan_path = "/work/probe-caption-plan.json"
    with open(plan_path, "w") as fh:
        json.dump(caption_overlay_plan(_fixed_pages(), STYLE, FRAMES, fps=FPS), fh)
    t0 = time.time()
    res = render_remotion_batch([{
        "id": "captions", "composition": "PromptlyOverlay",
        "propsFile": plan_path, "out": "/work/probe-captions.mov",
        "alpha": True,
    }], env=_SUBPROCESS_ENV)
    wall = time.time() - t0
    job = (res or {}).get("captions") or {}
    batch = (res or {}).get("_batch") or {}
    out = {
        "arm": label,
        "bench": bench,
        "ok": bool(job.get("ok")),
        "paint_ms": job.get("ms"),
        # MEASURED / ABSENT — never a confident zero from a failed render.
        "ms_per_frame": (round(job["ms"] / FRAMES, 1)
                         if job.get("ms") else None),
        "bundle_ms": batch.get("bundle_ms"),
        "bundle_cached": batch.get("bundle_cached"),
        "wall_s": round(wall, 1),
        "error": job.get("error"),
    }
    print(f"[{label}] {json.dumps(out)}", flush=True)
    return out


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=8, memory=16384)
def arm_cpu8():
    return _one_arm("cpu8")


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=16, memory=16384)
def arm_cpu16():
    return _one_arm("cpu16")


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=32, memory=16384)
def arm_cpu32():
    return _one_arm("cpu32")


@app.local_entrypoint()
def main():
    arms = [("cpu8", arm_cpu8), ("cpu16", arm_cpu16), ("cpu32", arm_cpu32)]
    rows = []
    for name, fn in arms:
        try:
            rows.append(fn.remote())
        except Exception as e:
            # A failed arm is ABSENT, never a slow one.
            rows.append({"arm": name, "ok": False, "error": str(e)[:200]})

    print("\n" + "=" * 78)
    print("CPU SWEEP — caption paint, 443 frames, Gadzhi @ 15fps, fixed plan")
    print("=" * 78)
    print(f"  {'arm':8}{'cpu':>5}{'eff_cores':>11}{'single_ms':>11}"
          f"{'paint_s':>10}{'ms/frame':>10}{'bundle_s':>10}")
    base = None
    for r in rows:
        if not r.get("ok"):
            print(f"  {r.get('arm','?'):8}  FAILED — {str(r.get('error'))[:60]}")
            continue
        b = r.get("bench") or {}
        if not b.get("digest_ok"):
            print(f"  {r['arm']:8}  WORKLOAD DIGEST MISMATCH — NOT COMPARABLE")
            continue
        print(f"  {r['arm']:8}{b.get('cpu_count'):>5}"
              f"{b.get('effective_cores'):>11}{b.get('single_ms'):>11}"
              f"{(r['paint_ms'] or 0)/1000:>10.1f}{r['ms_per_frame']:>10.1f}"
              f"{(r.get('bundle_ms') or 0)/1000:>10.1f}")
        if r["arm"] == "cpu8":
            base = r
    if base and base.get("ms_per_frame"):
        print()
        for r in rows:
            if r.get("ok") and r.get("ms_per_frame") and r["arm"] != "cpu8":
                sp = base["ms_per_frame"] / r["ms_per_frame"]
                print(f"  {r['arm']} vs cpu8: {sp:.2f}x faster on paint")
        print("\n  Read this against effective_cores, not against cpu: a container")
        print("  that does not deliver the cores it claims cannot paint with them.")
