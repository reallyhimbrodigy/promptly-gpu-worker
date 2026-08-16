#!/usr/bin/env python3
"""THE INSTALLED SET IS A REVIEWED ARTEFACT, NOT A RESOLVER'S OPINION `[Rule 1]`.

WHY THIS EXISTS, and it cost 33 users fifteen minutes each.

On 2026-08-15 a one-line change — `supabase>=2,<3` -> `supabase==2.7.4` — took
the entire editorial path down for eleven hours. Not because the pin was wrong,
but because **Modal's `.pip_install()` layers resolve INDEPENDENTLY**. There is
no co-resolution, so a later layer silently downgrades an earlier one and NOBODY
REVIEWS THE RESULT. What actually happened, proven from PyPI metadata:

    supabase==2.7.4      requires  httpx<0.28,>=0.24
    google-genai>=1.3.0  requires  httpx<1.0.0,>=0.28.1

Mutually exclusive. Every google-genai release from 1.3.0 on carries that httpx
floor, so **1.2.0 is the ONLY version compatible with the pin** — pip did not
merely permit it, the pin mathematically forced it, 73 minor versions back. And
1.2.0 predates `VideoMetadata.fps`, so `generate_edit_gemini` raised on every
job before it ever reached the editorial gate.

The diff that caused it was ONE LINE and named ONE package. The damage was in a
package nobody typed. That is the whole class: **the thing that breaks you is
never the thing you edited.**

So the installed set becomes a committed, reviewed artefact. Any package that
moves without a corresponding change to `INSTALLED_SET.txt` is drift, and drift
is reported LOUDLY within seconds of a deploy instead of being discovered eleven
hours later by reading failure rates.

WHY POST-DEPLOY AND NOT PRE. The image does not exist until Modal builds it, so
there is nothing to freeze beforehand. This runs against the RUNNING image and
is honest about that: it is a smoke alarm, not a door lock. Catching drift 30
seconds after a deploy instead of 11 hours after is the entire win.

IT NEVER FAILS SILENTLY. If it cannot reach a container it says so and exits 2 —
"I could not measure" is reported as its own state, never as "no drift"
[the PROBE COLLAPSE class].

    python3 installed_set_diff.py            # diff live image vs INSTALLED_SET.txt
    python3 installed_set_diff.py --update   # accept current as the new baseline
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASELINE = os.path.join(HERE, "INSTALLED_SET.txt")
APP = "promptly-gpu-worker"


def _live_container():
    """A running container of the worker app, or None."""
    r = subprocess.run(["modal", "container", "list", "--json"],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return None
    try:
        rows = json.loads(r.stdout or "[]")
    except Exception:
        return None
    for c in rows:
        if APP in str(c.get("App Name", "")):
            cid = c.get("Container ID")
            if cid:
                return cid
    return None


def _freeze(container_id):
    r = subprocess.run(
        ["modal", "container", "exec", container_id, "--",
         "python", "-m", "pip", "list", "--format=freeze"],
        capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return None
    out = {}
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if "==" in line and not line.startswith(("#", "PYTHON", "Usage")):
            name, _, ver = line.partition("==")
            out[name.strip().lower().replace("_", "-")] = ver.strip()
    return out or None


def _load_baseline():
    if not os.path.exists(BASELINE):
        return None
    out = {}
    for line in open(BASELINE, encoding="utf-8"):
        line = line.strip()
        if "==" in line:
            name, _, ver = line.partition("==")
            out[name.strip().lower().replace("_", "-")] = ver.strip()
    return out


def main(argv):
    cid = _live_container()
    if not cid:
        print("[installed-set] NO RUNNING CONTAINER for "
              f"{APP} — cannot read the live image.")
        print("[installed-set] THIS IS A FAILED MEASUREMENT, NOT A CLEAN DIFF. "
              "Re-run once a container is warm (any real job warms one).")
        return 2
    live = _freeze(cid)
    if not live:
        print(f"[installed-set] pip list FAILED inside {cid} — FAILED MEASUREMENT, "
              "not a clean diff.")
        return 2

    if "--update" in argv:
        with open(BASELINE, "w", encoding="utf-8") as f:
            for k in sorted(live):
                f.write(f"{k}=={live[k]}\n")
        print(f"[installed-set] baseline UPDATED from the live image: "
              f"{len(live)} packages -> {BASELINE}")
        print("[installed-set] COMMIT IT. An un-committed baseline reviews nothing.")
        return 0

    base = _load_baseline()
    if base is None:
        print(f"[installed-set] no baseline at {BASELINE} — run with --update once, "
              "then commit it.")
        return 2

    added = sorted(set(live) - set(base))
    removed = sorted(set(base) - set(live))
    moved = sorted(k for k in (set(live) & set(base)) if live[k] != base[k])

    print(f"[installed-set] live image {cid}: {len(live)} packages | "
          f"baseline: {len(base)}")
    if not (added or removed or moved):
        print(f"[installed-set] NO DRIFT — all {len(base)} packages match the "
              "reviewed baseline.")
        return 0

    print("\n[installed-set] !! DEPENDENCY DRIFT — packages moved that NO DIFF NAMED.")
    print("   This is the class that took editorial down for 11 hours on 2026-08-16:")
    print("   a one-line pin on `supabase` forced google-genai 73 versions back,")
    print("   because Modal's pip_install layers resolve INDEPENDENTLY.\n")
    for k in moved:
        print(f"   MOVED    {k:34} {base[k]:16} -> {live[k]}")
    for k in added:
        print(f"   ADDED    {k:34} {'-':16} -> {live[k]}")
    for k in removed:
        print(f"   REMOVED  {k:34} {base[k]:16} -> (gone)")
    print(f"\n   {len(moved)} moved, {len(added)} added, {len(removed)} removed.")
    print("   If this is INTENDED: python3 installed_set_diff.py --update && commit.")
    print("   If it is NOT: you have just found your next incident before it "
          "found your users.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
