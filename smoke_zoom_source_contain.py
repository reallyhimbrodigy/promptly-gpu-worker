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

# file -> why this one layer is deliberately cropped. The SUBJECT of each is the
# card or the inset, not the user's frame.
PINNED_COVER = {
    ("FocusWindow.jsx", 154): "the MAGNIFIED INSET — a loupe that contained itself would show the whole frame twice",
    ("LetterboxPush.jsx", 134): "the inner window LAYER, which is the letterbox itself; the outer plate at 107 is contain",
    ("DeviceMockup.jsx", 83): "the frame is mounted INSIDE a phone bezel — the bezel is the subject",
    ("EvidenceCard.jsx", 86): "cropped to a 16/9 card face; the card is the subject",
    ("EmojiCard.jsx", 78): "cropped to a 4/5 card face; the card is the subject",
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
                if (z + ".jsx", i) not in PINNED_COVER:
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

    # L4 the pins are LIVE. A pin whose line no longer says cover is a stale
    # argument, and a stale note is read as fact by the next person.
    stale = []
    for (fn, ln), _why in PINNED_COVER.items():
        p = os.path.join(BODIES, fn)
        if not os.path.exists(p):
            stale.append("%s (no file)" % fn); continue
        lines = open(p, encoding="utf-8").read().splitlines()
        if ln > len(lines) or not re.search(r'objectFit\s*:\s*"cover"', lines[ln - 1]):
            stale.append("%s:%d" % (fn, ln))
    leg("L4 no_stale_pins", not stale, "stale: %s" % (stale or "none"))

    # L5 repo-wide: a cover anywhere in port/bodies is either pinned or a zoom
    # failure already caught above. This is what catches a NEW body shipping cover.
    everywhere = []
    for fn in sorted(os.listdir(BODIES)):
        if not fn.endswith(".jsx"):
            continue
        for i, line in enumerate(open(os.path.join(BODIES, fn), encoding="utf-8")
                                 .read().splitlines(), 1):
            if re.search(r'objectFit\s*:\s*"cover"', line) and (fn, i) not in PINNED_COVER:
                everywhere.append("%s:%d" % (fn, i))
    leg("L5 no_unpinned_cover_anywhere", not everywhere, "unpinned: %s" % (everywhere or "none"))

    print("%d/%d legs ok" % (6 - len(FAILS), 6))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
