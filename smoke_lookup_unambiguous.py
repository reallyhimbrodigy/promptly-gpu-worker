#!/usr/bin/env python3
"""Every function a check looks up BY NAME is defined exactly once.

WHY THIS EXISTS. Auditing my own files for the walk-order hazard turned up 24
sites of the shape

    next((n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "X"), None)

`ast.walk` does NOT yield source order, so `next(...)` returns whichever match
the traversal reached first. Today that is harmless — `agentic_editor_app.py`
defines no function name twice, so every one of those lookups is unambiguous.
**By construction, not by design.** Nobody checked it, and neither Builder-1 nor
I knew it was load-bearing until the hazard was named.

THE DAY SOMEONE ADDS A NESTED HELPER SHADOWING A MODULE-LEVEL NAME, all 24
silently start resolving to whichever the traversal happens to reach — and this
repo has already paid for that class twice under *scope is not text*: a
definition placed after its callers, and a local that rebound a name and
shadowed it for a whole function. A check reading the wrong definition reports
confidently about code that never runs.

TWO FAILURES, both silent, both caught here:

    DEFINED TWICE   the lookup is a coin flip decided by traversal order
    DEFINED ZERO    the lookup returns None and the check quietly asserts
                    nothing about a function that no longer exists

THE NAMES ARE DERIVED FROM THE CHECKS THEMSELVES, never hand-listed, so a new
lookup is covered the day it is written and a deleted one stops being demanded.

RED-proven by red_proof_lookup_unambiguous.py.
"""
import ast
import pathlib
import sys

APP = pathlib.Path("agentic_editor_app.py")
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


# ── what every check looks up by name ───────────────────────────────────────
# Matched on the COMPARISON `<anything>.name == "X"`, not on the surrounding
# next()/comprehension, so the extraction survives a rewrite of the wrapper.
_looked_up = {}
_files = sorted(list(pathlib.Path(".").glob("smoke_*.py"))
                + list(pathlib.Path(".").glob("cert_*.py"))
                + list(pathlib.Path(".").glob("red_proof_*.py")))
for _p in _files:
    if _p.name == "smoke_lookup_unambiguous.py":
        continue
    try:
        _t = ast.parse(_p.read_text())
    except SyntaxError:
        continue          # smoke_tree_parses owns "does it parse"
    for _n in ast.walk(_t):
        if not isinstance(_n, ast.Compare) or len(_n.comparators) != 1:
            continue
        if not (isinstance(_n.left, ast.Attribute) and _n.left.attr == "name"):
            continue
        _c = _n.comparators[0]
        if isinstance(_c, ast.Constant) and isinstance(_c.value, str):
            _looked_up.setdefault(_c.value, []).append(f"{_p.name}:{_n.lineno}")

check(f"the extraction found lookups ({len(_looked_up)} distinct name(s)) — "
      f"non-vacuity", len(_looked_up) >= 10,
      f"only {len(_looked_up)} found across {len(_files)} check file(s); the "
      f"matcher is probably wrong and this check forbids nothing")

# ── how many times the app defines each ─────────────────────────────────────
_app = ast.parse(APP.read_text())
_defs = {}
for _n in ast.walk(_app):
    if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _defs.setdefault(_n.name, []).append(_n.lineno)

_ambiguous, _absent = [], []
for _name, _sites in sorted(_looked_up.items()):
    _where = _defs.get(_name, [])
    if len(_where) > 1:
        _ambiguous.append(f"{_name!r} defined at {_where} — looked up by "
                          f"{', '.join(_sites[:3])}")
    elif not _where:
        # Not every `.name == "x"` is an app-function lookup — some check files
        # introspect each other or match ast node names. Only report a miss when
        # the name is looked up against something that reads like the app.
        if any("agentic_editor_app" in pathlib.Path(s.split(":")[0]).read_text()
               for s in _sites):
            _absent.append(f"{_name!r} is defined NOWHERE in the app — looked "
                           f"up by {', '.join(_sites[:3])}")

check("no name a check looks up is defined twice in the app", not _ambiguous,
      "\n         ".join(_ambiguous) + "\n         ast.walk does not yield "
      "source order, so next() would resolve to whichever the traversal reached "
      "first — a coin flip, reported confidently.")
check("no check looks up a function the app does not define", not _absent,
      "\n         ".join(_absent) + "\n         The lookup returns None and the "
      "check quietly asserts nothing.")

print()
if fails:
    print("LOOKUP-UNAMBIGUOUS: FAIL")
    for _f in fails:
        print("  - " + _f)
    sys.exit(1)
print(f"LOOKUP-UNAMBIGUOUS: PASS — {len(_looked_up)} name(s) looked up across "
      f"{len(_files)} check file(s); each defined exactly once in the app")
