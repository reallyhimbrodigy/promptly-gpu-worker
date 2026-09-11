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
  cold — PROMPTLY_REMOTION_BUNDLE_CACHE=0, the kill switch the batch file
         already ships as its own control arm: bundle + startup
  warm — cache as found: startup alone

THE ARM MUST PROVE IT IS THE ARM IT CLAIMS. The first version cleared a
directory it GUESSED at (/tmp/remotion-bundle-cache) while the real cache is
/work/.rbundle, so "cold" cleared nothing, both arms ran in the same warm
container, and the labels came back INVERTED — 8.54s against the arm called
warm and 0.55s against the arm called cold. The numbers were right and every
word attached to them was wrong. So each arm now asserts BUNDLE_CACHED is what
that arm requires, and a mismatch is FAILED, not a result.

STATE, NOT A NUMBER. A run whose BUNDLE line never appears is FAILED, not 0.
"""
import modal

from agentic_editor_app import IMG as _IMG                        # noqa: E402

# THE MODULE HAS TO BE IN THE IMAGE, because Modal re-imports THIS FILE inside
# the container to find the function, and line 1 of it imports the app module.
# Reusing the real image is the point — a probe that builds its own image is
# measuring its own image — but reuse means the import must resolve on both
# sides of the boundary, and only the entrypoint file is mounted for free.
image = _IMG.add_local_file("agentic_editor_app.py",
                            "/root/agentic_editor_app.py", copy=True)

app = modal.App("promptly-zoom-empty-probe")


@app.function(image=image, cpu=8, memory=16384, timeout=900)
def empty_batch(cold: bool) -> dict:
    import os
    import re
    import subprocess
    import time

    R = "/promptly-remotion"
    env = dict(os.environ)
    if cold:
        env["PROMPTLY_REMOTION_BUNDLE_CACHE"] = "0"

    jf = "/tmp/empty_jobs.json"
    open(jf, "w").write("[]")
    t0 = time.time()
    p = subprocess.run(["node", os.path.join(R, "remotion_batch.mjs"), jf],
                       capture_output=True, text=True, timeout=870, env=env)
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
    cached = int(c.group(1)) if c else None
    want = 0 if cold else 1
    if cached is None:
        return {"state": "ABSENT", "wall_s": wall,
                "detail": "no BUNDLE_CACHED line — cannot tell which arm ran"}
    if cached != want:
        # THE ARM IS NOT THE ARM. Reporting the number anyway is how the
        # inverted labels happened.
        return {"state": "FAILED", "wall_s": wall, "bundle_cached": cached,
                "detail": f"arm cold={cold} requires BUNDLE_CACHED {want}, "
                          f"got {cached} — this is the OTHER arm, not a result"}
    return {"state": "MEASURED", "wall_s": wall, "rc": p.returncode,
            "bundle_ms": int(m.group(1)),
            "bundle_cached": cached,
            "jobs_painted": 0,
            "detail": f"empty payload: {wall}s wall, bundle "
                      f"{int(m.group(1)) / 1000:.2f}s, BUNDLE_CACHED={cached}, "
                      f"0 jobs painted"}


@app.local_entrypoint()
def main():
    print("PRICE STATED: 2 container-minutes on cpu=8, no GPU, image layers "
          "already built. ~$0.02.")
    for cold in (True, False):
        r = empty_batch.remote(cold)
        arm = ("cold (BUNDLE_CACHE=0, forced)" if cold
               else "warm (cache as found)")
        print(f"  {arm:24s} {r['state']:9s} {r.get('detail')}")
        if r["state"] != "MEASURED":
            print(f"    {str(r.get('out') or r.get('detail'))[:400]}")
