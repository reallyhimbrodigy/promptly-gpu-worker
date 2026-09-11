#!/usr/bin/env python3
"""pyflakes over the lane's run-breaking classes.

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
sys.exit(1 if fail else 0)
