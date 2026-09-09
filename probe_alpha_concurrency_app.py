"""PROBE: does the alpha layer use the cores the container actually has?

build_alpha_layer is 34.3% of wall — the largest single stage. remotion_batch.mjs
runs concurrency 8. The container benchmark reports effective_cores 10.96-15.26
against a cgroup quota of 24. So the box may have capacity the renderer is not
asking for, and nobody has ever recorded a concurrency result on this
composition — sweep_micro_concurrency_app.py exists and has never produced one.

EVERY ARM PROVES ITS LAYER IS NOT EMPTY BEFORE ITS TIME IS READ.
This is the whole reason this file is being rewritten rather than re-run. Its
previous version measured a caption layer that rendered SIX HUNDRED FRAMES OF
NOTHING and reported a confident ms/frame for it, because a fast render of an
empty composition is just a fast render. alpha_layer_max answers the only
question that distinguishes them: an empty alpha plane reports YMAX 256, a real
layer reaches thousands. An arm whose layer is empty is reported as VOID, never
as a time.

CONCURRENCY IS THE ONLY VARIABLE. cpu is pinned at 8 — production's value — so
the answer applies to production rather than to a box nobody runs. Each arm
prints its CONTAINER line; identical bytes gave 49.0 and 134.2 ms/frame six
hours apart, so an arm without its machine measured is not comparable to the arm
beside it.

  modal run probe_alpha_concurrency_app.py
"""
import json
import os
import time

import modal

from agentic_editor_app import (IMG, SECRETS, caption_overlay_plan,
                                caption_pages, container_benchmark,
                                render_remotion_batch, alpha_layer_state, ALPHA_MEASURED,
                                _SUBPROCESS_ENV)

PROBE_IMG = IMG.add_local_python_source("agentic_editor_app")
app = modal.App("probe-alpha-concurrency")

FRAMES, FPS, STYLE, PAGES_N = 443, 15, "Gadzhi", 23


def _fixed_pages():
    """23 pages / 443 frames — the exact shape every talking_head run produces.

    Built through caption_pages(), not hand-rolled: a hand-rolled page shape got
    the field names wrong once already and would have rendered an empty layer
    that looked like a fast one.
    """
    words, per_s = [], (FRAMES / FPS) / (PAGES_N * 3)
    for i in range(PAGES_N * 3):
        words.append({"s": i * per_s, "e": (i + 1) * per_s,
                      "w": ("THIS", "IS", "PAGE")[i % 3] + str(i // 3)})
    return caption_pages(words, 3)


def _arm(conc):
    os.makedirs("/work", exist_ok=True)
    bench = container_benchmark()
    plan = "/work/conc-plan.json"
    with open(plan, "w") as fh:
        json.dump(caption_overlay_plan(_fixed_pages(), STYLE, FRAMES, fps=FPS), fh)
    out = f"/work/conc-{conc}.mov"
    env = dict(_SUBPROCESS_ENV or os.environ)
    env["PROMPTLY_REMOTION_CONCURRENCY"] = str(conc)
    # Cache OFF: a cached bundle would make arm 2+ faster for a reason that has
    # nothing to do with concurrency, and the bundle is not what is being swept.
    env["PROMPTLY_REMOTION_BUNDLE_CACHE"] = "0"
    t0 = time.time()
    res = render_remotion_batch([{
        "id": "alpha", "composition": "PromptlyOverlay",
        "propsFile": plan, "out": out, "alpha": True,
        "expect_frames": FRAMES,
    }], env=env, timeout=1800)
    wall = time.time() - t0
    job = (res or {}).get("alpha") or {}
    batch = (res or {}).get("_batch") or {}
    # alpha_layer_state, NOT alpha_layer_max. The max form returns a float or
    # None, and None is a FAILED MEASUREMENT wearing a result's clothes — the
    # production guard read `is not None and <= 260` and let it through. This
    # probe already treated None as void, but ABSENT and FAILED want different
    # diagnoses when an arm comes back empty, and a sweep that cannot say which
    # is a sweep that will be re-run to find out.
    astate, ymax, adetail = alpha_layer_state(out, env=env)
    # ALPHA_MEASURED, the SHIPPED CONSTANT — not the string "MEASURED".
    #
    # The first run of this sweep hardcoded the uppercase spelling. The constants
    # are lowercase ("measured"/"absent"/"failed"), so every arm compared
    # unequal and all four were discarded as VOID — including two that had read
    # ymax 65520 on a yuva444p12le plane, which is a layer FULL of content. The
    # gate failed safe, refusing to report rather than reporting a fake number,
    # but it threw away a good measurement and cost a re-run. Comparing against
    # a remembered spelling instead of the shipped symbol is the same class as
    # every text-match false green in this repo.
    empty = astate != ALPHA_MEASURED
    rec = {
        "concurrency": conc, "bench": bench,
        "ok": bool(job.get("ok")),
        "frames_actual": job.get("frames_actual"),
        "frames_ok": job.get("frames_ok"),
        "alpha_state": astate, "alpha_ymax": ymax, "alpha_detail": adetail,
        # VOID, not slow. An empty layer has no meaningful ms/frame and must not
        # be averaged with real ones.
        "void": bool(empty),
        "paint_ms": None if empty else job.get("ms"),
        "ms_per_frame": (None if empty or not job.get("ms")
                         else round(job["ms"] / FRAMES, 1)),
        "bundle_ms": batch.get("bundle_ms"),
        "wall_s": round(wall, 1),
        "error": job.get("error"),
    }
    print(f"[arm] {json.dumps(rec)}", flush=True)
    return rec


# CONCURRENCY CANNOT BE SWEPT ALONE. Remotion refuses outright:
#   "Maximum for --concurrency is 8 (number of cores on this system)"
# at cpu=8, so the 16 and 24 arms of the first sweep failed before rendering.
# The renderer is bounded by the CORE COUNT, which means the question "does
# paint scale past concurrency 8" is really "does paint scale with cpu" — and
# the two have to move together or the higher arms cannot run at all.
@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=8, memory=16384)
def c4():
    return _arm(4)


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=8, memory=16384)
def c8():
    return _arm(8)


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=16, memory=16384)
def c16():
    return _arm(16)


@app.function(image=PROBE_IMG, secrets=SECRETS, timeout=1800, cpu=32, memory=16384)
def c24():
    return _arm(24)


@app.local_entrypoint()
def main():
    rows = []
    for name, fn in (("4", c4), ("8", c8), ("16", c16), ("24", c24)):
        try:
            rows.append(fn.remote())
        except Exception as e:
            rows.append({"concurrency": name, "ok": False, "error": str(e)[:200]})

    print("\n" + "=" * 96)
    print("ALPHA-LAYER CONCURRENCY SWEEP — 443 frames, Gadzhi @ 15fps, cpu tracks concurrency, cache OFF")
    print("=" * 96)
    print(f"  {'conc':>5}{'eff_cores':>11}{'single_ms':>11}{'quota':>7}"
          f"{'alpha_ymax':>12}{'frames':>8}{'paint_s':>9}{'ms/frame':>10}")
    base = None
    for r in rows:
        if not r.get("ok"):
            print(f"  {str(r.get('concurrency')):>5}  FAILED — {str(r.get('error'))[:60]}")
            continue
        b = r.get("bench") or {}
        if not b.get("digest_ok"):
            print(f"  {r['concurrency']:>5}  WORKLOAD DIGEST MISMATCH — NOT COMPARABLE")
            continue
        if r.get("void"):
            print(f"  {r['concurrency']:>5}{str(b.get('effective_cores')):>11}"
                  f"{str(b.get('single_ms')):>11}{str(b.get('cpu_quota')):>7}"
                  f"{str(r.get('alpha_ymax')):>12}   *** VOID ({r.get('alpha_state')}) "
                  f"— {str(r.get('alpha_detail'))[:60]} — its time means nothing ***")
            continue
        print(f"  {r['concurrency']:>5}{str(b.get('effective_cores')):>11}"
              f"{str(b.get('single_ms')):>11}{str(b.get('cpu_quota')):>7}"
              f"{str(r.get('alpha_ymax')):>12}{str(r.get('frames_actual')):>8}"
              f"{(r['paint_ms'] or 0)/1000:>9.1f}{r['ms_per_frame']:>10.1f}")
        if r["concurrency"] == 8:
            base = r
    live = [r for r in rows if r.get("ok") and not r.get("void") and r.get("ms_per_frame")]
    if base and base.get("ms_per_frame") and len(live) > 1:
        print()
        for r in live:
            if r["concurrency"] == 8:
                continue
            print(f"  conc {r['concurrency']} vs production's 8: "
                  f"{base['ms_per_frame'] / r['ms_per_frame']:.2f}x on paint")
        print("\n  Read against effective_cores, not against the quota: a container")
        print("  that does not deliver cores cannot paint with them. If ms/frame is")
        print("  FLAT from 8 upward, the renderer is not the thing holding the box.")
    elif not live:
        print("\n  NO ARM PRODUCED A NON-EMPTY LAYER — nothing was measured. The")
        print("  previous version of this probe reported ms/frame for exactly this")
        print("  state for two rounds.")
