#!/usr/bin/env python3
"""WATCH THE WHOLE REFERENCE SET, ONE VIDEO AT A TIME.

The shape was proven on the shortest video first (832 words, 0 timestamps,
craft not paraphrase). This runs the remaining nine.

Each result is written to its OWN file the moment it lands, so a crash at
video 7 does not cost videos 1-6. STATE is recorded per video: a FAILED or
ABSENT video is named in the manifest, never silently dropped — the synthesis
pass must know it is reading nine analyses or six.
"""
import concurrent.futures as cf
import json
import os
import sys
import time

import modal

EX = os.path.expanduser("~/Desktop/EXAMPLES")
OUT = os.environ.get("CRAFT_OUT", "/tmp/craft_out")
DONE = "v09044g40000cm9oa7nog65s2crhkf00.mp4"      # the shape check, already run

os.makedirs(OUT, exist_ok=True)


def measured(path):
    """A file on disk is not a result. Only MEASURED counts as done — a cached
    FAILED would be skipped forever and silently shrink the corpus the
    synthesis reads."""
    import json as _j
    import os as _o
    if not _o.path.exists(path):
        return False
    try:
        return _j.load(open(path))["state"] == "MEASURED"
    except Exception:                                             # noqa: BLE001
        return False


def main():
    weight = sys.argv[1] if len(sys.argv) > 1 else "zac_reference"
    # THE ONLY THING THAT CHANGES BETWEEN ARMS. Same bytes, same prompt, same
    # weights — so a difference is attributable to the sample rate and to
    # nothing else.
    fps = float(os.environ.get("CRAFT_FPS", "0") or 0)
    print(f"  video sample rate: {fps or 'DEFAULT (1 fps)'}   out: {OUT}")
    names = sorted(n for n in os.listdir(EX) if n.endswith(".mp4"))
    todo = [n for n in names if not measured(f"{OUT}/{n}.json")]
    if fps and DONE in todo:
        pass          # a new rate re-runs every video, including the shape check
    elif DONE in todo and os.path.exists("/tmp/craft_one.json"):
        # carry the shape-check result into the set rather than paying twice
        r = json.load(open("/tmp/craft_one.json"))
        json.dump(r, open(f"{OUT}/{DONE}.json", "w"))
        todo.remove(DONE)
        print(f"  carried in the shape check: {DONE}")

    total_s = 0.0
    for n in todo:
        total_s += os.path.getsize(os.path.join(EX, n)) / 1e6
    print(f"PRICE STATED: {len(todo)} videos, {total_s:.0f}MB of footage. "
          f"Gemini 2.5 Pro video-in at ~263 tok/s of runtime "
          f"=> ~$0.25-0.40 total. No GPU, no Modal render.")
    if not todo:
        print("  nothing to do — every video already has an analysis")
        return 0

    fn = modal.Function.from_name("promptly-craft-pass", "analyse")

    def one(name):
        b = open(os.path.join(EX, name), "rb").read()
        t0 = time.time()
        r = fn.remote(b, name, weight, sample_fps=fps)
        r["_client_wall_s"] = round(time.time() - t0, 1)
        json.dump(r, open(f"{OUT}/{name}.json", "w"))
        return name, r

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        for fut in cf.as_completed([ex.submit(one, n) for n in todo]):
            try:
                name, r = fut.result()
            except Exception as e:                                # noqa: BLE001
                print(f"  *** CLIENT FAILED {type(e).__name__}: {e}")
                continue
            print(f"  {r['state']:9s} {name[:40]:42s} {r['detail'][:52]:54s} "
                  f"{r['_client_wall_s']}s")

    states = {}
    for n in sorted(os.listdir(OUT)):
        if n.endswith(".json"):
            states[n] = json.load(open(f"{OUT}/{n}"))["state"]
    ok = sum(1 for v in states.values() if v == "MEASURED")
    print(f"\n  {ok}/{len(states)} MEASURED in {time.time() - t0:.0f}s "
          f"(the synthesis reads exactly these {ok})")
    for k, v in states.items():
        if v != "MEASURED":
            print(f"  *** NOT MEASURED: {k} -> {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
