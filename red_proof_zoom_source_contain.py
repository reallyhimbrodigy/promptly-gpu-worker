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

# A MUTATED .py RE-RUN IN A SUBPROCESS CAN BE SERVED A STALE .pyc, AND THE
# MUTANT THEN REPORTS THE PREVIOUS MUTATION'S BEHAVIOUR.
#
# Python invalidates its bytecode cache on (mtime, size). A red proof writes a
# mutant, runs it, restores, writes the next — all inside one mtime second — so
# a size collision between two mutants serves the earlier one's .pyc to the
# later one's run. MEASURED HERE: red_proof_what_landed reported 6/7 with the
# cache live and 7/7 with PYTHONDONTWRITEBYTECODE=1, and the NOT RED mutation
# was failing a leg belonging to the PRECEDING mutation.
#
# That is a false NOT RED — a mutation that does bite, reported as one that
# does not — and the same mechanism can produce a false RED, which is worse.
# The guard costs nothing: the child never writes bytecode, so there is nothing
# stale to serve.
def _child_env():
    import os as _os
    e = dict(_os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


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
     "L4 pins_live_and_single",
     lambda s: 'objectFit: "cover", aspectRatio: "4 / 5"' in s),
    # A PINNED FILE GROWS A SECOND COVER. The old (file, line) pin licensed
    # exactly one site by accident of its key; keyed on the file, a second crop
    # would ride in free unless the count is asserted.
    ("pinned_file_grows_a_second_cover", "EmojiCard.jsx",
     '            objectFit: "cover", aspectRatio: "4 / 5" }} />',
     '            objectFit: "cover", aspectRatio: "4 / 5" }} />\n'
     '          {/* second crop nobody argued for */}\n'
     '          <Img src={still} style={{ objectFit: "cover" }} />',
     "L4 pins_live_and_single",
     lambda s: s.count('objectFit: "cover"') == 1),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
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
