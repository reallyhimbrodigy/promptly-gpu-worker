#!/usr/bin/env python3
"""THE EMPTY-PAYLOAD TEST: is remotion_batch's 133s startup, or work?

ONE INVOCATION. remotion_batch.mjs takes a JSON file of jobs and, with an
EMPTY list, still runs the whole per-process path — the bundle cache decision,
the bundle if cold, the public-asset sync — and paints nothing. Whatever that
costs IS the fixed toll. Everything above it is work.

WHY THIS AND NOT MORE AGGREGATES. The 133s was read once as a fixed toll from
two matching aggregates, and per_job_ms refuted it: the four jobs in one round
cost 64.9s, 11.1s, 25.3s and the rest — paint scales with frames. That left
the real question unanswered, because a number that scales can still sit on
top of a large constant. This measures the constant directly instead of
inferring it from a fit.

Two arms, because the bundle cache is the thing that decides which constant
you pay:
  cold — cache cleared first: bundle + startup
  warm — cache present: startup alone

STATE, NOT A NUMBER. A run whose BUNDLE line never appears is FAILED, not 0.
"""
import modal

from agentic_editor_app import IMG as image                     # noqa: E402

app = modal.App("promptly-zoom-empty-probe")


@app.function(image=image, cpu=8, memory=16384, timeout=900)
def empty_batch(clear_cache: bool) -> dict:
    import os
    import re
    import shutil
    import subprocess
    import time

    R = "/promptly-remotion"
    cache_root = None
    for c in ("/tmp/remotion-bundle-cache", os.path.join(R, ".bundle-cache")):
        if os.path.isdir(c):
            cache_root = c
    if clear_cache and cache_root:
        shutil.rmtree(cache_root, ignore_errors=True)

    jf = "/tmp/empty_jobs.json"
    open(jf, "w").write("[]")
    t0 = time.time()
    p = subprocess.run(["node", os.path.join(R, "remotion_batch.mjs"), jf],
                       capture_output=True, text=True, timeout=870)
    wall = round(time.time() - t0, 2)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"^BUNDLE (\d+)$", out, re.M)
    c = re.search(r"^BUNDLE_CACHED (\d)", out, re.M)
    if p.returncode != 0:
        return {"state": "FAILED", "wall_s": wall, "rc": p.returncode,
                "detail": out[-600:]}
    if not m:
        # ABSENT, NOT ZERO. No BUNDLE line means the process did not reach the
        # thing being measured, and a 0 here would read as "startup is free".
        return {"state": "ABSENT", "wall_s": wall, "rc": p.returncode,
                "detail": "no BUNDLE line — the per-process path did not run",
                "out": out[-600:]}
    return {"state": "MEASURED", "wall_s": wall, "rc": p.returncode,
            "bundle_ms": int(m.group(1)),
            "bundle_cached": int(c.group(1)) if c else None,
            "cache_root": cache_root,
            "jobs_painted": 0,
            "detail": f"empty payload: {wall}s wall, bundle "
                      f"{int(m.group(1)) / 1000:.2f}s, 0 jobs painted"}


@app.local_entrypoint()
def main():
    print("PRICE STATED: 2 container-minutes on cpu=8, no GPU. ~$0.02.")
    for clear in (False, True):
        r = empty_batch.remote(clear)
        arm = "cold (cache cleared)" if clear else "warm (cache as found)"
        print(f"  {arm:24s} {r['state']:9s} {r.get('detail')}")
        if r["state"] != "MEASURED":
            print(f"    {str(r.get('out') or r.get('detail'))[:400]}")
