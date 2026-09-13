#!/usr/bin/env python3
"""No undefined name, no BRANCH-BOUND read, no duplicate dict key.

THE DOCSTRING USED TO SAY "no use-before-assignment" AND PYFLAKES DOES NOT
DELIVER THAT. Verified by running it on the exact shape that collected 5/5
ok=False on round 66 — a name assigned only inside the `else:` arm of a
conditional, read unconditionally below it. `python3 -m pyflakes` exits 0.
It sees a name never assigned; it does not see one assigned on only some
paths. A peer lost a whole round to it with 108 green smokes and four
import-time certs, because nothing in that lane calls `edit()`.

So this gate now runs `branch_bound_reads` from the app beside pyflakes, and
the docstring says what the gate actually does.

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
# ── THE CLASS PYFLAKES CANNOT SEE ─────────────────────────────────────────
# Driven from the app so the check exercises the SHIPPED rule, not a copy.
import modal_stub                                              # noqa: E402,F401
import agentic_editor_app as _AA_BB                             # noqa: E402
_bb = _AA_BB.branch_bound_reads(pathlib.Path("agentic_editor_app.py").read_text())
check("no local is assigned in ONE arm of a conditional and read below it — "
      "the shape that collected 5/5 ok=False on round 66 and that pyflakes "
      "exits 0 on",
      not _bb,
      "; ".join("%s(): %s stored line %d, read line %d" % _r for _r in _bb))

# AND THE RULE ITSELF MUST STILL DISCRIMINATE. A checker that flags nothing
# is indistinguishable from one that is switched off, so drive it on the
# shape it exists for and on the correct idiom it must not flag.
_DANGER = "def f(x):\n    if x:\n        y = 1\n    return y\n"
_GUARD  = "def f(x):\n    if x:\n        y = 1\n    else:\n        return 0\n    return y\n"
_BOTH   = "def f(x):\n    if x:\n        y = 1\n    else:\n        y = 2\n    return y\n"
check("it fires on a name bound in only one arm and read below",
      bool(_AA_BB.branch_bound_reads(_DANGER)))
check("it does NOT fire on the early-return guard — a checker that cries "
      "wolf on a correct idiom gets switched off, and then the class returns",
      not _AA_BB.branch_bound_reads(_GUARD))
check("and not when both arms assign, which is always bound",
      not _AA_BB.branch_bound_reads(_BOTH))

if fails:
    print("NO-UNDEFINED-NAMES: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print("NO-UNDEFINED-NAMES: PASS — %d file(s), zero run-breaking warnings, and "
      "every remaining class named" % len(FILES))
