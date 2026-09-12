#!/usr/bin/env python3
"""Re-read the whole reference corpus, one video at a time, STATE per video.

Same discipline as run_craft_set.py: each record is written the moment it
lands, so a failure at video 7 does not cost videos 1-6, and a FAILED video is
NAMED in the manifest rather than silently shrinking the corpus the index is
then derived from. A cached FAILED must never read as done.

    REFCORPUS_FPS=5 python3 run_reference_reread.py [--price-only]
"""
import json
import os
import subprocess
import sys

EX = os.path.expanduser("~/Desktop/EXAMPLES")
OUT = os.environ.get("REFCORPUS_OUT", "/tmp/refcorpus_5fps")
FPS = os.environ.get("REFCORPUS_FPS", "2")


def measured(path):
    """A file on disk is not a result."""
    if not os.path.exists(path):
        return False
    try:
        d = json.load(open(path))
        return d.get("state") == "MEASURED" and bool(d.get("record", {}).get("beats"))
    except Exception:                                             # noqa: BLE001
        return False


def main():
    price_only = "--price-only" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    names = sorted(n for n in os.listdir(EX) if n.endswith(".mp4"))
    print(f"  corpus {len(names)} videos   fps={FPS}   out={OUT}"
          f"{'   PRICE ONLY' if price_only else ''}")
    manifest = []
    for n in names:
        dst = f"{OUT}/{n}.json"
        if not price_only and measured(dst):
            print(f"  [skip MEASURED] {n}")
            manifest.append({"video": n, "state": "MEASURED", "cached": True})
            continue
        rec = f"{OUT}/{n}.record.json"
        cmd = [sys.executable, "build_reference_records.py",
               os.path.join(EX, n), "--out", rec]
        if price_only:
            cmd.append("--price-only")
        env = dict(os.environ, REFCORPUS_FPS=FPS)
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        tail = (r.stdout + r.stderr).strip().splitlines()
        print(f"  [{n}] rc={r.returncode}")
        for line in tail:
            print("     " + line)
        if price_only:
            manifest.append({"video": n, "state": "PRICED", "rc": r.returncode})
            continue
        # STATE, NOT A FILE TEST. rc==0 with no parseable record is FAILED.
        state, body = "FAILED", None
        if r.returncode == 0 and os.path.exists(rec):
            try:
                body = json.load(open(rec))
                state = "MEASURED" if body.get("beats") else "ABSENT"
            except Exception as e:                                # noqa: BLE001
                state = "FAILED"
                body = {"parse_error": f"{type(e).__name__}: {e}"}
        json.dump({"video": n, "state": state, "fps": float(FPS),
                   "record": body or {}, "stdout": "\n".join(tail)},
                  open(dst, "w"), ensure_ascii=False)
        manifest.append({"video": n, "state": state})
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=1)
    n_ok = sum(1 for m in manifest if m["state"] in ("MEASURED", "PRICED"))
    print(f"\n  {n_ok}/{len(manifest)} ok")
    for m in manifest:
        if m["state"] not in ("MEASURED", "PRICED"):
            print(f"    {m['state']}: {m['video']}")
    return 0 if n_ok == len(manifest) else 1


if __name__ == "__main__":
    sys.exit(main())
