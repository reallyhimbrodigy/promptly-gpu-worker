#!/usr/bin/env python3
"""The plan survives re-segmentation and a changed cut, and loses nothing silently.

WHY SOURCE SPANS. Verdicts are keyed by beat INDEX and indices are derived per
run — round 48 moved a fixture 8 -> 9 beats when subdivision changed. An index
is a position in a list that is rebuilt every time. Source time is not: it is
the moment an editor ruled on, and neither re-segmentation nor a changed cut
moves it. Zac ruled a re-edit MAY change the cut, which makes output-second
anchoring wrong rather than merely worse.

WHAT THIS DRIVES, on the shipped functions rather than a copy:
  round trip        plan -> beats -> verdicts returns what went in
  RESEGMENTATION    the same plan lands correctly on a DIFFERENT beat list,
                    which is the property beat indices do not have
  ORPHAN            a verdict naming a beat that does not exist is REPORTED
  UNPLACEABLE       an entry no beat overlaps is REPORTED, never forced onto
                    the nearest beat — a ruling silently moved to a different
                    moment is worse than one the user is told was not carried
  id stability      the same ruling gets the same id across runs, and two
                    rulings on one beat get DIFFERENT ids

RED-proven by red_proof_durable_plan.py.
"""
import ast
import pathlib
import sys

src = pathlib.Path("agentic_editor_app.py").read_text()
tree = ast.parse(src)
fails = []


def check(label, cond, detail=""):
    if not cond:
        fails.append(label + (f"  :: {detail}" if detail else ""))
    print(f"  [{'ok' if cond else 'FAIL'}] {label}"
          + (f"\n         {detail}" if not cond and detail else ""))


_ns = {"hashlib": __import__("hashlib")}
_want = ("plan_anchor_id", "durable_plan", "plan_onto_beats")
for _n in tree.body:
    # TUPLE TARGETS COUNT. `PLAN_ORPHAN, PLAN_UNPLACEABLE = ...` has a Tuple
    # target, not a Name, so a `getattr(t, "id", "")` filter skips it silently —
    # and the function then raises NameError deep inside a leg. Walk the target.
    if isinstance(_n, ast.Assign) and any(
            getattr(_t2, "id", "") in ("PLAN_ORPHAN", "PLAN_UNPLACEABLE",
                                       "VERDICT_FIELDS")
            for t in _n.targets for _t2 in ast.walk(t)):
        try:
            exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
        except Exception:
            pass
    if isinstance(_n, ast.FunctionDef) and _n.name in _want:
        exec(compile(ast.Module([_n], []), "<c>", "exec"), _ns)
_ns.setdefault("VERDICT_FIELDS", ["beat", "treatment", "cut", "text_content"])
check("all three plan functions are module-level and drivable",
      all(k in _ns for k in _want), f"{[k for k in _want if k in _ns]}")
if not all(k in _ns for k in _want):
    print("\nDURABLE-PLAN: FAIL"); sys.exit(1)
_dp, _po, _pid = _ns["durable_plan"], _ns["plan_onto_beats"], _ns["plan_anchor_id"]

BEATS = [{"i": 0, "t_start": 0.0, "t_end": 4.0},
         {"i": 1, "t_start": 4.0, "t_end": 9.0},
         {"i": 2, "t_start": 9.0, "t_end": 14.0}]
VERDICTS = [{"beat": 0, "treatment": ["text"], "cut": "keep", "text_content": "A"},
            {"beat": 2, "treatment": ["zoom"], "cut": "keep", "text_content": ""}]

# ── 1. round trip ────────────────────────────────────────────────────────────
_plan, _probs = _dp(BEATS, VERDICTS)
check("every verdict becomes a plan entry", len(_plan) == 2 and not _probs,
      f"{len(_plan)} entries, problems={_probs}")
check("entries carry the SOURCE span, not the beat index",
      all("src_t0" in e and "src_t1" in e for e in _plan)
      and _plan[0]["src_t0"] == 0.0 and _plan[0]["src_t1"] == 4.0,
      f"{[(e.get('src_t0'), e.get('src_t1')) for e in _plan]}")
_back, _bp = _po(_plan, BEATS)
check("round trip returns the same beats", not _bp
      and sorted(v["beat"] for v in _back) == [0, 2],
      f"{[v.get('beat') for v in _back]} problems={_bp}")

# ── 2. THE PROPERTY INDICES DO NOT HAVE ─────────────────────────────────────
# The same plan onto a RESEGMENTED beat list. Beat 2 has been split, so the old
# index 2 now names a different moment — the anchor must still find the right one.
RESEG = [{"i": 0, "t_start": 0.0, "t_end": 4.0},
         {"i": 1, "t_start": 4.0, "t_end": 6.5},
         {"i": 2, "t_start": 6.5, "t_end": 9.0},
         {"i": 3, "t_start": 9.0, "t_end": 14.0}]
_re, _rp = _po(_plan, RESEG)
check("a resegmented beat list still places every entry", not _rp and len(_re) == 2,
      f"{_re} problems={_rp}")
check("the zoom lands on the beat covering 9.0-14.0, now index 3 not 2",
      any(v["beat"] == 3 and "zoom" in (v.get("treatment") or []) for v in _re),
      f"{[(v.get('beat'), v.get('treatment')) for v in _re]} — an index-keyed "
      f"plan would have put it on the 6.5-9.0 beat")

# ── 3. NOTHING IS LOST SILENTLY ─────────────────────────────────────────────
_p2, _pr2 = _dp(BEATS, VERDICTS + [{"beat": 99, "treatment": ["sfx"]}])
check("a verdict naming a nonexistent beat is REPORTED, not dropped",
      len(_p2) == 2 and len(_pr2) == 1
      and _pr2[0]["state"] == _ns.get("PLAN_ORPHAN", "ORPHAN_VERDICT"),
      f"plan={len(_p2)} problems={_pr2}")
_far = [dict(_plan[0], src_t0=100.0, src_t1=104.0)]
_v3, _pr3 = _po(_far, BEATS)
check("an entry no beat overlaps AT ALL is REPORTED",
      not _v3 and len(_pr3) == 1
      and _pr3[0]["state"] == _ns.get("PLAN_UNPLACEABLE", "UNPLACEABLE"),
      f"verdicts={_v3} problems={_pr3}")

# THE CASE THE FLOOR ACTUALLY EXISTS FOR, and my first version missed it. A
# zero-overlap entry is reported even with NO floor, because there is no beat to
# force it onto — so testing only that case proves nothing about the floor. The
# real risk is PARTIAL overlap: an entry that grazes a beat would be silently
# placed on it, moving a ruling to a moment the user did not choose. 13.0-21.0
# overlaps the 9.0-14.0 beat by 1.0s of its own 8.0s span — 12.5%, under the 50%
# floor. (Found by the red proof: removing the floor left this leg green.)
_graze = [dict(_plan[0], src_t0=13.0, src_t1=21.0)]
_v4, _pr4 = _po(_graze, BEATS)
check("an entry that only GRAZES a beat is REPORTED, not forced onto it",
      not _v4 and len(_pr4) == 1
      and _pr4[0]["state"] == _ns.get("PLAN_UNPLACEABLE", "UNPLACEABLE"),
      f"verdicts={_v4} problems={_pr4} — 12.5% coverage is under the floor, and "
      f"placing it would move the ruling to a moment the user did not choose")

# ── 4. ids ──────────────────────────────────────────────────────────────────
check("the same ruling gets the same id twice (stable across runs)",
      _pid(0.0, 4.0, "text", "A") == _pid(0.0, 4.0, "text", "A"))
check("two rulings on one beat get DIFFERENT ids",
      _pid(0.0, 4.0, "text", "A") != _pid(0.0, 4.0, "text", "B"))
check("a different span gets a different id",
      _pid(0.0, 4.0, "text", "A") != _pid(0.0, 4.5, "text", "A"))
check("the id is derived from the anchor, not stored beside it",
      all(e["id"] == _pid(e["src_t0"], e["src_t1"],
                          ",".join(sorted(v.get("treatment") or [])) or "none",
                          str(v.get("text_content") or v.get("card_hero") or ""))
          for e, v in zip(_plan, VERDICTS)),
      "an id that does not reproduce from its own anchor is a second thing to "
      "keep in sync")

# ── 5. the plan is EMITTED, not merely computable ───────────────────────────
check("edit() ledgers the plan", 'led["plan"] = _plan' in src,
      "a plan that exists only as a function nobody calls is the "
      "unmounted-feature class")
check("edit() returns the plan to the caller", "plan=_plan" in src)
check("unaddressable rulings fail() loudly", 'fail("plan_unaddressable"' in src)

print()
if fails:
    print("DURABLE-PLAN: FAIL")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("DURABLE-PLAN: PASS — round trip, resegmentation, orphan and unplaceable "
      "both reported, ids stable and anchor-derived, plan emitted")
