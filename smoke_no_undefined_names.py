#!/usr/bin/env python3
"""No undefined name, no use-before-assignment, no duplicate dict key.

WHY THIS EXISTS, and it is the second time the class has been named here.
CLAUDE.md already records that "pyflakes caught a definition placed after its
callers AND a local that rebound the name" — and then nothing was wired to run
pyflakes, so the next instance shipped the same way.

2026-09-11: `_k6_total` was READ at line 11481 inside `edit()` and ASSIGNED at
11515. That is a NameError on every single run. It passed `ast.parse`, passed
the import-time asserts, passed 14 smokes and 6 red proofs, and passed the
pre-commit hook — because NOTHING EXECUTES THAT LINE outside a real job, and
every check in this repo either parses the file or imports it. A live path was
broken for two commits and the only thing that noticed was a pyflakes run I
happened to do by hand.

Also caught the same minute: `"beat"` added twice to one dict literal, because
Builder-1's zoom wiring already carried it and my commit message claimed a
change that was, for that family, a duplicate key.

SCOPED DELIBERATELY. This file has ~20 f-string-without-placeholder warnings
and several unused imports, and a gate that is always red stops being read —
the twin rule to "a check that has never failed is not yet a check". So the
allowed classes are listed HERE, by name, and anything outside the list fails.
Growing that list is an argument on the record, not a shrug.

RED-proven by red_proof_no_undefined_names.py.
"""
import pathlib
import subprocess
import sys

FILES = ["agentic_editor_app.py", "judge_placements.py", "modal_stub.py",
         "build_asset_inventory.py"]
# Warnings this file deliberately does not gate. Every entry is a class that is
# noisy in this repo and cannot break a run on its own.
TOLERATED = (
    "imported but unused",
    "f-string is missing placeholders",
    "unable to detect undefined names",
    "redefinition of unused",
    "is assigned to but never used",
    "may be undefined, or defined from star imports",
)
# Classes that BREAK A RUN and must be zero.
FATAL = (
    "undefined name",
    "local variable",                 # ...referenced before assignment
    "dictionary key",                 # ...repeated with different values
    "syntax error",
    "expected an indented block",
)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_have = subprocess.run([sys.executable, "-m", "pyflakes", "--version"],
                       capture_output=True, text=True)
# ABSENT IS NOT CLEAN. A missing linter and a clean file are different facts,
# and only one of them is good news.
check("pyflakes is available to run", _have.returncode == 0,
      "without it this check cannot be made, and reporting PASS would be the "
      "absence-as-success defect this repo has paid for six times")
if _have.returncode != 0:
    print("\nNO-UNDEFINED-NAMES: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)

for _f in FILES:
    if not pathlib.Path(_f).exists():
        check(f"{_f} exists", False, "a file in the gate list is missing")
        continue
    _r = subprocess.run([sys.executable, "-m", "pyflakes", _f],
                        capture_output=True, text=True)
    _lines = [l for l in ((_r.stdout or "") + (_r.stderr or "")).splitlines() if l.strip()]
    _fatal = [l for l in _lines
              if any(k in l.lower() for k in FATAL)
              and not any(t in l for t in TOLERATED)]
    check(f"{_f}: no undefined name, use-before-assignment or duplicate key",
          not _fatal, "\n         ".join(_fatal[:6]))
    _unknown = [l for l in _lines
                if not any(t in l for t in TOLERATED)
                and not any(k in l.lower() for k in FATAL)]
    check(f"{_f}: no pyflakes class outside the declared lists",
          not _unknown,
          "an unclassified warning is neither tolerated nor gated — decide "
          "which it is:\n         " + "\n         ".join(_unknown[:6]))

print()
if fails:
    print("NO-UNDEFINED-NAMES: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("NO-UNDEFINED-NAMES: PASS — %d file(s), zero run-breaking warnings, and "
      "every remaining class named" % len(FILES))
