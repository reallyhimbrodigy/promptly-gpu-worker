#!/usr/bin/env python3
"""Refuse to launch a round over a tree nobody described.

Builder-2's mount_scratch_check.py finds untracked/modified files under the
mounted paths. It checks the CHECKOUT IT RUNS IN — and that is not where the
mounts resolve. Run from the lane worktree it reports CLEAN (exit 0); run from
the main checkout it finds 5 files (exit 1), and the app mounts MAIN's
src/remotion because _REMOTION_SRC climbs _HERE/../../src/remotion, out of the
worktree. Wiring the checker as-is would have been a pre-flight that inspects a
directory the image never sees — a green from the wrong tree.

So this asks mount_fingerprint for the RESOLVED paths — the same list the
fingerprint hashes and the image copies — and checks each one in whatever
repository actually contains it.

WHY A PRE-FLIGHT WHEN THE FINGERPRINT ALREADY GUARDS. The fingerprint catches
drift DURING a round, which is right and has fired twice on real drift. But it
catches it after N arms have been paid for: rounds 37 and 38 both died three
arms in. This turns "we discover the tree was dirty after three arms" into "we
never launched".
"""
import os
import subprocess
import sys

import mount_fingerprint as MF


def toplevel(path):
    d = path if os.path.isdir(path) else os.path.dirname(path)
    r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip() or None


def main():
    paths = MF.mounted_paths()
    dirty, unchecked = [], []
    for p in paths:
        top = toplevel(p)
        if not top:
            # ~/.claude/skills is not in a repository. Reported, never assumed
            # clean: it is mounted and it can change, we just cannot see how.
            unchecked.append(p)
            continue
        r = subprocess.run(["git", "-C", top, "status", "--porcelain", "--", p],
                           capture_output=True, text=True)
        for line in (r.stdout or "").splitlines():
            if line.strip():
                dirty.append((top, line))
    print(f"MOUNT PRE-FLIGHT — {len(paths)} resolved mounted path(s)")
    for u in unchecked:
        print(f"  NOT CHECKED (outside any repo): {u}")
    if not dirty:
        print("  CLEAN — every in-repo mounted path is tracked and unmodified")
        return 0
    print(f"\n  {len(dirty)} file(s) would enter the image undescribed:")
    seen = set()
    for top, line in dirty:
        if line in seen:
            continue
        seen.add(line)
        print(f"    [{os.path.basename(top)}] {line}")
    print("\n  A round launched now mounts a tree nobody described, and the")
    print("  fingerprint will abort it the moment anyone tidies up — which is")
    print("  exactly how rounds 37 and 38 died, three arms in, twice.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
