#!/usr/bin/env python3
"""Run the LISTENING index pass over the ten. One video at a time, STATE each.

Mechanical cuts come from the SAME ffmpeg detector the silent pass used, so the
two arms are given identical ground truth for WHERE cuts are and differ only in
what the reader can perceive.

    python3 run_reference_listen.py [--price-only]
"""
import json
import os
import sys

import modal

EX = os.path.expanduser("~/Desktop/EXAMPLES")
OUT = os.environ.get("REFLISTEN_OUT", "/tmp/refcorpus_listen")
FPS = float(os.environ.get("REFLISTEN_FPS", "5"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_reference_records as BRR  # noqa: E402  (same detector, same constants)


def measured(p):
    if not os.path.exists(p):
        return False
    try:
        d = json.load(open(p))
        return d.get("state") == "MEASURED" and bool(
            (d.get("record") or {}).get("beats"))
    except Exception:                                             # noqa: BLE001
        return False


def main():
    os.makedirs(OUT, exist_ok=True)
    names = sorted(n for n in os.listdir(EX) if n.endswith(".mp4"))
    fn = modal.Function.from_name("promptly-reference-listen", "listen")
    print(f"  {len(names)} videos   fps={FPS}   out={OUT}")
    todo = [n for n in names if not measured(f"{OUT}/{n}.json")]
    print(f"  {len(names)-len(todo)} already MEASURED, {len(todo)} to run")

    calls = []
    for n in todo:
        path = os.path.join(EX, n)
        dur = BRR.probe_duration(path)
        shots = BRR.pass_a_shots(path)
        if dur is None:
            json.dump({"label": n, "state": "FAILED",
                       "detail": "ffprobe failed — UNMEASURED, not a "
                                 "zero-length video"},
                      open(f"{OUT}/{n}.json", "w"))
            print(f"  [{n}] ffprobe FAILED")
            continue
        data = open(path, "rb").read()
        print(f"  [{n}] {dur:.1f}s  {len(data)/1e6:.1f}MB  "
              f"{len(shots or [])} mechanical cuts -> spawning")
        # KEYWORDS, NEVER POSITIONAL. `listen` takes
        # (video_bytes, label, duration_s, mechanical_cuts, transcript, model,
        # sample_fps) and a positional call put FPS into `model` — the same
        # failure that killed round 56 when edit()'s signature grew in the
        # middle. A remote signature is a contract you cannot see from here.
        calls.append((n, fn.spawn(video_bytes=data, label=n, duration_s=dur,
                                  mechanical_cuts=shots or [], transcript="",
                                  sample_fps=FPS)))

    ok = 0
    for n, c in calls:
        try:
            r = c.get()
        except Exception as e:                                    # noqa: BLE001
            r = {"label": n, "state": "FAILED",
                 "detail": f"{type(e).__name__}: {str(e)[:200]}"}
        json.dump(r, open(f"{OUT}/{n}.json", "w"), ensure_ascii=False)
        bs = (r.get("record") or {}).get("beats") or []
        nm = {t.get("name") for b in bs for t in (b.get("treatment") or [])
              if isinstance(t, dict)}
        print(f"  [{n}] {r.get('state')}  {len(bs)} beats  {len(nm)} names  "
              f"{r.get('detail','')[:90]}")
        if r.get("state") == "MEASURED":
            ok += 1
    print(f"\n  {ok}/{len(calls)} MEASURED this run")
    return 0 if ok == len(calls) else 1


if __name__ == "__main__":
    sys.exit(main())
