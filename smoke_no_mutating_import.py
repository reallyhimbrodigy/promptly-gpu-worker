#!/usr/bin/env python3
"""A red proof must not run its mutations merely by being imported.

38 OF 63 DO. They have no `if __name__ == "__main__"` guard and every one of
them makes a module-level call, so `import red_proof_x` EXECUTES A MUTATING
HARNESS. I found that by doing it: measuring the stale-.pyc exposure, I imported
each proof to read its MUTATIONS list and one fired mid-measurement and printed
its tally into my output.

The tree came back clean because it restored correctly. THAT IS LUCK, NOT
DESIGN — a kill between mutate and restore leaves the mutant on disk, which is
the interrupted-fixture case no relocation reaches.

Nothing in this lane imports a red proof today, so it is LATENT rather than
live: one importlib away in whatever census or sweep gets written next, which is
exactly how it found me.

── A RATCHET, AND NAMED AS ONE ─────────────────────────────────────────────

It fails only if the count GROWS. Wrapping 38 files means moving each one's
top-level call inside a guard, a per-file edit that breaks the proof silently if
done wrong — that is a dedicated pass, not the tail of a session. A ceiling stops
the bleeding honestly; pretending 38 is acceptable would be the lie.

── AND IT READS BY AST, NEVER BY IMPORT ────────────────────────────────────

A checker for "this file runs on import" that imports the file to find out is
the defect performing itself.
"""
import ast
import glob
import io
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

# MEASURED 2026-09-22. A CEILING, not a target.
UNGUARDED_ON_IMPORT_TODAY = 38

FAILS = []
NLEGS = 0


def leg(name, ok, got):
    global NLEGS
    NLEGS += 1
    print("  %-46s %s   %s" % (name, "ok " if ok else "FAIL", got))
    if not ok:
        FAILS.append(name)


def top_level_calls(path):
    """How many expressions execute at module level. HOISTED so the library
    check can be driven with a fixture instead of asserting a fact about one
    file that no mutation can make false."""
    t = ast.parse(io.open(path, encoding="utf-8").read())
    return len([n for n in t.body
                if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)])


def scan(root=None):
    """-> (runs_on_import, guarded, unparseable). AST only.

    TAKES A ROOT so the rule can be driven over a FIXTURE. Three of this file's
    four mutations came back NOT RED on the first attempt, all vacuous for one
    reason: the real population contains no file that violates the property, so
    LOOSENING the assertion admits nothing and the mutant passes. A rule can only
    be proven against a population that can break it.""" + ""
    root = root or HERE
    runs, guarded, bad = [], [], []
    for f in sorted(glob.glob(os.path.join(root, "red_proof_*.py"))):
        name = os.path.basename(f)
        try:
            tree = ast.parse(io.open(f, encoding="utf-8").read())
        except Exception as e:                                 # noqa: BLE001
            bad.append((name, str(e)))
            continue
        has_guard = any(isinstance(n, ast.If) and "__name__" in ast.dump(n.test)
                        for n in tree.body)
        # A GUARD IS NOT THE PROPERTY. The property is "does anything execute".
        # A file with no guard but no module-level call is harmless, and counting
        # it would inflate the number with files that need no work.
        top_calls = [n for n in tree.body
                     if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)]
        if has_guard or not top_calls:
            guarded.append(name)
        else:
            runs.append((name, len(top_calls)))
    return runs, guarded, bad


def main():
    runs, guarded, bad = scan()
    total = len(runs) + len(guarded) + len(bad)

    # L0 A CHECK OVER AN EMPTY POPULATION ASSERTS NOTHING.
    leg("L0 population_present", total >= 40 and not bad,
        "%d red proof(s); unparseable: %s" % (total, bad or "none"))

    # L1 THE CEILING HOLDS. Fails only on GROWTH.
    leg("L1 unguarded_count_does_not_grow",
        len(runs) <= UNGUARDED_ON_IMPORT_TODAY,
        "%d run on import, ceiling %d%s"
        % (len(runs), UNGUARDED_ON_IMPORT_TODAY,
           "" if len(runs) <= UNGUARDED_ON_IMPORT_TODAY else "  <-- GREW"))

    # L2 THE COUNT MEANS WHAT IT SAYS, DRIVEN ON A FIXTURE that contains the
    # violating case the real population does not: a file with NO guard and NO
    # module-level call, which is harmless and must not be counted. A count
    # padded with harmless files cannot be driven to zero and stops being read.
    with tempfile.TemporaryDirectory() as tmp:
        w = lambda n, body: io.open(os.path.join(tmp, n), "w", encoding="utf-8").write(body)
        w("red_proof_guarded.py", 'def main():\n    pass\n\n\nif __name__ == "__main__":\n    main()\n')
        w("red_proof_runs.py", "def main():\n    pass\n\n\nmain()\n")
        w("red_proof_harmless.py", "X = 1\n\n\ndef main():\n    pass\n")
        w("red_proof_broken.py", "def main(:\n")
        fr, fg, fb = scan(tmp)
        names = sorted(n for n, _c in fr)
        leg("L2 only_files_that_execute_are_counted",
            names == ["red_proof_runs.py"] and "red_proof_harmless.py" in fg
            and len(fb) == 1,
            "counted=%s guarded=%d unparseable=%d" % (names, len(fg), len(fb)))

    # L2b AND THE REAL POPULATION AGREES WITH THAT RULE.
    leg("L2b every_counted_file_really_executes",
        bool(runs) and all(c > 0 for _n, c in runs),
        "%d counted, all with >=1 top-level call" % len(runs))

    # L3 THE SHARED LIBRARY IS SAFE TO IMPORT. 15 proofs import
    # red_proof_anchor; if IT ran on import, importing any of them would fire it.
    # DRIVEN ON A FIXTURE FIRST, because asserting a fact about one real file
    # cannot be mutation-proven: red_proof_anchor already has zero calls, so
    # loosening the check admits nothing and the mutant passes.
    with tempfile.TemporaryDirectory() as tmp:
        safe = os.path.join(tmp, "lib_safe.py")
        unsafe = os.path.join(tmp, "lib_unsafe.py")
        io.open(safe, "w", encoding="utf-8").write("def f():\n    pass\n")
        io.open(unsafe, "w", encoding="utf-8").write("def f():\n    pass\n\n\nf()\n")
        leg("L3 library_call_detector_discriminates",
            top_level_calls(safe) == 0 and top_level_calls(unsafe) == 1,
            "safe=%d unsafe=%d" % (top_level_calls(safe), top_level_calls(unsafe)))

    # L3b AND THE REAL SHARED LIBRARY IS SAFE. 15 proofs import
    # red_proof_anchor; if IT ran on import, importing any of them would fire it.
    anchor = os.path.join(HERE, "red_proof_anchor.py")
    n_anchor = top_level_calls(anchor) if os.path.isfile(anchor) else 0
    leg("L3b shared_anchor_library_is_import_safe", n_anchor == 0,
        "red_proof_anchor top-level calls: %d" % n_anchor)

    # L4 THIS CHECKER NEVER IMPORTS WHAT IT INSPECTS. A checker for "runs on
    # import" that imports the file to find out is the defect performing itself.
    me = io.open(os.path.join(HERE, "smoke_no_mutating_import.py"),
                 encoding="utf-8").read()
    mytree = ast.parse(me)
    imports = {a.name.split(".")[0]
               for n in ast.walk(mytree) if isinstance(n, ast.Import)
               for a in n.names}
    imports |= {(n.module or "").split(".")[0]
                for n in ast.walk(mytree) if isinstance(n, ast.ImportFrom)}
    leg("L4 checker_imports_nothing_it_inspects",
        not any(i.startswith("red_proof") for i in imports)
        and "importlib" not in imports,
        "imports: %s" % sorted(i for i in imports if i))

    print("%d/%d legs ok" % (NLEGS - len(FAILS), NLEGS))
    if FAILS:
        print("FAILED: %s" % ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
