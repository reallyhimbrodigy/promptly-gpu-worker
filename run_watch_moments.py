#!/usr/bin/env python3
"""Watch all ten, one video at a time, and write each result the moment it lands.

A crash at video 7 must not cost videos 1-6, and a FAILED video must be NAMED
rather than silently shrinking the corpus the sheet is built from — the
synthesis that reads nine analyses and thinks it read ten is the whole reason
this file records state per video.
"""
import concurrent.futures as cf
import json
import os
import subprocess
import sys
import time

import modal

EX = os.path.expanduser(os.environ.get("WATCH_EX", "~/Desktop/EXAMPLES"))
OUT = os.environ.get("WATCH_OUT", "/tmp/watched")


def duration_of(path):
    """ffprobe or nothing. A guessed duration would let an out-of-range
    timestamp through the validator that exists to catch it."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", path],
                       capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("ffprobe could not read %s: %s"
                           % (path, (r.stderr or "")[:200]))
    return float(r.stdout.strip())


def measured(path):
    """A file on disk is not a result. Only MEASURED counts as done — a cached
    FAILED would be skipped forever."""
    if not os.path.exists(path):
        return False
    try:
        return json.load(open(path))["state"] == "MEASURED"
    except Exception:                                             # noqa: BLE001
        return False


def main():
    os.makedirs(OUT, exist_ok=True)
    fps = float(os.environ.get("WATCH_FPS", "5") or 5)
    names = sorted(n for n in os.listdir(EX) if n.endswith(".mp4"))
    if not names:
        print("no .mp4 in %s" % EX)
        return 2
    todo = [n for n in names if not measured("%s/%s.json" % (OUT, n))]
    runtime = sum(duration_of(os.path.join(EX, n)) for n in names)
    print("  %d videos, %.0fs of footage, sampling video at %g fps WITH AUDIO"
          % (len(names), runtime, fps))
    print("  PRICE STATED: Gemini 2.5 Pro video-in ~263 tok/s + audio ~32 tok/s "
          "=> ~%.0fk input tokens, ~30k output. ~$0.40-0.60 total. No GPU."
          % (runtime * 295 / 1000.0))
    print("  already MEASURED: %d   to run: %d" % (len(names) - len(todo),
                                                   len(todo)))
    if not todo:
        return 0

    fn = modal.Function.from_name("promptly-watch-moments", "watch")

    def one(name):
        p = os.path.join(EX, name)
        d = duration_of(p)
        t0 = time.time()
        r = fn.remote(open(p, "rb").read(), name, d, sample_fps=fps)
        r["_client_wall_s"] = round(time.time() - t0, 1)
        json.dump(r, open("%s/%s.json" % (OUT, name), "w"), indent=1)
        return name, r

    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        for name, r in ex.map(one, todo):
            n = len((r.get("record") or {}).get("moments") or [])
            print("  %-44s %-8s %3d moments  %5.1fs  in=%s out=%s  %s"
                  % (name, r["state"], n, r.get("wall_s") or 0,
                     (r.get("tokens") or {}).get("in"),
                     (r.get("tokens") or {}).get("out"),
                     (r.get("detail") or "")[:70]))

    states = {}
    total = 0
    for name in names:
        try:
            r = json.load(open("%s/%s.json" % (OUT, name)))
        except Exception:                                         # noqa: BLE001
            states["NO FILE"] = states.get("NO FILE", 0) + 1
            continue
        states[r["state"]] = states.get(r["state"], 0) + 1
        total += len((r.get("record") or {}).get("moments") or [])
    print("\n  %.0fs wall   states %s   %d moments across %d videos"
          % (time.time() - t0, states, total, len(names)))
    if states.get("MEASURED", 0) != len(names):
        print("  *** NOT EVERY VIDEO WAS WATCHED — the sheet built from this "
              "is built from %d of %d" % (states.get("MEASURED", 0), len(names)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
