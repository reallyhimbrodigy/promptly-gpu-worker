#!/usr/bin/env python3
"""RED proof for smoke_no_mutating_import.py.

`ceiling_goes_to_zero` is the REFUSED state Builder 1 asked for: a ceiling the
population cannot meet must fail loudly rather than be quietly impossible.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = os.path.join(HERE, "smoke_no_mutating_import.py")
WATCHED = ["smoke_no_mutating_import.py"]


def _child_env():
    # A mutated .py re-run in a subprocess can be served a STALE .pyc; measured
    # at up to two lost verdicts per proof, erratic across runs.
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


MUTATIONS = [
    # THE CEILING BECOMES UNMEETABLE. 38 files run on import; a ceiling of 0 is
    # the honest target and today's REFUSED state, and it must say so rather
    # than pass silently.
    ("ceiling_goes_to_zero", "smoke_no_mutating_import.py",
     "UNGUARDED_ON_IMPORT_TODAY = 38", "UNGUARDED_ON_IMPORT_TODAY = 0",
     "L1 unguarded_count_does_not_grow",
     lambda s: "UNGUARDED_ON_IMPORT_TODAY = 38" in s),
    # THE COUNT STOPS MEANING WHAT IT SAYS: files with no module-level call get
    # counted too, inflating the number with files that need no work and making
    # the ceiling undrivable.
    ("count_padded_with_harmless_files", "smoke_no_mutating_import.py",
     "        if has_guard or not top_calls:", "        if has_guard:",
     "L2 only_files_that_execute_are_counted",
     lambda s: "has_guard or not top_calls" in s),
    # THE SHARED LIBRARY CHECK GOES BLIND — if red_proof_anchor ever runs on
    # import, the fifteen proofs importing it all fire.
    # THE CALL DETECTOR GOES BLIND, so a library that DOES run on import reads
    # as safe and the fifteen proofs importing it all fire. Aimed at the
    # fixture leg, because the real anchor has zero calls and cannot break.
    ("library_call_detector_blind", "smoke_no_mutating_import.py",
     "    return len([n for n in t.body\n"
     "                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)])",
     "    return 0",
     "L3 library_call_detector_discriminates",
     lambda s: "isinstance(n.value, ast.Call)" in s),
    # THE POPULATION FLOOR GOES, so an empty scan reads as a clean bill.
    # THE FLOOR BECOMES UNMEETABLE — the mirror of ceiling_goes_to_zero, and
    # the biting direction: LOOSENING a floor the population already clears
    # admits nothing, so the mutation has to make the requirement impossible.
    ("population_floor_unmeetable", "smoke_no_mutating_import.py",
     "total >= 40 and not bad", "total >= 100000 and not bad",
     "L0 population_present",
     lambda s: "total >= 40 and not bad" in s),
]


def run_smoke():
    p = subprocess.run([sys.executable, SMOKE], capture_output=True, text=True,
                       env=_child_env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def snapshot(paths):
    return {q: open(os.path.join(HERE, q), "rb").read() for q in paths}


def residue(base):
    return sorted(q for q, b in base.items()
                  if open(os.path.join(HERE, q), "rb").read() != b)


def main():
    rc, out = run_smoke()
    if rc != 0:
        print("HARNESS FAILURE: unmutated gate is not green (rc=%d)" % rc)
        print(out[-1200:])
        return 2
    print("baseline green.\n")
    base = snapshot(WATCHED)

    red = 0
    for name, target, old, new, phrase, pre in MUTATIONS:
        path = os.path.join(HERE, target)
        src = open(path, encoding="utf-8").read()
        n = src.count(old)
        if n != 1:
            print("  %-34s HARNESS FAILURE  anchor %dx" % (name, n))
            continue
        if pre is not None and not pre(src):
            print("  %-34s HARNESS FAILURE  VACUOUS precondition" % name)
            continue
        mutant = src.replace(old, new, 1)
        try:
            compile(mutant, path, "exec")
        except SyntaxError as e:
            print("  %-34s HARNESS FAILURE  will not parse (%s)" % (name, e))
            continue
        open(path, "w", encoding="utf-8").write(mutant)
        try:
            mrc, mout = run_smoke()
        finally:
            open(path, "w", encoding="utf-8").write(src)
        fired = re.search(r"^\s+%s\s+FAIL" % re.escape(phrase), mout, re.M) is not None
        ok = mrc != 0 and fired
        print("  %-34s %s  rc=%d phrase=%s" % (name, "RED " if ok else "NOT RED", mrc, fired))
        if ok:
            red += 1
        r = residue(base)
        if r:
            print("     RESIDUE after %s: %s" % (name, r))
            return 2

    ok = bool(MUTATIONS) and red == len(MUTATIONS)
    print("\n%d/%d RED-proven" % (red, len(MUTATIONS)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
