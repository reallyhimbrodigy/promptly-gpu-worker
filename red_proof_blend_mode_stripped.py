#!/usr/bin/env python3
"""RED proof for smoke_blend_mode_stripped.py.

The mutations remove the acknowledgements that were genuinely missing an hour
ago — the gate found all three on its first run — so it is proven against the
state the repo was actually in, not an invented one.
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
SMOKE = os.path.join(HERE, "smoke_blend_mode_stripped.py")

MUTATIONS = [
    # SOMEBODY ADDS A `screen` GLOW BACK. This is the realistic regression: the
    # declaration looks correct, reads correctly, and is inert.
    ("a_blend_comes_back", "port/bodies/ShutterFlashOverlay.jsx",
     "          opacity: beamOpacity }}>",
     '          opacity: beamOpacity, mixBlendMode: "screen" }}>',
     "L1 no_blend_declarations",
     lambda s: "opacity: beamOpacity }}>" in s),
    # ON A MENU COMPONENT. Retargeted to L1: the menu leg it used to name was a
    # strict SUBSET of L1, so this mutation went red on L1 and the menu leg was
    # never reached — rc=1 phrase=False, which is the signature of a red that is
    # not about the leg it claims. The menu leg is deleted; this one stays,
    # because a blend appearing on an offerable component is worth its own case.
    ("a_blend_comes_back_on_the_menu", "port/bodies/StickyNotes.jsx",
     '  const notes = [];',
     '  const notes = [];\n  const _x = { mixBlendMode: "screen" };',
     "L1 no_blend_declarations",
     lambda s: "const notes = [];" in s),
    # THE REASON IS DELETED and the next person re-adds a glow with nothing in
    # the tree to tell them why it cannot work.
    # AIMED AT ShutterFlash, WHICH CARRIES EXACTLY ONE. It was aimed at
    # DepthPull and passed: DepthPull states the finding TWICE — once in the
    # header and once beside the brightness filter — so deleting the header left
    # the second standing and the acknowledgement survived. The mutation changed
    # real bytes and could not change the verdict.
    ("the_reason_is_lost", "port/bodies/ShutterFlash.jsx",
     " * NO BLEND MODE DECLARED, DELIBERATELY. The beam and dot asked for `screen`\n * and ChatCut strips mixBlendMode at registration, so the declaration never\n * survived.",
     " * The beam and dot draw over the seam.",
     "L2 the_finding_is_recorded",
     lambda s: "NO BLEND MODE DECLARED, DELIBERATELY" in s),
    # THE DETECTOR GOES BLIND: with the pattern broken it finds nothing and
    # would report a clean corpus forever.
    ("detector_goes_blind", "smoke_blend_mode_stripped.py",
     "DECL = r'mixBlendMode:\\s*\"([a-z-]+)\"'",
     "DECL = r'mixBlendModeXX:\\s*\"([a-z-]+)\"'",
     "L3 detector_finds_a_known_positive",
     lambda s: "mixBlendMode:" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def residue():
    p = subprocess.run(["git", "status", "--porcelain",
                        "port/bodies", "smoke_blend_mode_stripped.py"],
                       cwd=HERE, capture_output=True, text=True)
    return p.stdout.strip()


def main():
    base = residue()
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-32s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-32s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            if target.endswith(".py"):
                compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-32s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-32s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue()
        if r != base:
            print("     RESIDUE after %s: %r" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
