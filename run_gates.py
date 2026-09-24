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
import shutil
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
    "smoke_menu_lines",
    "smoke_credit_prices",
    "smoke_sfx_levels",
    "smoke_baked_copy",
    "smoke_default_text",
    "smoke_pricing_model",
    "smoke_two_trees_agree",
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


# ── THE EIGHTH WAY A MUTATION STOPS MUTATING: A STALE .pyc ────────────────
#
# Found by Builder 1, 2026-09-24, and invisible to every guard either of us
# had. The anchor matches, the edit applies, the mutant is on disk — and the
# CHILD PROCESS IMPORTS A CACHED BYTECODE FILE OF THE ORIGINAL. CPython
# validates a cache on (mtime_seconds, size), so a mutation written in the
# same second as the restore, landing near the original's length, defeats
# both fields at once.
#
# IT WEARS THE WRONG COSTUME, WHICH IS WHAT MAKES IT EXPENSIVE. The symptom is
# `rc=1 phrase=False` — our own signature for "a red that is not about the
# property" — so the reflex is to re-aim a mutation that was never mis-aimed.
#
# `PYTHONDONTWRITEBYTECODE` IS THE WRONG GUARD AND SIX OF MY PROOFS CARRY IT.
# It stops the child WRITING a cache; it does not stop it READING one that is
# already there. Both halves are needed, and the clear has to come first.
#
# DONE HERE RATHER THAN IN 41 FILES. Forty-one red proofs mutate a .py module
# and they do not share a shape — six have an _env(), seventeen pass an env at
# all. Retrofitting each one is forty-one chances to get it wrong and no way
# to tell that it stayed right. Every one of them runs through THIS loop, so
# the cache is cleared once before any of them start and no child writes a new
# one. B1's advice was to stop triaging and put it in unconditionally; his
# resolver had already been wrong twice trying to separate the exposed
# population, and mine would be too.
def _clear_bytecode_caches():
    """Remove every __pycache__ under HERE. Returns how many were removed."""
    removed = 0
    for root, dirs, _files in os.walk(HERE):
        # do not descend into a worktree's own node_modules or .git
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        if os.path.basename(root) == "__pycache__":
            try:
                shutil.rmtree(root)
                removed += 1
            except OSError:
                pass
    return removed


def main():
    _n_caches = _clear_bytecode_caches()
    # PRINTED, because a guard nobody can see is a guard nobody maintains —
    # and because "0 removed" on a clean tree is a different fact from the
    # walk finding nothing.
    print("  bytecode caches cleared: %d" % _n_caches)
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
        # AND NO CHILD WRITES A NEW ONE. The clear above removes what exists;
        # this stops the next proof in the loop from leaving a cache that the
        # one after it could read.
        _env = dict(os.environ)
        _env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, os.path.join(HERE, n + ".py")],
                           capture_output=True, text=True, env=_env)
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
