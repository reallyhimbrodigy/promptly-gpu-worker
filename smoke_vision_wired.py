#!/usr/bin/env python3
"""VISION IS CALLED — and it is called on BOTH ROUTES, not just the visual one.

WHY THIS EXISTS. I reported vision as "built and wired both routes". Builder-2's
audit read the committed tree and found ZERO call sites. Both statements were
true of different trees:

    HEAD        extract_beat_frames  def@3233, calls []
                describe_beats_vision  DOES NOT EXIST
    my worktree calls at 8918 / 8925, uncommitted

So vision had never run. Round 46's screen_recording ruled `none` on all 36
beats — the most describable source in the corpus — and I read that as the
agent's judgement when the input simply was not there.

THE CLASS IS NOT "I FORGOT TO COMMIT". It is reporting a WORKING-TREE state as
the state of the world, which is this repo's oldest law (`built` != `committed`
!= `deployed` != `working`) arriving one rung lower than usual: not commit-vs-
deploy, but worktree-vs-commit. A local edit is the least visible state there
is — every check I ran, including every AST smoke, read the same unshared file
and agreed with me.

TWO LEGS, because a definition and a call fail differently:

  DEFINED   every helper the vision path needs exists.
  CALLED    each has at least one call site, and the site is NOT inside a branch
            that only the visual route reaches. `zoom_subject` asks what a push
            moves toward and captions cannot answer it, so the transcript route
            needs sight too.

  python3 smoke_vision_wired.py       exit 0 = vision runs on every route
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "agentic_editor_app.py")
TREE = ast.parse(open(APP, encoding="utf-8").read())
FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)

NEEDED = ("beat_keyframe_times", "extract_beat_frames", "describe_beats_vision",
          "parse_vision_lines", "merge_beat_descriptions")

# ── LEG 1: DEFINED ──────────────────────────────────────────────────────────
defs = {n.name: n for n in ast.walk(TREE) if isinstance(n, ast.FunctionDef)}
for nm in NEEDED:
    ok(nm in defs, f"{nm} is not defined — the vision path has a hole in it")

# ── LEG 2: CALLED ───────────────────────────────────────────────────────────
calls = {nm: [n.lineno for n in ast.walk(TREE)
              if isinstance(n, ast.Call) and getattr(n.func, "id", "") == nm]
         for nm in NEEDED}
for nm in NEEDED:
    ok(calls[nm],
       f"{nm} is DEFINED AND NEVER CALLED — this is the exact shape the audit "
       f"found: a helper that exists, imports clean, passes every scope check, "
       f"and has never once run")

# ── LEG 3: BOTH ROUTES ──────────────────────────────────────────────────────
# The route split is `if _beat_source == "visual": ... else: ...`. A vision call
# inside either arm serves one route. It must sit OUTSIDE both.
def _route_branches(fn):
    out = []
    for n in ast.walk(fn):
        if not isinstance(n, ast.If):
            continue
        _t = ast.dump(n.test)
        if "_beat_source" in _t or "beat_source" in _t:
            out.append(n)
    return out

_edit = defs.get("edit")
ok(_edit is not None, "edit() is gone — this check cannot locate the routes")
if _edit is not None:
    _branches = _route_branches(_edit)
    ok(_branches,
       "no `if _beat_source == ...` branch found in edit() — the route split "
       "this check is written against no longer exists, so leg 3 is vacuous")
    _inside = set()
    for _b in _branches:
        for _st in list(_b.body) + list(_b.orelse):
            for _x in ast.walk(_st):
                if (isinstance(_x, ast.Call)
                        and getattr(_x.func, "id", "") in NEEDED):
                    _inside.add((getattr(_x.func, "id", ""), _x.lineno))
    for nm, ln in sorted(_inside):
        FAIL.append(
            f"{nm}() at line {ln} sits INSIDE the beat_source route branch — "
            f"it runs on one route only. The transcript route knows the words "
            f"and still cannot see the frame; zoom_subject needs sight there "
            f"too. Hoist it above the split.")
    # Non-vacuity: the walk must actually be finding the vision calls somewhere.
    _seen = sum(len(v) for v in calls.values())
    ok(_seen >= len(NEEDED),
       f"only {_seen} vision call(s) found across {len(NEEDED)} helpers — the "
       f"walk is not reaching them and leg 3 forbids nothing")

# ── LEG 4: THE STATE IS A STATE, NOT A VALUE ────────────────────────────────
# A vision call that fails must be ABSENT/FAILED, never an empty description
# list that reads downstream as "nothing on screen". The guard that only checks
# the value lets the failure through.
_src = open(APP, encoding="utf-8").read()
for _st in ("MEASURED", "ABSENT", "FAILED"):
    ok(f'"{_st}"' in _src,
       f"the vision path has no {_st} state — a failed description and a source "
       f"with nothing in it would be indistinguishable")

print()
if FAIL:
    for m in FAIL:
        print(f"  [FAIL] {m}")
    print(f"\n{len(FAIL)} failure(s)")
    sys.exit(1)
print("ok smoke_vision_wired — defined, called, on both routes, states not values")
print("   call sites: " + "  ".join(f"{k}@{v}" for k, v in calls.items()))
