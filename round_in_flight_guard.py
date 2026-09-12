#!/usr/bin/env python3
"""Refuse to commit a MOUNTED path while a round is in flight.

THIS HAS NOW COST THREE ROUNDS. Rounds 61 and 62 died to a mounted file edited
mid-launch; round 64 died to a COMMIT made mid-round — by the person who had
just written the rule down, again. The mount fingerprint catches it, correctly,
and that is DETECTION: the round aborts after N arms are already paid for.
64 aborted after one arm, $0.151.

The pre-flight guards the moment BEFORE launch and the fingerprint guards
DURING — but nothing stopped the edit itself, and "remember not to touch the
tree for ten minutes" is exactly the kind of rule that rots. This is the
prevention half.

IT PROTECTS EVERY LANE, NOT JUST THE ONE THAT LAUNCHED. A round mounts paths
resolved out of the MAIN checkout as well as the lane worktree, so another
lane committing to src/remotion during someone else's round kills it the same
way. The lock is keyed to the round, not to the committer.

    exit 0  nothing in flight, or nothing staged that the image would mount
    exit 1  a round is running and this commit would change its tree
"""
import os
import subprocess
import sys

import mount_fingerprint as MF

FIXTURES = "/tmp/fixtures"


def in_flight():
    """Rounds that have announced themselves and not finished. STATE, not a guess."""
    out = []
    if not os.path.isdir(FIXTURES):
        return out
    for d in sorted(os.listdir(FIXTURES)):
        lock = os.path.join(FIXTURES, d, ".in_flight")
        if os.path.exists(lock):
            try:
                out.append((d, open(lock).read().strip()))
            except Exception:                                     # noqa: BLE001
                out.append((d, "(lock unreadable)"))
    return out


def main():
    live = in_flight()
    if not live:
        return 0
    # WHAT WOULD ACTUALLY ENTER THE IMAGE. A commit touching a file no mount
    # resolves is harmless and must not be blocked — a guard that fires on
    # every commit during a round gets switched off within a day.
    r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                       capture_output=True, text=True)
    staged = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
    if not staged:
        return 0
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True).stdout.strip()
    mounted = [os.path.realpath(p) for p in MF.mounted_paths()]
    hits = []
    for s in staged:
        full = os.path.realpath(os.path.join(top, s))
        for m in mounted:
            if full == m or full.startswith(m.rstrip("/") + os.sep):
                hits.append(s)
                break
    if not hits:
        return 0
    print("BLOCKED — a round is in flight and this commit changes its tree:")
    for d, fp in live:
        print(f"    {d} launched on {fp}")
    for h in sorted(set(hits)):
        print(f"    staged and MOUNTED: {h}")
    print("  The fingerprint would abort that round mid-arm and the arms "
          "already paid for are unscoreable.")
    print("  Wait for the round, or kill it first — rounds 61, 62 and 64 all "
          "died exactly here.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
