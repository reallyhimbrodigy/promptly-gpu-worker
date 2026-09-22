#!/usr/bin/env python3
"""RED proof for smoke_run_gates.py.

MUTATION 1 IS THE DEFECT THIS WHOLE PAIR EXISTS FOR, and it is the shape my
commit loop had: the failure is REPORTED IN THE TEXT and the exit code is 0.
`printf "exit=%d"` beside `git commit` is exactly that -- the number is on the
screen and nothing acts on it.

Every mutation here is aimed at a leg that drives a pure function over a
constructed population, because the real gates all pass: break the aggregation
and the suite still reports green, so a mutation aimed at the live run would be
byte-different and behaviourally identical. Second time today that decided a
design.
"""
import io
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
SMOKE = os.path.join(HERE, "smoke_run_gates.py")
WATCHED = ["run_gates.py", "smoke_run_gates.py"]

MUTATIONS = [
    # THE FAILURE IS NAMED AND THE EXIT IS GREEN. My loop printed exit=1 for a
    # failing gate and committed; this returns the FAILED list in the summary
    # and 0 beside it. A reader of the output sees the failure. The shell does
    # not, and the shell is what gates the commit.
    ("failure_reported_as_green", "run_gates.py",
     '        return 1, "%d/%d green; FAILED: %s" % (n - len(bad), n, ", ".join(bad))',
     '        return 0, "%d/%d green; FAILED: %s" % (n - len(bad), n, ", ".join(bad))',
     "L3 one_failure_fails_the_run",
     lambda s: 'if bad:' in s),
    # ONLY exit 1 COUNTS AS A FAILURE, so a HARNESS FAILURE (exit 2) -- the code
    # every one of these gates uses for "I could not run the measurement at
    # all" -- passes straight through as green. The worst possible half to miss:
    # exit 2 is the state that means nothing was measured.
    ("only_exit_one_counts_as_failure", "run_gates.py",
     "    bad = sorted(n for n, rc in results.items() if rc != 0)",
     "    bad = sorted(n for n, rc in results.items() if rc == 1)",
     "L3b failure_in_the_middle_fails_the_run",
     lambda s: "if rc != 0" in s),
    # THE COUNT FLOOR GOES, so a runner that executed a SUBSET reports green on
    # it -- the subset-as-total failure, which is how a suite rots down to the
    # checks that happen to pass.
    ("count_floor_removed", "run_gates.py",
     "    if n != N_EXPECTED:", "    if False:",
     "L4 short_population_is_harness_failure",
     lambda s: "if n != N_EXPECTED:" in s),
    # missing() STOPS LOOKING AT THE DISK. A deleted or renamed gate then drops
    # silently out of a suite whose total still looks respectable -- and L1
    # already caught this for real one minute ago, when red_proof_run_gates did
    # not yet exist.
    ("missing_goes_blind", "run_gates.py",
     '    return [n for n in names\n'
     '            if not os.path.isfile(os.path.join(HERE, n + ".py"))]',
     '    return []',
     "L5 missing_detects_an_absent_file",
     lambda s: "os.path.isfile(os.path.join(HERE" in s),
    # THE PAIRING DERIVATION BREAKS: every smoke maps to itself instead of to
    # its proof, so the suite would run the smokes twice and no red proof at
    # all -- sixteen executions, eight checks, and a green tally.
    ("pairing_derivation_breaks", "run_gates.py",
     '        out.append(s.replace("smoke_", "red_proof_", 1))',
     '        out.append(s)',
     "L0 every_smoke_has_a_red_proof",
     lambda s: 's.replace("smoke_", "red_proof_", 1)' in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True, env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot(paths):
    return {q: io.open(os.path.join(HERE, q), "rb").read() for q in paths}


def residue(base_bytes):
    """Content, not status -- porcelain cannot tell one dirty content from
    another, which is how a mutant's output reached a commit from the sfx proof
    earlier today."""
    return sorted(q for q, b in base_bytes.items()
                  if io.open(os.path.join(HERE, q), "rb").read() != b)


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1500:])
        return 2
    print("baseline green.\n")
    base_bytes = snapshot(WATCHED)

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = io.open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-34s HARNESS FAILURE  anchor %dx in %s" % (name, n, target))
            continue
        if pre is not None and not pre(src):
            print("  %-34s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-34s HARNESS FAILURE  mutant will not parse (%s)" % (name, e))
            continue
        io.open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            io.open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-34s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue(base_bytes)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
