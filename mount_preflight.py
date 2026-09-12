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
import hashlib
import json
import os
import subprocess
import sys

import mount_fingerprint as MF

# A CROSS-LANE FILE CAN BE DESCRIBED WITHOUT BEING COMMITTED, AND THAT IS THE
# ONLY WAY OUT THAT IS NOT A BYPASS.
#
# The abort says "nobody described this tree". The remedy it wants is a
# DESCRIPTION, not a disabled check — and when the file belongs to another lane
# there is a third option between "commit it" and "launch blind": its owner
# attests to the exact bytes, and this records them.
#
# It is deliberately NOT a skip list. An entry must carry the sha256 of the
# bytes it attests to, so:
#   * the attestation is verified here, every launch, against the file on disk;
#   * if the owner commits, reverts or edits it, the sha stops matching and the
#     abort comes back — the drift this check exists for is still caught;
#   * the round record gets a fingerprint of real bytes instead of "M file.mjs",
#     which is the difference between a description and a shrug.
#
# A stale identifier and a real one are indistinguishable once written down, so
# nothing here is trusted: the sha in the file is re-read from disk at launch.
ATTEST = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "mount_attestations.json")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _attestations():
    if not os.path.exists(ATTEST):
        return {}
    try:
        return {a["path"]: a for a in json.load(open(ATTEST))["attested"]}
    except Exception as e:                                        # noqa: BLE001
        # A MALFORMED ATTESTATION FILE IS NOT AN EMPTY ONE. Returning {} here
        # would silently re-block every launch and read as the owner having
        # withdrawn their attestation.
        print(f"  *** {ATTEST} is unreadable ({type(e).__name__}) — that is "
              f"ABSENT, not empty; fix it rather than launching")
        raise SystemExit(2)


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
                dirty.append((top, line, os.path.join(top, line[3:].strip())))
    att = _attestations()
    kept, covered = [], []
    for top, line, full in dirty:
        a = att.get(os.path.relpath(full, top))
        if not a:
            kept.append((top, line))
            continue
        if not os.path.exists(full):
            kept.append((top, line + "   [attested but MISSING]"))
            continue
        actual = _sha256(full)
        if actual != a.get("sha256"):
            kept.append((top, line + f"   [attestation STALE: on disk "
                                     f"{actual[:16]}, attested "
                                     f"{str(a.get('sha256'))[:16]}]"))
            continue
        covered.append((os.path.relpath(full, top), a, actual))
    dirty = kept
    print(f"MOUNT PRE-FLIGHT — {len(paths)} resolved mounted path(s)")
    for rel, a, sha in covered:
        print(f"  ATTESTED  {rel}")
        print(f"            sha256 {sha}")
        print(f"            owner {a.get('owner')} · {a.get('why')}")
        print(f"            reachable from this lane: {a.get('reachable')}")
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
