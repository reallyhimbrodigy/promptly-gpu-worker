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
# THE SURFACE IS READING THE WHOLE CORPUS, NOT A SEED — asked without naming
# which families, because the two facts this used to assert were facts about the
# SIX-WORD corpus and both are now false. It required cutaway at ALL SEVEN
# purposes (true when captions inflated every beat; the re-read puts cutaway on
# 3, concentrated on `evidence` where 22 of 45 beats carry one) and it required
# transition at NONE (`0 of 153` — the closed enum's shape, not the corpus's;
# transition now measures 16 occurrences across 8 of 10 videos).
#
# A smoke that hardcodes which families appear where has learned one corpus.
# The property is that the surface DISCRIMINATES between purposes — a seed or a
# broken mapping gives every purpose the same answer, or no answer.
_by_purpose = {p: A.offered_treatments(p, _b)[0] for p in A.BEAT_PURPOSES}
_distinct = {tuple(sorted(v)) for v in _by_purpose.values()}
if len(_distinct) < 3:
    print(f"  *** only {len(_distinct)} distinct offered set(s) across 7 "
          f"purposes — the surface is not discriminating, which is what a "
          f"seed, an empty map or a single dominant family looks like")
    fail += 1
_fams_seen = set().union(*_by_purpose.values()) if _by_purpose else set()
if len(_fams_seen) < 3:
    print(f"  *** only {sorted(_fams_seen)} ever offered — a corpus this size "
          f"reaching under three families means the capability map is not "
          f"matching the corpus names")
    fail += 1
# AND EVERY OFFERED FAMILY MUST BE ONE THE PIPELINE CAN RULE.
_rulable = {f for f in A._rulable_treatments() if f != "none"}
_alien = _fams_seen - _rulable
if _alien:
    print(f"  *** {sorted(_alien)} are offered but are not rulable families — "
          f"the corpus vocabulary is leaking through the capability map")
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
# DRIVEN WITH A BEAT AT EVERY PURPOSE. A single purposeless beat renders no
# REACHED FOR HERE line at all, so these three legs were asserting against an
# empty block and would pass or fail for reasons unrelated to the offered set.
_blk = A._reference_block(
    [{"i": _i, "purpose": _p, "t_start": float(_i), "t_end": float(_i) + 2.0,
      "role": _p, "text": "a line of speech"}
     for _i, _p in enumerate(A.BEAT_PURPOSES)])
if "REACHED FOR HERE" not in _blk:
    print("  *** the offered set never reaches the brief")
    fail += 1
if "not a quota" not in _blk:
    print("  *** the brief does not say the set is not a quota — the rates "
          "were ruled grade-only for this exact reason")
    fail += 1
# ABSENCES ARE NAMED WHEN THERE ARE ANY. Required unconditionally before —
# which assumed some family is unused at some purpose, true of the six-word
# corpus and not a property of surfaces in general. Compute whether any absence
# EXISTS, then require it to be named.
_any_absent = any(
    set(_rulable) - set(A.offered_treatments(_p, _b)[0]) - A.reference_unmeasurable()
    for _p in A.BEAT_PURPOSES)
if _any_absent and "never here:" not in _blk:
    print("  *** a rulable family is unused at some purpose and the surface "
          "does not say so — a list that quietly omits a family tells the "
          "agent less than one that says it was never used")
    fail += 1
if not _any_absent and "never here:" in _blk:
    print("  *** the surface claims a family is 'never here' when none is "
          "absent — that is the six-word reading coming back")
    fail += 1
# AND AN UNMEASURABLE FAMILY IS NAMED AS SUCH, never as never-used.
for _u in A.reference_unmeasurable():
    for _ln in _blk.splitlines():
        if "never here:" in _ln and _u in _ln.split("never here:")[1].split(
                ". Choose among")[0]:
            print(f"  *** {_u!r} is unmeasurable and is being reported as "
                  f"never-used")
            fail += 1

print(f"smoke_offered_set: {len(_b)} beats, "
      f"{len(_distinct)} distinct offered set(s) over 7 purposes, "
      f"{len(_fams_seen)} famil(ies) seen, {fail} wrong")
sys.exit(1 if fail else 0)
