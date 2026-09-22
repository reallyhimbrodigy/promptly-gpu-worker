#!/usr/bin/env python3
"""Run this lane's gates and EXIT NON-ZERO IF ANY FAILED.

WHY THIS FILE EXISTS. Every commit I made this session was ungated. The shape
was:

    for g in <sixteen gates>; do python3 $g.py; printf "exit=%s" $?; done
    git add -A && git commit ...

The `;` after `done` ends the list, so `git add -A && git commit` ran regardless
of what those sixteen exit codes were. I READ the printout each time and it was
green each time, so no bad commit came of it -- but a human reading printed exit
codes is a DISPLAY, not a gate. Verified rather than reasoned: a `false` in the
middle of that loop prints exit=1 and the commit point still reads `$?=0`.

Builder 1 hit the same class one turn earlier and worse. His verification chain
was `python3 -c "import proof_residue" && ... ; echo "exit=$?" && git commit` --
the import failed, the `&&` chain died, and the `;` RESTARTED it, so the echo
succeeded and git ran on an unverified tree. A module with a syntax error
shipped. `;` after `&&` discards exactly the protection the `&&` was there for.

Same family as reading an exit code through a pipe, which is already a standing
rule here: THE QUESTION IS ALWAYS WHETHER THE THING REPORTING IS THE THING BEING
MEASURED. A printf reports the gate. The shell reports the printf.

Use as `python3 run_gates.py && git commit ...`. Nothing enforces the `&&` --
.githooks is not this lane's region -- so what this file can do instead is
refuse to produce a green that is not earned, and carry its own denominator so
it cannot silently shrink to a subset that always passes.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# NAMED, NOT DISCOVERED, and the count is asserted. Discovery over *.py would
# sweep in every other lane's checks -- including the permanently-red ones -- and
# "a correct rule that arrives as a wave of red gets reverted, not investigated".
# But a hand-written list is the shape where a vanished member hides behind a
# passing total, so the count is a floor and every file must exist.
SMOKES = [
    "smoke_live_set",
    "smoke_zoom_source_contain",
    "smoke_transition_covers_canvas",
    "smoke_perceptibility_peaks",
    "smoke_proof_frame_recorded",
    "smoke_blend_mode_stripped",
    "smoke_poster_frame_legible",
    "smoke_sfx_loudness_states",
    "smoke_run_gates",
    "smoke_brief_composer",
    "smoke_no_use_before_define",
    "smoke_dispatch_classifier",
    "smoke_what_landed",
    "smoke_bake_guard",
    "smoke_no_mutating_import",
]
N_EXPECTED = 2 * len(SMOKES)


def gates():
    """Every smoke paired with its red proof.

    THE PAIRING IS THE POINT, not a convenience: a smoke with no red proof is a
    check that has never failed, which is not yet a check. Deriving the proof
    name from the smoke name means a deleted proof shows up as a MISSING FILE
    rather than as a suite that quietly got shorter.
    """
    out = []
    for s in SMOKES:
        out.append(s)
        out.append(s.replace("smoke_", "red_proof_", 1))
    return out


def missing(names):
    """Named gates with no file on disk. Hoisted so it can be driven."""
    return [n for n in names
            if not os.path.isfile(os.path.join(HERE, n + ".py"))]


def verdict(results):
    """(exit_code, summary) from {name: returncode}. Hoisted so it can be driven.

    The whole failure this file exists for is an aggregation that reports green
    on a non-green population, and that cannot be mutation-tested through the
    real gates -- they all pass, so breaking the aggregation changes nothing and
    the mutation is VACUOUS. Driven over a fixture in red_proof_run_gates.py
    instead, the same way the falsy-zero fix had to be.
    """
    bad = sorted(n for n, rc in results.items() if rc != 0)
    n = len(results)
    if n != N_EXPECTED:
        return 2, "HARNESS FAILURE: ran %d gate(s), expected %d" % (n, N_EXPECTED)
    if bad:
        return 1, "%d/%d green; FAILED: %s" % (n - len(bad), n, ", ".join(bad))
    return 0, "%d/%d green" % (n, n)


def main():
    names = gates()
    gone = missing(names)
    if gone:
        print("HARNESS FAILURE: %d named gate(s) have no file: %s"
              % (len(gone), ", ".join(gone)))
        return 2

    results = {}
    for n in names:
        # Bare, no pipe. The status of a pipeline is the status of its LAST
        # command, and that has cost this repo four wrong readings.
        p = subprocess.run([sys.executable, os.path.join(HERE, n + ".py")],
                           capture_output=True, text=True)
        results[n] = p.returncode
        print("  %-40s exit=%d" % (n, p.returncode))
        if p.returncode != 0:
            tail = ((p.stdout or "") + (p.stderr or "")).strip().splitlines()[-12:]
            for ln in tail:
                print("      | %s" % ln)

    rc, summary = verdict(results)
    print("\n%s" % summary)
    return rc


if __name__ == "__main__":
    sys.exit(main())
