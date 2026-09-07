"""SMOKE — a cut at the EDGE is still a cut.

MEASURED, round 18. pet_video kept 12.0s of 18.0s across ONE span; its own
ledger recorded {'keep': 2, 'cut': 1}; the family mix reported cut 0.0/25s.
product_shot kept 10.5s of 15.0s and reported the same zero. A third of each
video was removed and the meter said nothing was cut.

THE COUNT WAS len(keep_spans) - 1 — the number of joins BETWEEN kept regions.
That is right for a cut in the middle and blind to a cut at either end: trim the
tail and one span survives, so it counts zero. Every head/tail trim this
pipeline has ever made was invisible in the cut rate, on every round.

A removal is a maximal region of the source surviving into no keep span: before
the first, between any two, after the last.
"""
import ast
import sys

FAIL = []
ok = lambda c, m: None if c else FAIL.append(m)
SRC = open("agentic_editor_app.py", encoding="utf-8").read()
TREE = ast.parse(SRC)
_ns = {}
_fn = next((n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "count_cuts"), None)
ok(_fn is not None, "count_cuts is not module-level")
if _fn:
    exec(compile(ast.Module([_fn], []), "<s>", "exec"), _ns)
    cc = _ns["count_cuts"]

    # THE ROUND-18 CASES, which the old count reported as zero
    ok(cc([(0.0, 12.0)], 18.0) == 1,
       f"pet_video's shape (kept 0-12 of 18s, tail trimmed) counts "
       f"{cc([(0.0, 12.0)], 18.0)} cuts, not 1 — a third of the video removed "
       f"and reported as no cut")
    ok(cc([(0.0, 10.5)], 15.0) == 1, "product_shot's tail trim counts as no cut")
    ok(cc([(6.0, 18.0)], 18.0) == 1, "a HEAD trim counts as no cut")
    ok(cc([(3.0, 15.0)], 18.0) == 2, "trimming BOTH ends counts as fewer than 2")

    # and the cases the old count got right must stay right
    ok(cc([(0.0, 5.0), (10.0, 18.0)], 18.0) == 1,
       "an internal join no longer counts as one cut")
    ok(cc([(i * 3.85, (i + 1) * 3.85 - 0.5) for i in range(10)], 38.5) == 10,
       "the talking_head shape (10 kept spans with gaps) miscounts")
    ok(cc([(0.0, 18.0)], 18.0) == 0, "an uncut video reports a cut")

    # ADJACENT spans are not a cut — the edit is contiguous there
    ok(cc([(0.0, 9.0), (9.0, 18.0)], 18.0) == 0,
       "two touching spans counted as a cut — nothing was removed between them")
    ok(cc([(0.0, 9.0), (9.02, 18.0)], 18.0) == 0,
       "a 20ms rounding gap counted as a cut — eps must absorb float noise")

    # OVERLAPPING spans are the case the merge actually protects. Without it the
    # tail check reads the LAST span's end rather than the furthest point kept,
    # and invents a trim that never happened. (Adjacent spans are handled by the
    # join epsilon either way, so they do not test the merge at all — my first
    # version asserted only those and a mutation removing the merge passed.)
    ok(cc([(0.0, 18.0), (5.0, 10.0)], 18.0) == 0,
       f"a span fully CONTAINED in another produced "
       f"{cc([(0.0, 18.0), (5.0, 10.0)], 18.0)} cuts — the whole source is kept, "
       f"so the merge must collapse them before the tail is measured")
    ok(cc([(0.0, 10.0), (8.0, 18.0)], 18.0) == 0,
       "two OVERLAPPING spans covering the source reported a cut")

    # degenerate inputs must not invent or crash
    ok(cc([], 18.0) == 0 and cc(None, 18.0) == 0, "empty keep_spans raised or invented a cut")
    ok(cc([(0.0, 12.0)], 0) == 0, "a zero duration must yield 0, not a guess")

# the wiring: the meter must USE it, and the duration must exist
ok("count_cuts(led.get(\"keep_spans\")" in SRC,
   "the family mix does not use count_cuts")
ok("len(led.get(\"keep_spans\") or []) - 1" not in SRC,
   "the old joins-only count is still there")
ok('led["source_duration_s"] = _src_dur' in SRC,
   "source_duration_s is never ledgered — count_cuts would receive None, return "
   "0 silently, and report no cuts forever")

if FAIL:
    print("FAIL smoke_cut_count:")
    for f in FAIL:
        print("  - " + f)
    sys.exit(1)
print("ok smoke_cut_count — head/tail/both-edge trims counted, internal joins "
       "unchanged, adjacent spans and rounding gaps are not cuts, duration ledgered")
