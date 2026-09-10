#!/usr/bin/env python3
"""EVERY FUNCTION A CHECK LOOKS UP BY NAME IS DEFINED EXACTLY ONCE.

My checks locate functions with `next(n for n in ast.walk(t) if
isinstance(n, ast.FunctionDef) and n.name == "X")`. That is order-independent
ONLY BECAUSE the app defines no function name twice — a property that is
LOAD-BEARING FOR 15 LOOKUPS AND WAS NEVER STATED ANYWHERE.

Builder-2 has 23 sites resting on the same assumption and found it the same way:
safe by construction, construction unstated. Neither of us knew it was
load-bearing until we looked.

TWO SILENT FAILURES, and both render as a passing check:

  DEFINED TWICE  the lookup becomes a coin flip decided by TRAVERSAL ORDER, not
                 source order, and every leg then reports confidently about
                 whichever copy the walk reached first — possibly the one that
                 never runs. This repo has paid for the shadowing class twice
                 already: a definition placed after its callers, and a local
                 rebinding a name for a whole function. *Scope is not text.*

  DEFINED ZERO   `next(..., None)` returns None and the guarded legs silently
                 assert nothing about a function that no longer exists. That is
                 absence rendered as success, in the lookup itself.

THE NAMES ARE DERIVED FROM THE CHECKS, matched on the comparison
`<x>.name == "X"` rather than on the next()/comprehension wrapper — so this
survives a rewrite of the wrapper, covers a new lookup the day it is written,
and stops demanding a name whose check was deleted. Nobody maintains a list.

  python3 smoke_lookup_unambiguous.py    exit 0 = every lookup resolves to one
"""
import ast
import collections
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "agentic_editor_app.py")
FAIL = []

# ── what do the checks look up? ─────────────────────────────────────────────
looked = {}
for f in sorted(glob.glob(os.path.join(HERE, "smoke_*.py"))
                + glob.glob(os.path.join(HERE, "red_proof_*.py"))):
    try:
        tree = ast.parse(open(f, encoding="utf-8").read())
    except Exception:                                             # noqa: BLE001
        continue
    for n in ast.walk(tree):
        if (isinstance(n, ast.Compare) and isinstance(n.left, ast.Attribute)
                and n.left.attr == "name"):
            for c in n.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    looked.setdefault(c.value, set()).add(os.path.basename(f))

# ── how many times does the app define each? ────────────────────────────────
defs = collections.Counter()
for n in ast.walk(ast.parse(open(APP, encoding="utf-8").read())):
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        defs[n.name] += 1

app_names = [nm for nm in looked if nm in defs]
for nm in sorted(looked):
    if defs[nm] > 1:
        FAIL.append(
            f"{nm!r} is defined {defs[nm]} times in agentic_editor_app.py and "
            f"{len(looked[nm])} check(s) look it up by name "
            f"({', '.join(sorted(looked[nm]))}). The lookup resolves by "
            f"TRAVERSAL ORDER, not source order — those checks are reporting "
            f"about whichever copy the walk reached first, possibly the one "
            f"that never runs")

# DEFINED ZERO. A check may legitimately look up a name in its OWN file (a
# helper it defines) or in another module — so the test is: absent from the app
# AND absent from the file doing the looking.
#
# MY FIRST VERSION HAD A HOLE ITS OWN RED PROOF FOUND. It only flagged a missing
# name when the SAME FILE also looked up a name that resolved ("siblings"), as a
# proxy for "this file inspects the app". A check file that looks up EXACTLY ONE
# function had no siblings and therefore no coverage — which is most of them.
# Deleting count_cuts, a real looked-up function, did not fire it.
#
# A heuristic clever enough to need a proxy is a heuristic with a hole in it.
_self_defined = {}
for f in sorted(glob.glob(os.path.join(HERE, "smoke_*.py"))
                + glob.glob(os.path.join(HERE, "red_proof_*.py"))):
    try:
        _t = ast.parse(open(f, encoding="utf-8").read())
    except Exception:                                             # noqa: BLE001
        continue
    _self_defined[os.path.basename(f)] = {
        n.name for n in ast.walk(_t)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

for nm in sorted(looked):
    if nm in defs:
        continue
    # which of the looking files could NOT be talking about their own helper?
    _outside = sorted(f for f in looked[nm] if nm not in _self_defined.get(f, set()))
    if _outside:
        FAIL.append(
            f"{nm!r} is looked up by {', '.join(_outside)} and is DEFINED ZERO "
            f"TIMES in the app and in those files — next(..., None) returns "
            f"None and those legs assert nothing about a function that does not "
            f"exist. Absence rendered as success, inside the lookup itself")

print(f"LOOKUP-UNAMBIGUOUS  {len(looked)} name(s) looked up by checks, "
      f"{len(app_names)} of them app functions")
# A check over an empty population asserts nothing.
if len(app_names) < 5:
    FAIL.append(f"only {len(app_names)} app-function lookups found — the walk "
                f"is not reaching them and this check forbids nothing")
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("  every looked-up app function is defined exactly once")
