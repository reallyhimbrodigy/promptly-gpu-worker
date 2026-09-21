#!/usr/bin/env python3
"""RED proof for smoke_zoom_source_contain.py.

The mutations edit the BODIES, which is where the defect would really land — a
zoom body quietly going back to `cover`. Backups are in memory; the tree is
checked for residue after every mutation, because an in-memory restore does not
survive a SIGKILL and only a post-run tree check reaches that.

Each mutation carries the phrase its leg prints. A red whose output does not
contain that phrase is reported NOT RED: a crash and a caught defect exit the
same way.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BODIES = os.path.join(HERE, "port", "bodies")
SMOKE = os.path.join(HERE, "smoke_zoom_source_contain.py")

# (name, file, old, new, leg-phrase, precondition over the unmutated source)
MUTATIONS = [
    ("stepzoom_back_to_cover", "StepZoom.jsx",
     '          objectFit: "contain",', '          objectFit: "cover",',
     "L2 no_unpinned_cover_in_zooms",
     lambda s: s.count('objectFit: "contain"') == 1),
    ("smoothpush_back_to_cover", "SmoothPush.jsx",
     '          objectFit: "contain",', '          objectFit: "cover",',
     "L2 no_unpinned_cover_in_zooms",
     lambda s: s.count('objectFit: "contain"') == 1),
    # A body that loses its plate entirely must not pass as "no cover found".
    ("depthpull_loses_its_plate", "DepthPull.jsx",
     '            objectFit: "contain",', '            objectFit: "fill",',
     "L3 every_zoom_has_contain",
     lambda s: s.count('objectFit: "contain"') == 1),
    # A NON-ZOOM body shipping cover — the case L5 exists for.
    ("new_body_ships_cover", "FilmStrip.jsx",
     'objectFit: "contain", filter: correct }} />',
     'objectFit: "cover", filter: correct }} />',
     "L5 no_unpinned_cover_anywhere",
     lambda s: 'objectFit: "contain", filter: correct }} />' in s),
    # THE BUILT BLOB GOES STALE — the exact failure that happened: a body edited
    # and never rebuilt, every source-reading leg green, and port/build/ still
    # carrying the old code that is what actually registers.
    ("built_blob_goes_stale", "build/StepZoom.jsx",
     'objectFit: "contain"', 'objectFit: "cover"',
     "L6 built_blobs_in_sync",
     lambda s: 'objectFit: "contain"' in s),
    # AND THE MARKER SURVIVES INTO A BUILT BLOB — a component registered with
    # `// @@VELOCITY_CAP@@` still in it calls three undefined symbols.
    ("marker_survives_the_build", "build/SmoothPush.jsx",
     "  const rootStyle = {", "  // @@VELOCITY_CAP@@\n  const rootStyle = {",
     "L7 no_unsubstituted_marker",
     lambda s: "const rootStyle = {" in s),
    # A pin that no longer points at a cover is a stale argument.
    ("pin_goes_stale", "EmojiCard.jsx",
     '            objectFit: "cover", aspectRatio: "4 / 5" }} />',
     '            objectFit: "contain", aspectRatio: "4 / 5" }} />',
     "L4 no_stale_pins",
     lambda s: 'objectFit: "cover", aspectRatio: "4 / 5"' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain", "port/bodies", "port/build"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base = residue()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:]); return 2
    print("baseline green.\n")

    red = 0
    for name, fn, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, "port", fn) if fn.startswith("build/") else os.path.join(BODIES, fn)
        if not os.path.exists(path):
            print("  %-28s HARNESS FAILURE  no such body %s" % (name, fn)); continue
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-28s HARNESS FAILURE  anchor %dx in %s" % (name, n, fn)); continue
        if pre is not None and not pre(src):
            print("  %-28s HARNESS FAILURE  VACUOUS precondition" % name); continue
        open(path, "w", encoding="utf-8").write(src.replace(old, new, 1))
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-28s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r)); return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
