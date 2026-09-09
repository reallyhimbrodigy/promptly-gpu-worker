#!/usr/bin/env python3
"""Every shape the catalogue ADVERTISES must be a shape place_sfx ACCEPTS.

THE BUG THIS PINS, observed in round 41 on talking_head. The sanitiser was

    nm = re.sub(r"[^A-Za-z0-9_-]", "", str(name or ""))

which strips the dot. _asset_inventory.json advertises `sfx.files` WITH
extensions — 'boom.mp3', 'money-ching.mp3' — and the membership test compares
against os.path.splitext-stripped stems. So the agent sends the name it was
shown, the sanitiser turns 'money-ching.mp3' into 'money-chingmp3', and it can
never match anything. Two of four ruled sfx were lost that way in one run:

    place_sfx failed: 'money-chingmp3' is not in the catalogue
    place_sfx failed: 'boommp3' is not in the catalogue

It is the card-props defect one family over: the agent used the shape it was
given and the code rejected that shape. "Educate rather than validate applies to
SHAPES" — and the corollary is that the shape you PUBLISH is the shape you must
ACCEPT. A refusal that is technically correct still loses the placement.

DRIVEN BY THE REAL CATALOGUE, not by hand-picked strings: every file in the
shipped inventory is checked in both the form it is advertised in and its stem.
A new sound with a dot, a dash or a digit is covered the day it is added, which
is the only way this does not rot.

  python3 smoke_sfx_name_shapes.py     exit 0 = every advertised shape resolves
"""
import json
import os
import sys

import agentic_editor_app as app

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    inv = json.load(open(os.path.join(HERE, "_asset_inventory.json")))
    files = list(((inv or {}).get("sfx") or {}).get("files") or [])
    if not files:
        print("FAIL: inventory advertises no sfx files — nothing to check")
        return 1
    stems = {os.path.splitext(f)[0] for f in files}

    if not hasattr(app, "sfx_catalogue_name"):
        print("FAIL: agentic_editor_app.sfx_catalogue_name does not exist.")
        print("      The normalisation is still inline in place_sfx, where no")
        print("      test can reach it — the same state sfx_start_s was hoisted")
        print("      out of, and the reason this bug shipped unseen.")
        return 1
    norm = app.sfx_catalogue_name

    fails = []
    print(f"{len(files)} advertised sound(s); each checked in both shapes\n")
    for f in sorted(files):
        stem = os.path.splitext(f)[0]
        for shape, given in (("as advertised", f), ("stem only", stem)):
            got = norm(given)
            ok = got in stems
            if not ok:
                fails.append(f"{given!r} ({shape}) -> {got!r}, not in catalogue")
            print(f"  [{'ok' if ok else 'FAIL'}] {shape:14} {given:28} -> {got}")

    # The membership set itself must not be empty of the thing we resolved to.
    if norm("boom.mp3") != norm("boom"):
        fails.append("the two advertised shapes of one sound do not agree")

    # A name that is not a sound must still be refused — accepting more shapes
    # is not accepting anything. Path traversal must not survive normalisation.
    print()
    for bad in ("../../etc/passwd", "/assets/sounds/boom.mp3.exe", "", None,
                "no-such-sound"):
        got = norm(bad)
        refused = got not in stems
        # boom.mp3.exe splits to 'boom.mp3' -> must not resolve to 'boom'
        print(f"  [{'ok' if refused else 'FAIL'}] refuses        {str(bad):28} -> {got!r}")
        if not refused:
            fails.append(f"{bad!r} normalised to a REAL catalogue entry {got!r}")

    print()
    if fails:
        for f in fails:
            print(f"FAIL: {f}")
        return 1
    print(f"every advertised shape resolves; {len(files)} sound(s), both shapes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
