#!/usr/bin/env python3
"""No undefined name, no BRANCH-BOUND read, no duplicate dict key.

THE DOCSTRING USED TO SAY "no use-before-assignment" AND PYFLAKES DOES NOT
DELIVER THAT. Verified by running it on the exact shape that collected 5/5
ok=False on round 66 — a name assigned only inside the `else:` arm of a
conditional, read unconditionally below it. `python3 -m pyflakes` exits 0.
It sees a name never assigned; it does not see one assigned on only some
paths. This lane lost a whole round to it with 108 green smokes and four
import-time certs, because nothing in the lane calls `edit()` — and I then
failed four attempts at a static check of my own (79, 34, 1326 and "many"
false positives) and dropped it rather than ship a checker that cries wolf.
Builder-2's `branch_bound_reads` is the one that discriminates, RED-proven
below on the shape it exists for AND on the two correct idioms it must not
flag.

So this gate runs `branch_bound_reads` from the app beside pyflakes, and the
docstring says what the gate actually does.

CLAUDE.md HAS RECORDED SINCE 2026-08-27 that a cert reasons about text and
only pyflakes sees scope — and nothing was ever wired to run it. `_k6_total`
was read at one line inside edit() and assigned thirty lines later: a
NameError on every job, carried for two commits, past ast.parse, the
import-time asserts, every smoke, every red proof and the pre-commit hook.
Each of those either PARSES or IMPORTS, and nothing executes that line outside
a real job.

GATES ONLY THE CLASSES THAT BREAK A RUN, and NAMES the tolerated ones so the
list cannot grow by shrug: f-strings without placeholders are cosmetic and are
listed here on purpose, with a count, so a new one is visible rather than
absorbed.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["agentic_editor_app.py", "handler.py", "modal_app.py",
         "moodreel_editor.py"]
# THESE BREAK A RUN — every one is a NameError, a SyntaxError, or a silent
# overwrite at the moment the line executes.
FATAL = (
    "undefined name",                    # _k6_total: NameError on every job
    "referenced before assignment",      # the same thing, seen from the flow
    "invalid syntax", "unexpected indent",
    "dictionary key",                    # a repeated key: the later value wins
    "shadowed by loop variable",         # an import rebound mid-loop
    "redefinition of unused",            # two defs, one name — lookup by name
)
# THESE DO NOT BREAK A RUN and are COUNTED, never hidden. Naming them is the
# point: an unclassified message fails, so the list cannot grow by shrug, and
# the counts move if anyone adds one.
TOLERATED = (
    "f-string is missing placeholders",
    "imported but unused",
    "assigned to but never used",
    "is unused: name is never assigned in scope",
)

fail, tol_n = 0, 0
for name in FILES:
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        continue
    r = subprocess.run([sys.executable, "-m", "pyflakes", p],
                       capture_output=True, text=True)
    for line in (r.stdout or "").splitlines():
        if any(t in line for t in TOLERATED):
            tol_n += 1
            continue
        if any(f in line for f in FATAL):
            print(f"  *** {line}")
            fail += 1
        else:
            print(f"  *** UNCLASSIFIED (neither fatal nor tolerated): {line}")
            fail += 1

# THE TOLERATED COUNT IS A BASELINE, not a shrug. If it grows, somebody added
# dead code and should say so; the number is printed on every run so the growth
# is visible without anyone diffing pyflakes output.
BASELINE_TOLERATED = 46
print(f"smoke_no_undefined_names: {len(FILES)} file(s), {fail} FATAL, "
      f"{tol_n} tolerated (baseline {BASELINE_TOLERATED})")
if tol_n > BASELINE_TOLERATED:
    print(f"  NOTE: tolerated findings grew {BASELINE_TOLERATED} -> {tol_n}. "
          f"Not fatal, not invisible.")

# ── THE CLASS PYFLAKES CANNOT SEE ─────────────────────────────────────────
# Driven from the app so the check exercises the SHIPPED rule, not a copy of
# it. Merged in from lane/duration-producer 2026-09-12; the `check`/`fails`
# scaffolding it was written against does not exist in this file, so it is
# wired to this file's own `fail` counter rather than pasted in hopefully.
import pathlib                                                  # noqa: E402
import modal_stub                                               # noqa: E402
modal_stub.install()
import agentic_editor_app as _AA_BB                             # noqa: E402


def check(what, passed, detail=""):
    global fail
    if not passed:
        print(f"  *** {what}" + (f"  [{detail}]" if detail else ""))
        fail += 1


_bb = _AA_BB.branch_bound_reads(pathlib.Path("agentic_editor_app.py").read_text())
check("no local is assigned in ONE arm of a conditional and read below it — "
      "the shape that collected 5/5 ok=False on round 66 and that pyflakes "
      "exits 0 on",
      not _bb,
      "; ".join("%s(): %s stored line %d, read line %d" % _r for _r in _bb))

# AND THE RULE ITSELF MUST STILL DISCRIMINATE. A checker that flags nothing
# is indistinguishable from one that is switched off, so drive it on the
# shape it exists for and on the correct idioms it must not flag.
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

if fail:
    print("NO-UNDEFINED-NAMES: FAIL")
    sys.exit(1)
print("NO-UNDEFINED-NAMES: PASS — %d file(s), zero run-breaking warnings, "
      "every remaining class named, and the branch-bound rule RED-proven"
      % len(FILES))
