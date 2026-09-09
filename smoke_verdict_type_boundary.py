#!/usr/bin/env python3
"""A ruling with the wrong TYPES is rejected loudly, and no garbage becomes a family.

WHY. Round 46, talking_head, printed this and went green on it:

    RULED vs BUILT : a 3->0 GAP  c 3->0 GAP  card 0->0  d 3->0 GAP  r 3->0 GAP
    [1] ['c', 'a', 'r', 'd']/keep  10 times a day workload. StatCard hero '10'.

The agent supplied `treatment` as the bare string "card" against a schema that
correctly declares an array (verified on the frozen tree). ONE missing check
produced TWO symptoms:

  * seven consumers do `for t in (v.get("treatment") or [])`, so the STRING was
    iterated into 'c','a','r','d';
  * led["ruled_vs_built"] keyed off set(_fam_ruled), so those letters became
    four reported FAMILIES each 3->0 with a GAP marker, while the real
    `card 0->0` read clean. Three cards ruled, ZERO built.
  * and the same payload BYPASSED THE DEDUP, because the ingest guard is
    `if _v.get("beat") in _seen` and _seen holds whatever type arrived:
        beat 1 (int) then beat "1" (str)  ->  2 STORED
    so beat 1 carried BOTH ['none'] and the corrupt ruling and every per-beat
    count in that round counted one beat twice.

TWO KINDS OF LEG, because the defect had two homes. The VALUE legs run the pure
boundary. The WIRING legs read the AST of the reporting layer — which lives
inside edit() and cannot be called — because a correct boundary that the report
ignores changes nothing, and the report is where the phantom families appeared.

  python3 smoke_verdict_type_boundary.py     exit 0
"""
import ast
import os
import sys

import agentic_editor_app as app

fails = []
HERE = os.path.dirname(os.path.abspath(__file__))


def check(label, ok, detail=""):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        fails.append(label)


if not hasattr(app, "normalise_verdict"):
    print("  [FAIL] normalise_verdict does not exist")
    sys.exit(1)
nv = app.normalise_verdict

print("VALUE legs — the exact round-46 payload:")
ok, rec, why = nv({"beat": 1, "treatment": "card", "why": "x"})
check("a bare-string treatment is REJECTED, not coerced", not ok,
      why[:70] if why else "")
check("the rejection names the characters it would have become",
      not ok and ("'a'" in why or "a'," in why or "sorted" in why or "character" in why),
      why[:70])
ok2, rec2, _ = nv({"beat": "1", "treatment": ["none"]})
check("a string beat index is NORMALISED to int (closes the dedup bypass)",
      ok2 and isinstance(rec2.get("beat"), int) and rec2["beat"] == 1,
      f"{type(rec2.get('beat')).__name__ if ok2 else 'rejected'}")
check("an unknown family is REJECTED", not nv({"beat": 2, "treatment": ["carrd"]})[0])
check("a non-string inside the list is REJECTED",
      not nv({"beat": 3, "treatment": ["text", 7]})[0])
check("a legal ruling PASSES and is lower-cased",
      nv({"beat": 4, "treatment": ["TEXT", "zoom"]})[1]["treatment"] == ["text", "zoom"])
check("an empty treatment is legal ([] is a real answer)",
      nv({"beat": 5, "treatment": []})[0])
check("['none'] is legal", nv({"beat": 6, "treatment": ["none"]})[0])
check("a non-object verdict is REJECTED", not nv("nope")[0])
check("a missing beat is REJECTED", not nv({"treatment": ["text"]})[0])
# THE DEDUP, end to end: the two shapes must collide after normalisation.
a1 = nv({"beat": 1, "treatment": ["none"]})[1]
a2 = nv({"beat": "1", "treatment": ["text"]})[1]
check("two rulings for one beat COLLIDE after normalisation",
      a1["beat"] == a2["beat"], f"{a1['beat']!r} vs {a2['beat']!r}")

print("\nWIRING legs — the reporting layer must not invent a family:")
tree = ast.parse(open(os.path.join(HERE, "agentic_editor_app.py"),
                      encoding="utf-8").read())
src = open(os.path.join(HERE, "agentic_editor_app.py"), encoding="utf-8").read()
# DERIVED, NOT RESTATED. This leg used to carry its own literal copy of the
# family set, so adding `cutaway` broke it in a way that said nothing about the
# property — it went red because a SECOND list had gone stale, which is the
# duplication the alias exists to prevent. What this leg actually cares about is
# that TREATMENT_FAMILIES is a closed tuple over the ONE source of truth;
# smoke_five_families is where the membership itself is asserted, once.
check("TREATMENT_FAMILIES is a closed tuple aliasing _TREATMENT_FAMILIES",
      isinstance(getattr(app, "TREATMENT_FAMILIES", None), tuple)
      and set(app.TREATMENT_FAMILIES) == set(app._TREATMENT_FAMILIES)
      and len(app.TREATMENT_FAMILIES) == len(app._TREATMENT_FAMILIES),
      str(getattr(app, "TREATMENT_FAMILIES", None)))
check("the family set is non-trivial (an empty alias would pass the leg above)",
      len(app.TREATMENT_FAMILIES) >= 5, str(len(app.TREATMENT_FAMILIES)))
check("verdict_family_unknown is a CONTRACT_FAILURES member",
      "verdict_family_unknown" in app.CONTRACT_FAILURES)
# ruled_vs_built must key off the CLOSED set, never off whatever arrived —
# asked of the AST, because the comment ABOVE the fixed line quotes the old
# expression and a substring search flags it. (That is what the first version of
# this leg did, on a tree where the code was already correct.)
_iters = []
for _n in ast.walk(tree):
    if not isinstance(_n, ast.Assign):
        continue
    _t0 = _n.targets[0]
    if not (isinstance(_t0, ast.Subscript)
            and isinstance(_t0.slice, ast.Constant)
            and _t0.slice.value == "ruled_vs_built"):
        continue
    if isinstance(_n.value, ast.DictComp):
        for _g in _n.value.generators:
            _iters.append({x.id for x in ast.walk(_g.iter)
                           if isinstance(x, ast.Name)})
check("ruled_vs_built is a comprehension over a closed set", len(_iters) == 1,
      f"{len(_iters)} generator source(s) found")
if _iters:
    check("its iterable is TREATMENT_FAMILIES, not _fam_ruled",
          "TREATMENT_FAMILIES" in _iters[0] and "_fam_ruled" not in _iters[0],
          f"names in the iterable: {sorted(_iters[0])}")
# The unknown-family failure must be RAISED, not merely defined.
_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
          and getattr(n.func, "id", "") == "fail"
          and n.args and isinstance(n.args[0], ast.Constant)
          and n.args[0].value == "verdict_family_unknown"]
check("fail('verdict_family_unknown', ...) is actually CALLED", len(_calls) == 1,
      f"{len(_calls)} call(s)")
# And the ingest must go through the boundary.
_nvc = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and getattr(n.func, "id", "") == "normalise_verdict"]
check("the ingest CALLS normalise_verdict", len(_nvc) == 1, f"{len(_nvc)} call(s)")
check("rejections are PRINTED, not only ledgered",
      "verdict REJECTED" in src)

print()
if fails:
    print(f"{len(fails)} failure(s)")
    sys.exit(1)
print("wrong types are rejected loudly and no garbage becomes a family")
