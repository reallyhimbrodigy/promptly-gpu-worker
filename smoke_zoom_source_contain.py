#!/usr/bin/env python3
"""A zoom must not CROP the user's frame: the source plate is objectFit contain.

THE DEFECT THIS PREVENTS IS INVISIBLE IN EVERY TALLY. `cover` renders a
perfectly good frame — right duration, right motion, real footage, a real zoom —
with the edges of the user's own picture silently cut off. Nothing errors, the
velocity cap is unaffected, the component lands in the manifest and passes every
count. It is the repo's third failure class: a change that is REAL AND WRONG,
and only comparing the output against the SOURCE it was derived from sees it.

WHY IT IS A CHECK AND NOT A COMMENT. The seven bodies each carried a written
exception arguing `cover` was correct, and each was right when written: before
canvas-follows-source, a portrait canvas on a landscape source had bars, and
which fit placed them was a real question. That landed — prestage derives the
canvas per run, w/h/fps are keyword-only with no default — so both reasons
expired together. A prose exception that expires is exactly how `cover` comes
back: one plausible paragraph at a time, the same way a density rate does.

THE PINNED EXCEPTIONS ARE AN ARGUMENT ON THE RECORD, NOT AN ALLOW-LIST. Each
names a layer that is deliberately cropped INTO A CARD or INTO AN INSET, where
the frame is decoration rather than the subject, and the crop is the design. A
pin is re-read and re-argued when it is touched; a skip list is not.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")

# The zoom family, per lane_contract.live_set(). Derived, never hand-listed —
# a zoom added to the library must be covered the day it lands.
sys.path.insert(0, HERE)
import lane_contract as lc                                     # noqa: E402

# file -> why its ONE cover site is deliberately cropped. The SUBJECT of each is
# the card or the inset, not the user's frame.
#
# KEYED ON THE FILE, NOT ON A LINE, AND THE LINE NUMBER WAS NEVER LOAD-BEARING.
# This was (file, line) and it drifted TWICE IN TWO EDITS on the same file:
# EmojiCard's cover moved 78 -> 127 when I inserted the no-still branch, then
# 127 -> 140 when I rewrote that branch. Both times L4 correctly refused the
# stale pin — the guard worked — and both times the repair was to retype a
# number that was about to move again.
#
# Every pinned file contains EXACTLY ONE cover site, so the line carried no
# information the file did not already carry. L4 now asserts that count instead:
# one cover per pinned file, pinned by file. Insertions above it are free, and a
# SECOND cover appearing in a pinned file is caught as an unpinned site rather
# than being silently covered by a stale pin.
#
# This repo's own rule, arrived at the hard way for the third time today: anchor
# on the thing, not on one spelling of where the thing sits.
PINNED_COVER_FILES = {
    "FocusWindow.jsx": "the MAGNIFIED INSET — a loupe that contained itself would show the whole frame twice",
    "LetterboxPush.jsx": "the inner window LAYER, which is the letterbox itself; its outer plate is contain",
    "DeviceMockup.jsx": "the frame is mounted INSIDE a phone bezel — the bezel is the subject",
    "EvidenceCard.jsx": "cropped to a 16/9 card face; the card is the subject",
    "EmojiCard.jsx": "cropped to a 4/5 card face; the card is the subject",
}

FAILS = []


def leg(name, ok, got):
    print("  %-38s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def main():
    ls = lc.live_set()
    if ls["state"] != lc.MEASURED:
        print("HARNESS FAILURE: live_set is %s (%s)" % (ls["state"], ls.get("why")))
        return 2
    zooms = ls["by_family"].get("zoom") or []
    # A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING. all([]) is True.
    leg("L0 zoom_family_nonempty", len(zooms) >= 7, "%d zooms" % len(zooms))
    if not zooms:
        print("0/0 — refusing to report a pass over an empty family")
        return 1

    missing = [z for z in zooms if not os.path.exists(os.path.join(BODIES, z + ".jsx"))]
    leg("L1 every_zoom_has_a_body", not missing, "missing: %s" % (missing or "none"))

    # L2 every zoom's SOURCE plate is contain, and any cover in a zoom body is pinned.
    unpinned, checked = [], 0
    for z in zooms:
        p = os.path.join(BODIES, z + ".jsx")
        if not os.path.exists(p):
            continue
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if re.search(r'objectFit\s*:\s*"cover"', line):
                checked += 1
                if (z + ".jsx") not in PINNED_COVER_FILES:
                    unpinned.append("%s:%d" % (z, i))
    leg("L2 no_unpinned_cover_in_zooms", not unpinned,
        "%d cover site(s) in zoom bodies, %d unpinned %s"
        % (checked, len(unpinned), unpinned or ""))

    # L3 each zoom actually HAS a contain plate — "no cover" is satisfied by a
    # body with no plate at all, which is the absence-as-success shape.
    nocontain = []
    for z in zooms:
        p = os.path.join(BODIES, z + ".jsx")
        if os.path.exists(p) and not re.search(r'objectFit\s*:\s*"contain"',
                                               open(p, encoding="utf-8").read()):
            nocontain.append(z)
    leg("L3 every_zoom_has_contain", not nocontain, "without contain: %s" % (nocontain or "none"))

    # L4 THE PINS ARE LIVE, AND EACH COVERS EXACTLY ONE SITE. A pin for a file
    # with no cover is a stale argument; a pin for a file with TWO is a pin
    # quietly licensing a second crop nobody argued for.
    stale, doubled = [], []
    for fn in sorted(PINNED_COVER_FILES):
        p = os.path.join(BODIES, fn)
        if not os.path.exists(p):
            stale.append("%s (no file)" % fn)
            continue
        n = len(re.findall(r'objectFit\s*:\s*"cover"',
                           open(p, encoding="utf-8").read()))
        if n == 0:
            stale.append(fn)
        elif n > 1:
            doubled.append("%s (%d)" % (fn, n))
    leg("L4 pins_live_and_single", not stale and not doubled,
        "stale: %s | more than one cover: %s" % (stale or "none", doubled or "none"))

    # L5 repo-wide: a cover anywhere in port/bodies is either pinned or a zoom
    # failure already caught above. This is what catches a NEW body shipping cover.
    everywhere = []
    for fn in sorted(os.listdir(BODIES)):
        if not fn.endswith(".jsx"):
            continue
        for i, line in enumerate(open(os.path.join(BODIES, fn), encoding="utf-8")
                                 .read().splitlines(), 1):
            if re.search(r'objectFit\s*:\s*"cover"', line) and fn not in PINNED_COVER_FILES:
                everywhere.append("%s:%d" % (fn, i))
    leg("L5 no_unpinned_cover_anywhere", not everywhere, "unpinned: %s" % (everywhere or "none"))

    # L6 THE BUILT BLOB IS WHAT REGISTERS, AND IT MUST NOT BE STALE.
    # port/bodies/*.jsx is a TEMPLATE — six of the seven zooms carry a
    # `// @@VELOCITY_CAP@@` marker that port/emit_zoom_component.mjs replaces —
    # so the file this smoke reads is NOT the file that ships. When the contain
    # switch landed I edited the bodies and never rebuilt: every legs above went
    # green while port/build/ still said `cover`, and I was one tool call from
    # registering a body with the marker still in it, which would have shipped
    # components calling three undefined symbols.
    #
    # The build already had a --check mode for exactly this and nothing ran it.
    # A generator with a drift check that no gate invokes is a check that does
    # not exist.
    import subprocess
    r = subprocess.run(["node", os.path.join(HERE, "port", "emit_zoom_component.mjs"), "--check"],
                       cwd=HERE, capture_output=True, text=True)
    drift = [l for l in (r.stdout or "").splitlines() if l.startswith("DRIFT")]
    leg("L6 built_blobs_in_sync", r.returncode == 0,
        "emit --check rc=%d, %d drifted %s" % (r.returncode, len(drift),
                                               [d.split()[1].rstrip(":") for d in drift] or ""))

    # L7 and no built blob still carries the marker — the failure that would
    # actually reach a user, rather than the one that is merely out of date.
    left = []
    for fn in sorted(os.listdir(os.path.join(HERE, "port", "build"))):
        if fn.endswith(".jsx") and "@@VELOCITY_CAP@@" in open(
                os.path.join(HERE, "port", "build", fn), encoding="utf-8").read():
            left.append(fn[:-4])
    leg("L7 no_unsubstituted_marker", not left, "still templated: %s" % (left or "none"))

    print("%d/%d legs ok" % (8 - len(FAILS), 8))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
