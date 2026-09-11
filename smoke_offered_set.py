#!/usr/bin/env python3
"""Purpose maps to an OFFERED set the agent chooses within — never a rule.

ZAC, 2026-09-10: "purpose maps to an offered set the agent chooses within,
with a reason — not a harness decision." The same corpus produced the
reference rates, and those were ruled GRADE-ONLY for exactly this reason: a
set the harness enforces is the harness editing.

WHAT THE SEED HID, and why this check exists at all. reference_index.json
carried 39 of 153 beats. On those 39 cutaway appeared only on evidence and
turn. On all 153 it is on ALL SEVEN purposes — 72 of 153, the most-used
visual move in the corpus. A surface derived from the seed would have withheld
the family that had just been built from five of the seven moments where
editors actually use it. So this asserts the derivation runs on the FULL
index, and that it is offered rather than enforced.
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import modal_stub                                                # noqa: E402
modal_stub.install()
import agentic_editor_app as A                                   # noqa: E402

fail = 0
_b, _meta = A.load_reference_index()

# 1. the FULL corpus, not a seed
if len(_b) < (_meta.get("beats_in_corpus") or 0):
    print(f"  *** the index carries {len(_b)} of "
          f"{_meta.get('beats_in_corpus')} beats — a derivation on a seed is "
          f"a derivation on a differently-shaped corpus, not a smaller one")
    fail += 1

# 2. every purpose has an offered set with a denominator, and cutaway is
#    offered at every purpose the corpus uses it at
for _p in A.BEAT_PURPOSES:
    _f, _n = A.offered_treatments(_p, _b)
    if _n <= 0:
        print(f"  *** purpose {_p!r} has no beats in the corpus")
        fail += 1
    if not _f:
        print(f"  *** purpose {_p!r} offers nothing from {_n} beats")
        fail += 1
    for _fam, _k in _f.items():
        if _k > _n:
            print(f"  *** {_p}: {_fam} counted {_k} of {_n} — a count above "
                  f"its own denominator")
            fail += 1
_cut_purposes = [p for p in A.BEAT_PURPOSES
                 if A.offered_treatments(p, _b)[0].get("cutaway")]
if len(_cut_purposes) < 7:
    print(f"  *** cutaway is offered at {len(_cut_purposes)} of 7 purposes "
          f"({_cut_purposes}) — on the full corpus it is on all seven, and a "
          f"surface that says otherwise is reading the seed")
    fail += 1

# 3. a family the corpus never uses is never offered
for _p in A.BEAT_PURPOSES:
    if A.offered_treatments(_p, _b)[0].get("transition"):
        print(f"  *** transition offered at {_p} — it is 0 of 153 in the corpus")
        fail += 1

# 4. OFFERED, NOT ENFORCED: nothing may reject or drop a ruling for being
#    outside the set. Checked on the AST of the whole module.
_tree = ast.parse(open(os.path.join(HERE, "agentic_editor_app.py")).read())
_callers = [n for n in ast.walk(_tree)
            if isinstance(n, ast.Call)
            and getattr(n.func, "id", "") == "offered_treatments"]
if not _callers:
    print("  *** offered_treatments is never called — a surface nobody reads")
    fail += 1
for _fn in [n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)]:
    _uses = any(isinstance(n, ast.Call)
                and getattr(n.func, "id", "") == "offered_treatments"
                for n in ast.walk(_fn))
    if not _uses:
        continue
    for _n in ast.walk(_fn):
        if isinstance(_n, ast.Call) and getattr(_n.func, "id", "") in (
                "fail",) and _fn.name != "_reference_block":
            print(f"  *** {_fn.name} both derives the offered set and fail()s "
                  f"— that is enforcement wearing an offer's clothes")
            fail += 1

# 5. it reaches the agent, with the denominator and the refusal to be a quota
_blk = A._reference_block([{"i": 0, "t_start": 0.0, "t_end": 3.0}])
if "REACHED FOR HERE" not in _blk:
    print("  *** the offered set never reaches the brief")
    fail += 1
if "not a quota" not in _blk:
    print("  *** the brief does not say the set is not a quota — the rates "
          "were ruled grade-only for this exact reason")
    fail += 1
if "never here:" not in _blk:
    print("  *** absences are not named — a list that quietly omits a family "
          "tells the agent less than one that says it was never used")
    fail += 1

print(f"smoke_offered_set: {len(_b)} beats, "
      f"cutaway at {len(_cut_purposes)}/7 purposes, {fail} wrong")
sys.exit(1 if fail else 0)
